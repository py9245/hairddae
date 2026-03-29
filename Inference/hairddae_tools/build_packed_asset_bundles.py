#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import cv2
import numpy as np

TOOLS_DIR = Path(__file__).resolve().parent
INFERENCE_DIR = TOOLS_DIR.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(INFERENCE_DIR) not in sys.path:
    sys.path.insert(0, str(INFERENCE_DIR))

from local_demo_paths import read_json, resolve_asset_path, static_root
from run_hair_overlay_poc import (
    BUNDLE_PROFILE_EDGE_RISK,
    BUNDLE_PROFILE_LEGACY,
    _BUNDLE_PROFILE_REQUIRED_KEYS,
    _masked_mean_luma,
    _normalize_bundle_profile,
    _packed_bundle_asset_id,
    _synthesize_full_frame_from_hair_rgba,
    expanded_hair_crop,
    hair_bbox_from_mask,
    packed_bundle_path,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build packed legacy/edge-risk asset bundles.")
    parser.add_argument("--static-root", type=Path, default=static_root())
    parser.add_argument("--dataset-code", action="append", dest="dataset_codes")
    parser.add_argument("--profiles", default=f"{BUNDLE_PROFILE_LEGACY},{BUNDLE_PROFILE_EDGE_RISK}")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    return parser.parse_args()


def _iter_dataset_codes(static_root_path: Path, requested: list[str] | None) -> list[str]:
    if requested:
        return [code.strip() for code in requested if code.strip()]
    return sorted(path.name for path in static_root_path.iterdir() if path.is_dir() and path.name.isdigit())


def _read_required_image(
    asset_root: Path,
    metadata: dict[str, Any],
    path_key: str,
    flags: int,
    cached_hair_rgba: list[np.ndarray | None],
) -> np.ndarray | None:
    raw_value = metadata.get(path_key)
    if raw_value not in (None, ""):
        resolved_path = resolve_asset_path(asset_root, str(raw_value))
        if resolved_path.is_file():
            image = cv2.imread(str(resolved_path), flags)
            if image is not None:
                return image

    hair_rgba_path = metadata.get("hair_rgba_path")
    if hair_rgba_path not in (None, ""):
        if cached_hair_rgba[0] is None:
            hair_rgba_resolved = resolve_asset_path(asset_root, str(hair_rgba_path))
            if hair_rgba_resolved.is_file():
                cached_hair_rgba[0] = cv2.imread(str(hair_rgba_resolved), cv2.IMREAD_UNCHANGED)
        hair_rgba = cached_hair_rgba[0]
        if hair_rgba is not None and getattr(hair_rgba, "ndim", 0) == 3:
            synthesized_full_frame = _synthesize_full_frame_from_hair_rgba(
                hair_rgba,
                bbox=metadata.get("hair_rgba_bbox"),
                image_size=metadata.get("image_size"),
                path_key=path_key,
            )
            if synthesized_full_frame is not None:
                return synthesized_full_frame
            if path_key == "image_path" and hair_rgba.shape[2] >= 3:
                return hair_rgba[:, :, :3].copy()
            if path_key == "alpha_path" and hair_rgba.shape[2] >= 4:
                return hair_rgba[:, :, 3].copy()
    return None


def _build_payload(asset_root: Path, metadata_path_str: str, profile: str) -> dict[str, Any] | None:
    metadata = read_json(resolve_asset_path(asset_root, metadata_path_str))
    anchors = read_json(resolve_asset_path(asset_root, metadata["anchors_path"]))["anchors"]
    required_keys = _BUNDLE_PROFILE_REQUIRED_KEYS[profile]
    cached_hair_rgba: list[np.ndarray | None] = [None]

    image = _read_required_image(asset_root, metadata, "image_path", cv2.IMREAD_COLOR, cached_hair_rgba)
    alpha = _read_required_image(asset_root, metadata, "alpha_path", cv2.IMREAD_GRAYSCALE, cached_hair_rgba)
    hair_mask = _read_required_image(asset_root, metadata, "hair_mask_path", cv2.IMREAD_GRAYSCALE, cached_hair_rgba)
    if hair_mask is None or alpha is None:
        return None
    face_mask = _read_required_image(asset_root, metadata, "face_mask_path", cv2.IMREAD_GRAYSCALE, cached_hair_rgba)
    protect_face_mask = _read_required_image(asset_root, metadata, "protect_face_mask_path", cv2.IMREAD_GRAYSCALE, cached_hair_rgba)

    image_for_bounds = image if image is not None else alpha
    hair_bbox = hair_bbox_from_mask(hair_mask)
    crop_box = expanded_hair_crop(hair_bbox, image_for_bounds.shape[1], image_for_bounds.shape[0])
    hair_luma = _masked_mean_luma(image, hair_mask) if image is not None else None
    x0, y0, x1, y1 = crop_box

    payload: dict[str, Any] = {
        "anchors_json": np.array(json.dumps(anchors, ensure_ascii=True), dtype=np.str_),
        "crop_box": np.array(crop_box, dtype=np.int32),
        "hair_bbox": np.array(hair_bbox, dtype=np.int32),
        "hair_luma": np.array([-1.0 if hair_luma is None else float(hair_luma)], dtype=np.float32),
        "image_size": np.array([image_for_bounds.shape[0], image_for_bounds.shape[1]], dtype=np.int32),
        "packed_crop_only": np.array([1], dtype=np.uint8),
    }
    if "image_path" in required_keys and image is not None:
        payload["image"] = image[y0:y1, x0:x1]
    if "alpha_path" in required_keys:
        payload["alpha"] = alpha[y0:y1, x0:x1]
    if "hair_mask_path" in required_keys:
        payload["hair_mask"] = hair_mask[y0:y1, x0:x1]
    if "face_mask_path" in required_keys and face_mask is not None:
        payload["face_mask"] = face_mask[y0:y1, x0:x1]
    if "protect_face_mask_path" in required_keys and protect_face_mask is not None:
        payload["protect_face_mask"] = protect_face_mask[y0:y1, x0:x1]
    return payload


def build_packed_bundles_for_dataset(
    dataset_root: Path,
    *,
    profiles: list[str],
    force: bool,
    limit: int,
) -> dict[str, int]:
    manifest_path = dataset_root / "manifests" / "asset_index_v0.json"
    if not manifest_path.is_file():
        return {"generated": 0, "skipped": 0, "failed": 0}
    index_payload = read_json(manifest_path)
    items = list(index_payload.get("items") or [])
    if limit > 0:
        items = items[:limit]

    generated = 0
    skipped = 0
    failed = 0

    for item in items:
        metadata_path_str = str(item.get("metadata_path") or "").strip()
        if not metadata_path_str:
            failed += 1
            continue
        metadata = read_json(resolve_asset_path(dataset_root, metadata_path_str))
        asset_id = _packed_bundle_asset_id(metadata, metadata_path_str)
        for profile in profiles:
            target_path = packed_bundle_path(dataset_root, asset_id, profile)
            if target_path.is_file() and not force:
                skipped += 1
                continue
            payload = _build_payload(dataset_root, metadata_path_str, profile)
            if payload is None:
                failed += 1
                continue
            target_path.parent.mkdir(parents=True, exist_ok=True)
            np.savez(target_path, **payload)
            generated += 1
    return {"generated": generated, "skipped": skipped, "failed": failed}


def main() -> int:
    args = parse_args()
    profiles = [_normalize_bundle_profile(profile) for profile in str(args.profiles).split(",") if profile.strip()]
    dataset_codes = _iter_dataset_codes(args.static_root, args.dataset_codes)
    for dataset_code in dataset_codes:
        dataset_root = args.static_root / dataset_code
        stats = build_packed_bundles_for_dataset(
            dataset_root,
            profiles=profiles,
            force=bool(args.force),
            limit=max(0, int(args.limit)),
        )
        print(
            f"{dataset_code}: generated={stats['generated']} skipped={stats['skipped']} failed={stats['failed']}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
