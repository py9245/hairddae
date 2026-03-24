#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

from local_demo_paths import read_json, resolve_asset_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synthesize missing full-frame rgb assets from hair_rgba crops."
    )
    parser.add_argument("--asset-root", required=True, help="Dataset root, e.g. ../static/0010")
    parser.add_argument(
        "--asset-index",
        default="manifests/asset_index_v0.json",
        help="Relative path to asset index under asset root.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Rewrite image_path targets even if they already exist.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process at most N assets. 0 means no limit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be created without writing files.",
    )
    return parser.parse_args()


def _load_asset_index(asset_root: Path, asset_index_rel: str) -> list[dict[str, object]]:
    asset_index_path = resolve_asset_path(asset_root, asset_index_rel)
    payload = json.loads(asset_index_path.read_text(encoding="utf-8"))
    items = payload.get("items")
    if not isinstance(items, list):
        raise RuntimeError(f"invalid asset index payload: {asset_index_path}")
    return [row for row in items if isinstance(row, dict)]


def _coerce_image_size(metadata: dict[str, object]) -> tuple[int, int] | None:
    image_size = metadata.get("image_size")
    if not isinstance(image_size, dict):
        return None
    width = int(image_size.get("width") or 0)
    height = int(image_size.get("height") or 0)
    if width <= 0 or height <= 0:
        return None
    return width, height


def _coerce_bbox(metadata: dict[str, object]) -> tuple[int, int, int, int] | None:
    bbox = metadata.get("hair_rgba_bbox")
    if not isinstance(bbox, dict):
        return None
    x = int(bbox.get("x") or 0)
    y = int(bbox.get("y") or 0)
    w = int(bbox.get("w") or 0)
    h = int(bbox.get("h") or 0)
    if w <= 0 or h <= 0:
        return None
    return x, y, w, h


def _synthesize_full_frame_rgb(
    hair_rgba: np.ndarray,
    *,
    canvas_width: int,
    canvas_height: int,
    bbox_x: int,
    bbox_y: int,
    bbox_w: int,
    bbox_h: int,
) -> np.ndarray:
    if hair_rgba.ndim != 3 or hair_rgba.shape[2] < 3:
        raise RuntimeError("hair_rgba image must have at least 3 channels")

    crop_rgb = hair_rgba[:, :, :3]
    if crop_rgb.shape[1] != bbox_w or crop_rgb.shape[0] != bbox_h:
        crop_rgb = cv2.resize(crop_rgb, (bbox_w, bbox_h), interpolation=cv2.INTER_LINEAR)

    canvas = np.zeros((canvas_height, canvas_width, 3), dtype=np.uint8)
    dst_x0 = max(0, bbox_x)
    dst_y0 = max(0, bbox_y)
    dst_x1 = min(canvas_width, bbox_x + bbox_w)
    dst_y1 = min(canvas_height, bbox_y + bbox_h)
    if dst_x1 <= dst_x0 or dst_y1 <= dst_y0:
        raise RuntimeError("hair_rgba_bbox lies outside image_size")

    src_x0 = dst_x0 - bbox_x
    src_y0 = dst_y0 - bbox_y
    src_x1 = src_x0 + (dst_x1 - dst_x0)
    src_y1 = src_y0 + (dst_y1 - dst_y0)
    canvas[dst_y0:dst_y1, dst_x0:dst_x1] = crop_rgb[src_y0:src_y1, src_x0:src_x1]
    return canvas


def _write_png(path: Path, image_bgr: np.ndarray) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        path.unlink()

    encoded_ok, encoded = cv2.imencode(".png", image_bgr)
    if encoded_ok:
        path.write_bytes(encoded.tobytes())
        return path.is_file() and not path.is_symlink()

    try:
        Image.fromarray(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB), mode="RGB").save(
            path,
            format="PNG",
            optimize=False,
        )
        return path.is_file() and not path.is_symlink()
    except Exception:
        return False


def process_asset_root(
    *,
    asset_root: Path,
    asset_index_rel: str = "manifests/asset_index_v0.json",
    overwrite: bool = False,
    limit: int = 0,
    dry_run: bool = False,
    verbose: bool = True,
) -> dict[str, Any]:
    items = _load_asset_index(asset_root, asset_index_rel)
    processed = 0
    created = 0
    skipped_exists = 0
    skipped_invalid = 0
    errors = 0

    for item in items:
        if limit > 0 and processed >= limit:
            break

        metadata_path_raw = str(item.get("metadata_path") or "").strip()
        if not metadata_path_raw:
            skipped_invalid += 1
            continue

        metadata = read_json(resolve_asset_path(asset_root, metadata_path_raw))
        image_path_raw = str(metadata.get("image_path") or "").strip()
        hair_rgba_path_raw = str(metadata.get("hair_rgba_path") or "").strip()
        image_size = _coerce_image_size(metadata)
        bbox = _coerce_bbox(metadata)
        asset_id = str(item.get("asset_id") or metadata_path_raw)

        if not image_path_raw or not hair_rgba_path_raw or image_size is None or bbox is None:
            skipped_invalid += 1
            continue

        image_path = resolve_asset_path(asset_root, image_path_raw)
        if image_path.is_file() and not image_path.is_symlink() and not overwrite:
            skipped_exists += 1
            continue

        hair_rgba_path = resolve_asset_path(asset_root, hair_rgba_path_raw)
        hair_rgba = cv2.imread(str(hair_rgba_path), cv2.IMREAD_UNCHANGED)
        if hair_rgba is None:
            print(f"[error] {asset_id}: failed to read hair_rgba_path={hair_rgba_path}")
            errors += 1
            continue

        processed += 1
        width, height = image_size
        x, y, w, h = bbox

        try:
            full_frame_rgb = _synthesize_full_frame_rgb(
                hair_rgba,
                canvas_width=width,
                canvas_height=height,
                bbox_x=x,
                bbox_y=y,
                bbox_w=w,
                bbox_h=h,
            )
        except Exception as exc:
            if verbose:
                print(f"[error] {asset_id}: {exc}")
            errors += 1
            continue

        if verbose:
            print(f"[create] {asset_id}: {image_path_raw}")
        if dry_run:
            continue

        write_ok = _write_png(image_path, full_frame_rgb)
        if not write_ok:
            if verbose:
                print(f"[error] {asset_id}: failed to write {image_path}")
            errors += 1
            continue
        created += 1

    summary = {
        "asset_root": str(asset_root),
        "processed": processed,
        "created": created,
        "skipped_exists": skipped_exists,
        "skipped_invalid": skipped_invalid,
        "errors": errors,
        "dry_run": bool(dry_run),
    }
    if verbose:
        print(json.dumps(summary, ensure_ascii=False))
    return summary


def main() -> None:
    args = parse_args()
    process_asset_root(
        asset_root=Path(args.asset_root).resolve(),
        asset_index_rel=args.asset_index,
        overwrite=bool(args.overwrite),
        limit=int(args.limit),
        dry_run=bool(args.dry_run),
        verbose=True,
    )


if __name__ == "__main__":
    main()
