#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from local_demo_paths import read_json, resolve_asset_path, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score asset naturalness risk using comprehensive frame features."
    )
    parser.add_argument("--asset-root", required=True, help="Asset factory root")
    parser.add_argument("--feature-root", required=True, help="Comprehensive feature root")
    parser.add_argument("--skip-missing-features", action="store_true", help="Skip assets without feature metadata")
    parser.add_argument("--skip-existing", action="store_true", help="Skip assets that already have naturalness_risk_v1")
    parser.add_argument("--write-back-metadata", action="store_true", help="Write scores back into asset metadata JSON")
    parser.add_argument("--limit", type=int, default=0, help="Optional cap on assets")
    return parser.parse_args()


def load_mask(path: Path | None) -> np.ndarray | None:
    if path is None or not path.is_file():
        return None
    mask = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if mask is None or mask.size == 0:
        return None
    return mask


def dilate_mask(mask: np.ndarray | None, radius: int) -> np.ndarray | None:
    if mask is None or mask.size == 0:
        return None
    if radius <= 0:
        return mask
    kernel_size = radius * 2 + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    return cv2.dilate(mask, kernel, iterations=1)


def mask_ratio(mask: np.ndarray | None) -> float:
    if mask is None or mask.size == 0:
        return 0.0
    return float(np.count_nonzero(mask)) / float(mask.shape[0] * mask.shape[1])


def overlap_ratio(base_mask: np.ndarray | None, other_mask: np.ndarray | None) -> float:
    if base_mask is None or other_mask is None or base_mask.size == 0:
        return 0.0
    base = np.asarray(base_mask) > 0
    if np.count_nonzero(base) == 0:
        return 0.0
    other = np.asarray(other_mask) > 0
    overlap = np.count_nonzero(base & other)
    return float(overlap) / float(np.count_nonzero(base))


def union_masks(*masks: np.ndarray | None) -> np.ndarray | None:
    valid_masks = [np.asarray(mask, dtype=np.uint8) for mask in masks if mask is not None and np.asarray(mask).size > 0]
    if not valid_masks:
        return None
    merged = valid_masks[0].copy()
    for mask in valid_masks[1:]:
        merged = cv2.bitwise_or(merged, mask)
    return merged


def outside_ratio(base_mask: np.ndarray | None, support_mask: np.ndarray | None, dilate_radius: int = 0) -> tuple[float, np.ndarray | None]:
    if base_mask is None or support_mask is None or base_mask.size == 0:
        return 0.0, None
    base = (np.asarray(base_mask) > 0).astype(np.uint8) * 255
    support = dilate_mask((np.asarray(support_mask) > 0).astype(np.uint8) * 255, dilate_radius)
    if support is None:
        return 0.0, None
    outside = cv2.bitwise_and(base, cv2.bitwise_not(support))
    area = int(np.count_nonzero(base))
    if area <= 0:
        return 0.0, outside
    return float(np.count_nonzero(outside)) / float(area), outside


def outside_component_stats(outside_mask: np.ndarray | None) -> dict[str, Any]:
    if outside_mask is None or outside_mask.size == 0 or np.count_nonzero(outside_mask) == 0:
        return {"count": 0, "largest_area": 0.0, "slender_count": 0}
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats((outside_mask > 0).astype(np.uint8), connectivity=8)
    count = 0
    largest_area = 0.0
    slender_count = 0
    for label_idx in range(1, num_labels):
        area = float(stats[label_idx, cv2.CC_STAT_AREA])
        width = max(1.0, float(stats[label_idx, cv2.CC_STAT_WIDTH]))
        height = max(1.0, float(stats[label_idx, cv2.CC_STAT_HEIGHT]))
        aspect = max(width / height, height / width)
        count += 1
        largest_area = max(largest_area, area)
        if area >= 12.0 and aspect >= 2.6:
            slender_count += 1
    return {"count": count, "largest_area": round(largest_area, 3), "slender_count": slender_count}


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def asset_frame_stem(asset_id: str, style_id: str | None) -> str:
    prefix = f"{style_id}__" if style_id else ""
    if prefix and asset_id.startswith(prefix):
        return asset_id[len(prefix) :]
    if "__" in asset_id:
        return asset_id.split("__", 1)[1]
    return asset_id


def far_side_mask(shape: tuple[int, int], face_center_x: float, yaw_1deg: int) -> np.ndarray:
    height, width = shape
    x_coords = np.arange(width, dtype=np.float32)
    if yaw_1deg >= 0:
        mask = x_coords[None, :] >= face_center_x
    else:
        mask = x_coords[None, :] <= face_center_x
    return np.repeat(mask.astype(np.uint8), height, axis=0) * 255


def frontal_upper_mask(shape: tuple[int, int], face_bbox: dict[str, Any]) -> np.ndarray:
    height, width = shape
    mask = np.zeros((height, width), dtype=np.uint8)
    x0 = max(0, int(round(float(face_bbox.get("x", 0.0)) - float(face_bbox.get("w", 0.0)) * 0.10)))
    x1 = min(width, int(round(float(face_bbox.get("x", 0.0)) + float(face_bbox.get("w", 0.0)) * 1.10)))
    y0 = max(0, int(round(float(face_bbox.get("y", 0.0)) - float(face_bbox.get("h", 0.0)) * 0.45)))
    y1 = min(height, int(round(float(face_bbox.get("y", 0.0)) + float(face_bbox.get("h", 0.0)) * 0.40)))
    if x1 > x0 and y1 > y0:
        mask[y0:y1, x0:x1] = 255
    return mask


def compute_scores(
    asset_meta: dict[str, Any],
    feature_meta: dict[str, Any],
    asset_root: Path,
    feature_root: Path,
) -> dict[str, Any]:
    asset_hair = load_mask(resolve_asset_path(asset_root, asset_meta.get("hair_mask_path", "")))
    asset_face = load_mask(resolve_asset_path(asset_root, asset_meta.get("face_mask_path", "")))
    asset_ear_left = load_mask(resolve_asset_path(asset_root, asset_meta.get("ear_mask_left_path", "")))
    asset_ear_right = load_mask(resolve_asset_path(asset_root, asset_meta.get("ear_mask_right_path", "")))
    if asset_hair is None:
        return {
            "ok": False,
            "reason": "missing_asset_hair_mask",
        }

    parsing = feature_meta.get("parsing", {})
    person_seg = feature_meta.get("person_segmentation", {})
    face = feature_meta.get("face", {})
    face_bbox = face.get("face_bbox") or {}
    pose = face.get("pose") or {}
    anchors = face.get("anchors") or {}
    if not face_bbox or not anchors:
        return {
            "ok": False,
            "reason": "missing_face_features",
        }

    feature_face = load_mask(feature_root / parsing.get("mask_paths", {}).get("face_mask", "")) if parsing.get("ok") else None
    feature_ear_left = load_mask(feature_root / parsing.get("mask_paths", {}).get("ear_left_mask", "")) if parsing.get("ok") else None
    feature_ear_right = load_mask(feature_root / parsing.get("mask_paths", {}).get("ear_right_mask", "")) if parsing.get("ok") else None
    feature_head = load_mask(feature_root / parsing.get("head_silhouette_mask_path", "")) if parsing.get("ok") else None
    combined_person = load_mask(feature_root / person_seg.get("combined", {}).get("segmentation_mask_path", "")) if person_seg.get("combined", {}).get("ok") else None

    yaw_1deg = int(pose.get("yaw_1deg", 0))
    pitch_1deg = int(pose.get("pitch_1deg", 0))
    roll_1deg = int(pose.get("roll_1deg", 0))
    face_center_x = (
        float(anchors["left_temple"]["x"])
        + float(anchors["right_temple"]["x"])
        + float(anchors["lower_left"]["x"])
        + float(anchors["lower_right"]["x"])
        + float(anchors["forehead_center"]["x"])
    ) / 5.0

    head_excess_ratio, head_excess_mask = outside_ratio(asset_hair, feature_head, dilate_radius=6)
    person_excess_ratio, person_excess_mask = outside_ratio(asset_hair, combined_person, dilate_radius=10)
    face_overlap = overlap_ratio(asset_hair, dilate_mask(feature_face, 4))
    feature_ear_union = union_masks(feature_ear_left, feature_ear_right)
    ear_overlap = overlap_ratio(asset_hair, dilate_mask(feature_ear_union, 4))
    asset_face_overlap = overlap_ratio(asset_hair, dilate_mask(asset_face, 2))
    asset_ear_union = union_masks(asset_ear_left, asset_ear_right)
    asset_ear_overlap = overlap_ratio(asset_hair, dilate_mask(asset_ear_union, 2))
    hole_ratio = float(asset_meta.get("hole_ratio") or 0.0)
    hole_pixels = int(asset_meta.get("hole_pixels") or 0)
    fringe_fill_ratio = asset_meta.get("fringe_fill_ratio")
    fringe_fill_ratio = None if fringe_fill_ratio is None else float(fringe_fill_ratio)
    mask_component_count = int(asset_meta.get("mask_component_count") or 0)

    frontal_mask = frontal_upper_mask(asset_hair.shape, face_bbox)
    frontal_head_excess = cv2.bitwise_and(head_excess_mask, frontal_mask) if head_excess_mask is not None else None
    frontal_head_excess_ratio = (
        float(np.count_nonzero(frontal_head_excess)) / max(1, int(np.count_nonzero(asset_hair)))
        if frontal_head_excess is not None
        else 0.0
    )
    frontal_components = outside_component_stats(frontal_head_excess)

    far_mask = far_side_mask(asset_hair.shape, face_center_x, yaw_1deg)
    far_head_excess = cv2.bitwise_and(head_excess_mask, far_mask) if head_excess_mask is not None else None
    far_person_excess = cv2.bitwise_and(person_excess_mask, far_mask) if person_excess_mask is not None else None
    far_head_excess_ratio = (
        float(np.count_nonzero(far_head_excess)) / max(1, int(np.count_nonzero(asset_hair)))
        if far_head_excess is not None
        else 0.0
    )
    far_person_excess_ratio = (
        float(np.count_nonzero(far_person_excess)) / max(1, int(np.count_nonzero(asset_hair)))
        if far_person_excess is not None
        else 0.0
    )
    far_components = outside_component_stats(far_head_excess)

    frontal_factor = clamp01((12.0 - abs(float(yaw_1deg))) / 12.0) * clamp01((8.0 - abs(float(roll_1deg))) / 8.0)
    side_factor = clamp01((abs(float(yaw_1deg)) - 14.0) / 16.0)

    frontal_spike_risk = clamp01(
        frontal_factor
        * (
            frontal_head_excess_ratio * 8.0
            + frontal_components["slender_count"] * 0.18
            + clamp01(frontal_components["largest_area"] / 220.0) * 0.25
        )
    )
    side_shell_risk = clamp01(
        side_factor
        * (
            far_head_excess_ratio * 6.0
            + far_person_excess_ratio * 3.5
            + far_components["slender_count"] * 0.10
        )
    )
    face_skin_overlap_risk = clamp01(max(face_overlap, asset_face_overlap) * 8.0)
    ear_skin_overlap_risk = clamp01(max(ear_overlap, asset_ear_overlap) * 5.0)
    global_excess_risk = clamp01(max(head_excess_ratio * 3.5, person_excess_ratio * 2.2))
    hole_shape_risk = clamp01(hole_ratio * 180.0 + max(0, hole_pixels - 18) / 90.0 + max(0, mask_component_count - 2) * 0.08)
    fringe_deformation_risk = 0.0
    if fringe_fill_ratio is not None:
        fringe_deformation_risk = clamp01(max(0.0, 0.30 - fringe_fill_ratio) / 0.16)
    downward_face_cover_risk = 0.0
    if pitch_1deg >= 24:
        downward_face_cover_risk = clamp01(max(face_overlap, asset_face_overlap) * 24.0 + naturalness_bias(face_bbox))
    elif pitch_1deg >= 20:
        downward_face_cover_risk = clamp01(max(face_overlap, asset_face_overlap) * 18.0)
    elif pitch_1deg >= 16:
        downward_face_cover_risk = clamp01(max(face_overlap, asset_face_overlap) * 12.0)
    multi_risk_count = sum(
        risk_value >= 0.28
        for risk_value in (
            frontal_spike_risk,
            side_shell_risk,
            face_skin_overlap_risk,
            hole_shape_risk,
            fringe_deformation_risk,
            downward_face_cover_risk,
        )
    )
    compound_risk = clamp01(max(0, multi_risk_count - 1) * 0.14)

    overall_risk = clamp01(
        0.22 * frontal_spike_risk
        + 0.20 * side_shell_risk
        + 0.16 * face_skin_overlap_risk
        + 0.08 * ear_skin_overlap_risk
        + 0.06 * global_excess_risk
        + 0.12 * hole_shape_risk
        + 0.08 * fringe_deformation_risk
        + 0.08 * downward_face_cover_risk
        + 0.08 * compound_risk
    )

    tags: list[str] = []
    if frontal_spike_risk >= 0.45:
        tags.append("frontal_spike_risk")
    if side_shell_risk >= 0.45:
        tags.append("side_shell_risk")
    if face_skin_overlap_risk >= 0.40:
        tags.append("face_skin_overlap_risk")
    if ear_skin_overlap_risk >= 0.40:
        tags.append("ear_skin_overlap_risk")
    if global_excess_risk >= 0.42:
        tags.append("global_excess_risk")
    if hole_shape_risk >= 0.30:
        tags.append("hole_shape_risk")
    if fringe_deformation_risk >= 0.42:
        tags.append("fringe_deformation_risk")
    if downward_face_cover_risk >= 0.35:
        tags.append("downward_face_cover_risk")

    return {
        "ok": True,
        "naturalness_risk_v1": round(overall_risk, 6),
        "naturalness_score_v1": round(1.0 - overall_risk, 6),
        "naturalness_risk_components_v1": {
            "frontal_spike_risk": round(frontal_spike_risk, 6),
            "side_shell_risk": round(side_shell_risk, 6),
            "face_skin_overlap_risk": round(face_skin_overlap_risk, 6),
            "ear_skin_overlap_risk": round(ear_skin_overlap_risk, 6),
            "global_excess_risk": round(global_excess_risk, 6),
            "hole_shape_risk": round(hole_shape_risk, 6),
            "fringe_deformation_risk": round(fringe_deformation_risk, 6),
            "downward_face_cover_risk": round(downward_face_cover_risk, 6),
            "compound_risk": round(compound_risk, 6),
        },
        "naturalness_metrics_v1": {
            "head_excess_ratio": round(head_excess_ratio, 6),
            "person_excess_ratio": round(person_excess_ratio, 6),
            "face_overlap_ratio_runtime": round(face_overlap, 6),
            "ear_overlap_ratio_runtime": round(ear_overlap, 6),
            "face_overlap_ratio_asset": round(asset_face_overlap, 6),
            "ear_overlap_ratio_asset": round(asset_ear_overlap, 6),
            "frontal_head_excess_ratio": round(frontal_head_excess_ratio, 6),
            "far_head_excess_ratio": round(far_head_excess_ratio, 6),
            "far_person_excess_ratio": round(far_person_excess_ratio, 6),
            "frontal_outside_components": frontal_components,
            "far_outside_components": far_components,
            "hole_ratio_asset": round(hole_ratio, 6),
            "hole_pixels_asset": hole_pixels,
            "fringe_fill_ratio_asset": None if fringe_fill_ratio is None else round(fringe_fill_ratio, 6),
            "mask_component_count_asset": mask_component_count,
            "pitch_1deg_runtime": pitch_1deg,
        },
        "naturalness_failure_tags_v1": tags,
    }


def naturalness_bias(face_bbox: dict[str, Any]) -> float:
    if not face_bbox:
        return 0.0
    face_h = float(face_bbox.get("h") or 0.0)
    face_w = float(face_bbox.get("w") or 0.0)
    if face_h <= 0.0 or face_w <= 0.0:
        return 0.0
    aspect = max(face_h / max(face_w, 1.0), 1.0)
    return clamp01((aspect - 1.18) / 0.55) * 0.18


def main() -> None:
    args = parse_args()
    asset_root = Path(args.asset_root).resolve()
    feature_root = Path(args.feature_root).resolve()
    metadata_dir = asset_root / "metadata"
    manifest_dir = asset_root / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)

    metadata_paths = sorted(metadata_dir.glob("*.json"))
    if args.limit > 0:
        metadata_paths = metadata_paths[: args.limit]

    results: list[dict[str, Any]] = []
    summary = {
        "asset_root": str(asset_root),
        "feature_root": str(feature_root),
        "processed": 0,
        "skipped_existing": 0,
        "scored": 0,
        "missing_feature": 0,
        "failed": 0,
        "tag_counts": {},
    }

    for metadata_path in metadata_paths:
        asset_meta = read_json(metadata_path)
        asset_id = str(asset_meta.get("asset_id") or metadata_path.stem)
        style_id = asset_meta.get("style_id")
        frame_stem = asset_frame_stem(asset_id, style_id)
        feature_path = feature_root / "metadata" / f"{frame_stem}.json"

        if args.skip_existing and asset_meta.get("naturalness_risk_v1") is not None:
            summary["skipped_existing"] += 1
            continue

        summary["processed"] += 1

        if not feature_path.is_file():
            result = {
                "asset_id": asset_id,
                "ok": False,
                "reason": "missing_feature_metadata",
                "feature_path": str(feature_path),
            }
            results.append(result)
            summary["missing_feature"] += 1
            if not args.skip_missing_features and args.write_back_metadata:
                asset_meta["naturalness_risk_v1"] = None
                asset_meta["naturalness_score_v1"] = None
                asset_meta["naturalness_failure_tags_v1"] = ["missing_feature_metadata"]
                write_json(metadata_path, asset_meta)
            continue

        feature_meta = read_json(feature_path)
        score_payload = compute_scores(asset_meta, feature_meta, asset_root, feature_root)
        result = {
            "asset_id": asset_id,
            "feature_path": str(feature_path),
            **score_payload,
        }
        results.append(result)

        if not score_payload.get("ok"):
            summary["failed"] += 1
            continue

        summary["scored"] += 1
        for tag in score_payload.get("naturalness_failure_tags_v1", []):
            summary["tag_counts"][tag] = int(summary["tag_counts"].get(tag, 0)) + 1

        if args.write_back_metadata:
            asset_meta.update(
                {
                    "naturalness_risk_v1": score_payload["naturalness_risk_v1"],
                    "naturalness_score_v1": score_payload["naturalness_score_v1"],
                    "naturalness_risk_components_v1": score_payload["naturalness_risk_components_v1"],
                    "naturalness_metrics_v1": score_payload["naturalness_metrics_v1"],
                    "naturalness_failure_tags_v1": score_payload["naturalness_failure_tags_v1"],
                }
            )
            write_json(metadata_path, asset_meta)

    write_json(
        manifest_dir / "asset_naturalness_summary_v1.json",
        {
            "summary": summary,
            "items": results,
        },
    )


if __name__ == "__main__":
    main()
