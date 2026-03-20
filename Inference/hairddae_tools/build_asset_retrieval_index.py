#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from local_demo_paths import load_manifest_payload, read_json, resolve_asset_path, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build retrieval index and simple auto-QC for asset factory.")
    parser.add_argument("--asset-root", required=True)
    parser.add_argument("--write-back-metadata", action="store_true")
    return parser.parse_args()


def point_distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    if any(a.get(k) is None for k in ("x", "y")) or any(b.get(k) is None for k in ("x", "y")):
        return 0.0
    return float(math.hypot(a["x"] - b["x"], a["y"] - b["y"]))


def mask_area_ratio(mask_path: Path) -> float:
    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        return 0.0
    return float(np.count_nonzero(mask)) / float(mask.shape[0] * mask.shape[1])


def value_in_range(value: float | None, low: float, high: float) -> bool:
    return value is not None and low <= value <= high


def normalize(value: float, low: float, high: float) -> float:
    if value <= low:
        return 0.0
    if value >= high:
        return 1.0
    return (value - low) / (high - low)


def approved_runtime_face_overlap_limit(pitch_value: int) -> float:
    # Keep mild up/down pitch bins better covered while staying stricter on
    # strong downward poses where face-cover artifacts are more noticeable.
    if -6 <= pitch_value <= 4:
        return 0.0062
    if pitch_value >= 16:
        return 0.0055
    return 0.0057


def main() -> None:
    args = parse_args()
    asset_root = Path(args.asset_root).resolve()
    payload = load_manifest_payload(asset_root)
    items = payload["items"]
    critical_failure_tags = {
        "empty_mask",
        "top_cut_risk",
        "side_cut_risk",
        "fragmented_mask",
        "internal_hole_risk",
        "fringe_cut_risk",
        "face_overlap_risk",
        "side_skin_overlap_risk",
        "missing_anchor_data",
    }
    critical_naturalness_tags = {
        "frontal_spike_risk",
        "side_shell_risk",
        "face_skin_overlap_risk",
        "ear_skin_overlap_risk",
        "downward_face_cover_risk",
        "hole_shape_risk",
        "fringe_deformation_risk",
    }

    index_items: list[dict[str, Any]] = []
    approved_count = 0
    approved_runtime_count = 0
    rejected_count = 0
    failure_counter: Counter[str] = Counter()

    for row in items:
        anchors_path = resolve_asset_path(asset_root, row["anchors_path"])
        metadata = read_json(resolve_asset_path(asset_root, row["metadata_path"]))
        anchors_payload = read_json(anchors_path)
        anchors = anchors_payload.get("anchors")
        image_size = metadata.get("image_size") or {}
        width = image_size.get("width")
        height = image_size.get("height")
        has_anchor_data = isinstance(anchors, dict) and width not in (None, 0) and height not in (None, 0)

        if has_anchor_data:
            temple_span_ratio = point_distance(anchors["left_temple"], anchors["right_temple"]) / max(1.0, width)
            lower_span_ratio = point_distance(anchors["lower_left"], anchors["lower_right"]) / max(1.0, width)
            neck_span_ratio = point_distance(anchors["neck_left"], anchors["neck_right"]) / max(1.0, width)
            crown_offset_ratio = abs(anchors["forehead_center"]["y"] - anchors["crown"]["y"]) / max(1.0, height)
        else:
            temple_span_ratio = 0.0
            lower_span_ratio = 0.0
            neck_span_ratio = 0.0
            crown_offset_ratio = 0.0

        hair_area = mask_area_ratio(resolve_asset_path(asset_root, metadata["hair_mask_path"]))
        alpha_area = mask_area_ratio(resolve_asset_path(asset_root, metadata["alpha_path"]))
        hole_ratio = float(metadata.get("hole_ratio") or 0.0)
        fringe_fill_ratio = metadata.get("fringe_fill_ratio")
        failure_tags = metadata.get("failure_tags", [])
        naturalness_risk = float(metadata.get("naturalness_risk_v1") or 0.0)
        face_overlap_ratio = float(metadata.get("face_overlap_ratio") or 0.0)
        pitch_value = int(metadata.get("pitch_1deg") or 0)
        derived_naturalness_tags: list[str] = []
        if pitch_value >= 24:
            if face_overlap_ratio >= 0.008 or naturalness_risk >= 0.05:
                derived_naturalness_tags.append("downward_face_cover_risk")
        elif pitch_value >= 20:
            if face_overlap_ratio >= 0.010 or naturalness_risk >= 0.055:
                derived_naturalness_tags.append("downward_face_cover_risk")
        elif pitch_value >= 16:
            if face_overlap_ratio >= 0.012 and naturalness_risk >= 0.05:
                derived_naturalness_tags.append("downward_face_cover_risk")
        naturalness_failure_tags = sorted(
            set(metadata.get("naturalness_failure_tags_v1", [])) | set(derived_naturalness_tags)
        )
        if not has_anchor_data:
            failure_tags = sorted(set(failure_tags + ["missing_anchor_data"]))
        critical_failure_tags_present = sorted(tag for tag in failure_tags if tag in critical_failure_tags)
        has_critical_failures = bool(critical_failure_tags_present)
        critical_naturalness_tags_present = sorted(
            tag for tag in naturalness_failure_tags if tag in critical_naturalness_tags
        )
        has_critical_naturalness_failures = bool(critical_naturalness_tags_present) or naturalness_risk >= 0.34
        failure_counter.update(failure_tags)
        failure_counter.update({f"naturalness::{tag}": 1 for tag in naturalness_failure_tags})

        qc_checks = {
            "face_ratio": value_in_range(metadata.get("face_ratio"), 0.02, 0.20),
            "hair_width_ratio": value_in_range(metadata.get("hair_width_ratio"), 0.15, 0.75),
            "hair_height_ratio": value_in_range(metadata.get("hair_height_ratio"), 0.27, 0.49),
            "hair_area_ratio": value_in_range(hair_area, 0.03, 0.09),
            "alpha_area_ratio": value_in_range(alpha_area, 0.005, 0.12),
            "temple_span_ratio": value_in_range(temple_span_ratio, 0.13, 0.19),
            "lower_span_ratio": value_in_range(lower_span_ratio, 0.105, 0.145),
            "crown_offset_ratio": value_in_range(crown_offset_ratio, 0.118, 0.139),
            "naturalness_risk_v1": naturalness_risk <= 0.20,
            "face_overlap_ratio": face_overlap_ratio <= 0.007,
            "hole_ratio": hole_ratio <= 0.0004,
            "fringe_fill_ratio": fringe_fill_ratio is None or float(fringe_fill_ratio) >= 0.28,
            "failure_tags": not has_critical_failures and not has_critical_naturalness_failures,
        }
        pass_count = sum(bool(v) for v in qc_checks.values())
        total_qc_checks = len(qc_checks)
        quality_score = round(pass_count / total_qc_checks, 6)
        approved_qc_checks = {
            "all_qc_checks": pass_count == total_qc_checks,
            "naturalness_risk_v1": naturalness_risk <= 0.18,
        }
        approved = (
            (not has_critical_failures)
            and (not has_critical_naturalness_failures)
            and all(bool(value) for value in approved_qc_checks.values())
        )
        strict_failure_tags_allowed = {"wispy_loss_risk"}
        approved_runtime_face_overlap_limit_value = approved_runtime_face_overlap_limit(pitch_value)
        approved_runtime_checks = {
            "approved": approved,
            "face_overlap_ratio": face_overlap_ratio <= approved_runtime_face_overlap_limit_value,
            "naturalness_risk_v1": naturalness_risk <= 0.18,
            "failure_tags": set(failure_tags).issubset(strict_failure_tags_allowed),
        }
        approved_runtime = all(bool(value) for value in approved_runtime_checks.values())
        approved_strict_checks = {
            "approved": approved,
            "naturalness_risk_v1": naturalness_risk <= 0.12,
            "face_overlap_ratio": face_overlap_ratio <= 0.005,
            "alpha_area_ratio": alpha_area <= 0.10,
            "failure_tags": set(failure_tags).issubset(strict_failure_tags_allowed),
        }
        approved_strict = all(bool(value) for value in approved_strict_checks.values())
        quality_status = "rejected" if (has_critical_failures or has_critical_naturalness_failures) else ("approved" if approved else "borderline")

        if approved:
            approved_count += 1
        if approved_runtime:
            approved_runtime_count += 1
        if has_critical_failures or has_critical_naturalness_failures:
            rejected_count += 1

        if args.write_back_metadata:
            metadata["quality_score"] = quality_score
            metadata["edge_score"] = None
            metadata["matte_score"] = quality_score
            metadata["quality_status"] = quality_status
            metadata["approved"] = approved
            metadata["approved_runtime"] = approved_runtime
            metadata["approved_strict"] = approved_strict
            metadata["critical_failure_tags"] = critical_failure_tags_present
            metadata["critical_naturalness_failure_tags_v1"] = critical_naturalness_tags_present
            write_json(resolve_asset_path(asset_root, row["metadata_path"]), metadata)

        index_items.append(
            {
                "asset_id": metadata["asset_id"],
                "pose_key": metadata["pose_key"],
                "image_path": metadata["image_path"],
                "alpha_path": metadata["alpha_path"],
                "hair_mask_path": metadata["hair_mask_path"],
                "face_mask_path": metadata["face_mask_path"],
                "anchors_path": metadata["anchors_path"],
                "metadata_path": row["metadata_path"],
                "yaw_1deg": metadata["yaw_1deg"],
                "pitch_1deg": metadata["pitch_1deg"],
                "roll_1deg": metadata["roll_1deg"],
                "face_ratio": metadata["face_ratio"],
                "hair_width_ratio": metadata["hair_width_ratio"],
                "hair_height_ratio": metadata["hair_height_ratio"],
                "forehead_visible_ratio": metadata["forehead_visible_ratio"],
                "ear_visibility_left": metadata["ear_visibility_left"],
                "ear_visibility_right": metadata["ear_visibility_right"],
                "face_overlap_ratio": face_overlap_ratio,
                "overlap_suppression_ratio": metadata.get("overlap_suppression_ratio"),
                "temple_span_ratio": round(temple_span_ratio, 6),
                "lower_span_ratio": round(lower_span_ratio, 6),
                "neck_span_ratio": round(neck_span_ratio, 6),
                "crown_offset_ratio": round(crown_offset_ratio, 6),
                "hair_area_ratio": round(hair_area, 6),
                "alpha_area_ratio": round(alpha_area, 6),
                "hole_ratio": round(hole_ratio, 6),
                "fringe_fill_ratio": None if fringe_fill_ratio is None else round(float(fringe_fill_ratio), 6),
                "mask_component_count": metadata.get("mask_component_count"),
                "hair_mean_confidence": metadata.get("hair_mean_confidence"),
                "hair_p90_confidence": metadata.get("hair_p90_confidence"),
                "boundary_touches": metadata.get("boundary_touches", {}),
                "failure_tags": failure_tags,
                "critical_failure_tags": critical_failure_tags_present,
                "has_critical_failures": has_critical_failures,
                "naturalness_risk_v1": naturalness_risk,
                "naturalness_failure_tags_v1": naturalness_failure_tags,
                "critical_naturalness_failure_tags_v1": critical_naturalness_tags_present,
                "has_critical_naturalness_failures": has_critical_naturalness_failures,
                "quality_score": quality_score,
                "naturalness_score_v1": metadata.get("naturalness_score_v1"),
                "quality_status": quality_status,
                "approved": approved,
                "approved_runtime": approved_runtime,
                "approved_strict": approved_strict,
                "qc_checks": qc_checks,
                "approved_qc_checks": approved_qc_checks,
                "approved_runtime_face_overlap_limit": approved_runtime_face_overlap_limit_value,
                "approved_runtime_checks": approved_runtime_checks,
                "approved_strict_checks": approved_strict_checks,
            }
        )

    index_path = asset_root / "manifests" / "asset_index_v0.json"
    summary_path = asset_root / "manifests" / "asset_index_summary.json"
    write_json(
        index_path,
        {
            "summary": {
                "total_assets": len(index_items),
                "approved_assets": approved_count,
                "approved_runtime_assets": approved_runtime_count,
                "rejected_assets": rejected_count,
                "failure_tag_counts": dict(sorted(failure_counter.items())),
            },
            "items": index_items,
        },
    )

    hair_area_values = sorted(item["hair_area_ratio"] for item in index_items)
    summary = {
        "asset_root": str(asset_root),
        "total_assets": len(index_items),
        "approved_assets": approved_count,
        "approved_runtime_assets": approved_runtime_count,
        "rejected_assets": rejected_count,
        "approved_ratio": round(approved_count / len(index_items), 6) if index_items else 0.0,
        "approved_runtime_ratio": round(approved_runtime_count / len(index_items), 6) if index_items else 0.0,
        "failure_tag_counts": dict(sorted(failure_counter.items())),
        "hair_area_ratio": {
            "min": hair_area_values[0] if hair_area_values else None,
            "p50": hair_area_values[len(hair_area_values) // 2] if hair_area_values else None,
            "max": hair_area_values[-1] if hair_area_values else None,
        },
    }
    write_json(summary_path, summary)


if __name__ == "__main__":
    main()
