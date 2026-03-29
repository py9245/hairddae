#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import threading
import time
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from cv2_cuda_utils import (
    opencv_cuda_download,
    opencv_cuda_upload,
    opencv_cvt_color,
    opencv_dilate,
    opencv_gaussian_blur,
    opencv_resize,
    opencv_warp_affine,
    opencv_warp_affine_uploaded,
)
from local_demo_paths import read_json, resolve_asset_path, write_json

DEFAULT_RENDERER = "legacy"
AVAILABLE_RENDERERS = ("legacy", "mesh_v1", "mesh_v2", "mesh_v3", "mesh_v4")
MESH_ANCHOR_NAMES = (
    "crown",
    "forehead_center",
    "left_temple",
    "right_temple",
    "left_side",
    "right_side",
    "left_ear_root",
    "right_ear_root",
    "lower_left",
    "lower_right",
    "neck_left",
    "neck_right",
)
MESH_V2_CONTROL_POINT_SPECS: tuple[tuple[str, dict[str, float]], ...] = (
    ("crown", {"crown": 1.0}),
    ("crown_left", {"crown": 0.62, "left_temple": 0.38}),
    ("top_left", {"forehead_center": 0.42, "left_temple": 0.58}),
    ("left_temple", {"left_temple": 1.0}),
    ("left_ear_bridge", {"left_temple": 0.45, "left_ear_root": 0.55}),
    ("left_side", {"left_side": 1.0}),
    ("left_cheek", {"left_side": 0.45, "lower_left": 0.55}),
    ("lower_left", {"lower_left": 1.0}),
    ("lower_center", {"lower_left": 0.5, "lower_right": 0.5}),
    ("lower_right", {"lower_right": 1.0}),
    ("right_cheek", {"right_side": 0.45, "lower_right": 0.55}),
    ("right_side", {"right_side": 1.0}),
    ("right_ear_bridge", {"right_temple": 0.45, "right_ear_root": 0.55}),
    ("right_temple", {"right_temple": 1.0}),
    ("top_right", {"forehead_center": 0.42, "right_temple": 0.58}),
    ("crown_right", {"crown": 0.62, "right_temple": 0.38}),
    ("forehead_center", {"forehead_center": 1.0}),
    ("neck_left", {"neck_left": 1.0}),
    ("neck_center", {"neck_left": 0.5, "neck_right": 0.5}),
    ("neck_right", {"neck_right": 1.0}),
)

_LEGACY_GPU_CACHE_LOCK = threading.Lock()


def _env_bool(name: str, default: bool) -> bool:
    raw_value = str(os.environ.get(name, "")).strip().lower()
    if not raw_value:
        return default
    return raw_value in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw_value = str(os.environ.get(name, "")).strip()
    if not raw_value:
        return float(default)
    try:
        return float(raw_value)
    except ValueError:
        return float(default)


HAIR_TONE_MATCH_ENABLED = _env_bool("INFERENCE_RTC_HAIR_TONE_MATCH_ENABLED", True)
HAIR_TONE_MATCH_STRENGTH = float(np.clip(_env_float("INFERENCE_RTC_HAIR_TONE_MATCH_STRENGTH", 0.68), 0.0, 1.0))
HAIR_TONE_MATCH_GAIN_MIN = float(np.clip(_env_float("INFERENCE_RTC_HAIR_TONE_MATCH_GAIN_MIN", 0.84), 0.5, 1.0))
HAIR_TONE_MATCH_GAIN_MAX = float(np.clip(_env_float("INFERENCE_RTC_HAIR_TONE_MATCH_GAIN_MAX", 1.18), 1.0, 1.6))
HAIR_TONE_MATCH_DELTA_THRESHOLD = float(np.clip(_env_float("INFERENCE_RTC_HAIR_TONE_MATCH_DELTA_THRESHOLD", 0.035), 0.0, 0.2))
ASSET_BUNDLE_CACHE_SIZE = max(8, int(os.environ.get("INFERENCE_RUNTIME_ASSET_BUNDLE_CACHE_SIZE", "64")))
ASSET_EDGE_RISK_CACHE_SIZE = max(32, int(os.environ.get("INFERENCE_RUNTIME_ASSET_EDGE_RISK_CACHE_SIZE", "256")))
PACKED_BUNDLES_ENABLED = _env_bool("INFERENCE_RUNTIME_PACKED_BUNDLES_ENABLED", True)
LEGACY_AUX_ALIGN_ENABLED = _env_bool("INFERENCE_RTC_LEGACY_AUX_ALIGN_ENABLED", False)
LEGACY_AUX_ALIGN_MAX_SHIFT_RATIO = float(
    np.clip(_env_float("INFERENCE_RTC_LEGACY_AUX_ALIGN_MAX_SHIFT_RATIO", 0.028), 0.0, 0.08)
)
LEGACY_AUX_ALIGN_MAX_YSHIFT_RATIO = float(
    np.clip(_env_float("INFERENCE_RTC_LEGACY_AUX_ALIGN_MAX_YSHIFT_RATIO", 0.024), 0.0, 0.08)
)
LEGACY_AUX_ALIGN_MAX_XSCALE_DELTA = float(
    np.clip(_env_float("INFERENCE_RTC_LEGACY_AUX_ALIGN_MAX_XSCALE_DELTA", 0.028), 0.0, 0.08)
)

BUNDLE_PROFILE_FULL = "full"
BUNDLE_PROFILE_LEGACY = "legacy"
BUNDLE_PROFILE_MESH = "mesh"
BUNDLE_PROFILE_EDGE_RISK = "edge_risk"

_BUNDLE_PROFILE_REQUIRED_KEYS: dict[str, frozenset[str]] = {
    BUNDLE_PROFILE_FULL: frozenset(
        {
            "image_path",
            "alpha_path",
            "hair_mask_path",
            "face_mask_path",
            "forehead_mask_path",
            "ear_mask_left_path",
            "ear_mask_right_path",
            "neck_shoulder_mask_path",
            "protect_face_mask_path",
        }
    ),
    BUNDLE_PROFILE_LEGACY: frozenset(
        {
            "image_path",
            "alpha_path",
            "hair_mask_path",
            "face_mask_path",
            "protect_face_mask_path",
        }
    ),
    BUNDLE_PROFILE_MESH: frozenset(
        {
            "image_path",
            "alpha_path",
            "hair_mask_path",
            "face_mask_path",
            "forehead_mask_path",
            "ear_mask_left_path",
            "ear_mask_right_path",
            "neck_shoulder_mask_path",
            "protect_face_mask_path",
        }
    ),
    BUNDLE_PROFILE_EDGE_RISK: frozenset({"alpha_path", "hair_mask_path"}),
}

_PACKED_BUNDLE_FIELDS: dict[str, tuple[str, ...]] = {
    BUNDLE_PROFILE_LEGACY: (
        "image",
        "alpha",
        "hair_mask",
        "face_mask",
        "protect_face_mask",
    ),
    BUNDLE_PROFILE_EDGE_RISK: (
        "alpha",
        "hair_mask",
    ),
}


def _normalize_bundle_profile(profile: str | None) -> str:
    normalized = str(profile or "").strip().lower()
    if normalized == BUNDLE_PROFILE_LEGACY:
        return BUNDLE_PROFILE_LEGACY
    if normalized == BUNDLE_PROFILE_MESH:
        return BUNDLE_PROFILE_MESH
    if normalized == BUNDLE_PROFILE_EDGE_RISK:
        return BUNDLE_PROFILE_EDGE_RISK
    return BUNDLE_PROFILE_FULL


def _packed_bundle_asset_id(metadata: dict[str, Any], metadata_path_str: str) -> str:
    asset_id = str(metadata.get("asset_id") or "").strip()
    if asset_id:
        return asset_id
    return Path(metadata_path_str).stem


def packed_bundle_path(asset_root: Path, asset_id: str, profile: str) -> Path:
    return asset_root / "packed" / profile / f"{asset_id}.npz"


def _load_packed_asset_bundle(
    asset_root: Path,
    metadata_path_str: str,
    metadata: dict[str, Any],
    bundle_profile: str,
) -> dict[str, Any] | None:
    if not PACKED_BUNDLES_ENABLED:
        return None
    if bundle_profile not in _PACKED_BUNDLE_FIELDS:
        return None
    asset_id = _packed_bundle_asset_id(metadata, metadata_path_str)
    packed_path = packed_bundle_path(asset_root, asset_id, bundle_profile)
    if not packed_path.is_file():
        return None
    with np.load(packed_path, allow_pickle=False) as packed:
        anchors_json = packed.get("anchors_json")
        if anchors_json is None:
            return None
        anchors = json.loads(str(np.asarray(anchors_json).item()))
        crop_box = tuple(int(v) for v in np.asarray(packed["crop_box"]).tolist())
        hair_bbox = tuple(int(v) for v in np.asarray(packed["hair_bbox"]).tolist())
        hair_luma_array = packed.get("hair_luma")
        hair_luma = None
        if hair_luma_array is not None:
            raw_hair_luma = float(np.asarray(hair_luma_array).reshape(-1)[0])
            hair_luma = None if not np.isfinite(raw_hair_luma) or raw_hair_luma <= 0.0 else raw_hair_luma
        payload: dict[str, Any] = {
            "metadata": metadata,
            "anchors": anchors,
            "image": None,
            "alpha": None,
            "hair_mask": None,
            "face_mask": None,
            "forehead_mask": None,
            "ear_mask_left": None,
            "ear_mask_right": None,
            "neck_shoulder_mask": None,
            "protect_face_mask": None,
            "hair_bbox": hair_bbox,
            "hair_luma": hair_luma,
            "crop_box": crop_box,
            "image_size": tuple(int(v) for v in np.asarray(packed["image_size"]).tolist()),
            "bundle_profile": bundle_profile,
            "packed_bundle_path": str(packed_path),
            "packed_crop_only": bool(int(np.asarray(packed["packed_crop_only"]).reshape(-1)[0])),
        }
        for field_name in _PACKED_BUNDLE_FIELDS[bundle_profile]:
            payload[field_name] = np.asarray(packed[field_name])
        return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run retrieval + affine hair overlay POC on user frames.")
    parser.add_argument("--asset-root", required=True)
    parser.add_argument("--user-feature-json", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--save-debug", action="store_true")
    parser.add_argument("--output-format", choices=["jpg", "png"], default="jpg")
    parser.add_argument("--jpeg-quality", type=int, default=90)
    parser.add_argument("--renderer", choices=AVAILABLE_RENDERERS, default=DEFAULT_RENDERER)
    parser.add_argument("--skip-image-write", action="store_true")
    return parser.parse_args()


def normalize_renderer_name(renderer_name: str | None) -> str:
    normalized = str(renderer_name or "").strip().lower()
    if normalized == "mesh_v4":
        return "mesh_v4"
    if normalized == "mesh_v3":
        return "mesh_v3"
    if normalized == "mesh_v2":
        return "mesh_v2"
    if normalized == "mesh_v1":
        return "mesh_v1"
    return DEFAULT_RENDERER


def _masked_mean_luma(image_bgr: np.ndarray, mask: np.ndarray | None) -> float | None:
    if image_bgr.ndim != 3 or image_bgr.shape[2] != 3 or mask is None:
        return None
    if mask.ndim != 2 or mask.size == 0:
        return None
    if mask.shape[:2] != image_bgr.shape[:2]:
        return None
    tone_mask = np.where(mask >= 24, np.uint8(255), np.uint8(0))
    active_pixels = int(np.count_nonzero(tone_mask))
    if active_pixels < max(32, int(round(mask.size * 0.006))):
        return None
    luma = opencv_cvt_color(image_bgr, cv2.COLOR_BGR2GRAY, min_pixels=8_192)
    mean_luma = float(cv2.mean(luma, mask=tone_mask)[0])
    if not np.isfinite(mean_luma) or mean_luma <= 1.0:
        return None
    return round(mean_luma, 3)


def resolve_hair_tone_gain(user_row: dict[str, Any], asset_hair_luma: float | None) -> float | None:
    if not HAIR_TONE_MATCH_ENABLED or asset_hair_luma is None:
        return None
    tone_payload = user_row.get("_hair_tone")
    if not isinstance(tone_payload, dict):
        return None
    user_hair_luma = tone_payload.get("mean_luma")
    coverage = float(tone_payload.get("coverage") or 0.0)
    if coverage < 0.008:
        return None
    try:
        user_luma = float(user_hair_luma)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(user_luma) or user_luma <= 1.0:
        return None

    raw_gain = user_luma / max(float(asset_hair_luma), 1.0)
    clamped_gain = float(np.clip(raw_gain, HAIR_TONE_MATCH_GAIN_MIN, HAIR_TONE_MATCH_GAIN_MAX))
    effective_gain = 1.0 + (clamped_gain - 1.0) * HAIR_TONE_MATCH_STRENGTH
    if abs(effective_gain - 1.0) <= HAIR_TONE_MATCH_DELTA_THRESHOLD:
        return None
    return round(effective_gain, 4)


def apply_masked_rgb_gain(
    image_bgr: np.ndarray,
    mask: np.ndarray | None,
    rgb_gain: float | None,
) -> np.ndarray:
    if rgb_gain is None or abs(float(rgb_gain) - 1.0) <= HAIR_TONE_MATCH_DELTA_THRESHOLD:
        return image_bgr
    if image_bgr.ndim != 3 or image_bgr.shape[2] != 3 or mask is None:
        return image_bgr
    if mask.ndim != 2 or mask.shape[:2] != image_bgr.shape[:2]:
        return image_bgr

    tone_mask = np.where(mask >= 8, np.uint8(255), np.uint8(0))
    if int(np.count_nonzero(tone_mask)) < 24:
        return image_bgr

    scaled = cv2.convertScaleAbs(image_bgr, alpha=float(rgb_gain), beta=0.0)
    adjusted = image_bgr.copy()
    cv2.copyTo(scaled, tone_mask, adjusted)
    return adjusted

def point_distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    return float(np.hypot(float(a["x"]) - float(b["x"]), float(a["y"]) - float(b["y"])))


def derive_geom_from_feature(item: dict[str, Any]) -> dict[str, float]:
    anchors = item["anchors"]
    bbox = item["face_bbox"]
    width = max(1.0, bbox["w"])
    height = max(1.0, bbox["h"])
    return {
        "temple_span_norm": point_distance(anchors["left_temple"], anchors["right_temple"]) / width,
        "lower_span_norm": point_distance(anchors["lower_left"], anchors["lower_right"]) / width,
        "crown_offset_norm": abs(float(anchors["forehead_center"]["y"]) - float(anchors["crown"]["y"])) / height,
        "face_ratio": float(item["face_ratio"]),
    }


def pose_distance(user_pose: dict[str, Any], asset_row: dict[str, Any]) -> float:
    return round(
        3.2 * abs(user_pose["yaw_1deg"] - asset_row["yaw_1deg"])
        + 4.8 * abs(user_pose["pitch_1deg"] - asset_row["pitch_1deg"])
        + 3.4 * abs(user_pose["roll_1deg"] - asset_row["roll_1deg"]),
        6,
    )


def retrieval_score(user_row: dict[str, Any], asset_row: dict[str, Any]) -> float:
    user_pose = user_row["pose"]
    yaw_gap = abs(user_pose["yaw_1deg"] - asset_row["yaw_1deg"])
    pitch_gap = abs(user_pose["pitch_1deg"] - asset_row["pitch_1deg"])
    roll_gap = abs(user_pose["roll_1deg"] - asset_row["roll_1deg"])
    side_factor = min(1.0, abs(float(user_pose["yaw_1deg"])) / 30.0)
    pose_score = (
        (3.2 + 1.4 * side_factor) * yaw_gap
        + max(2.8, 4.8 - 1.6 * side_factor) * pitch_gap
        + max(2.0, 3.4 - 0.45 * side_factor) * roll_gap
    )
    user_geom = user_row["_geom"]
    geom_score = (
        (24.0 * (1.0 - 0.65 * side_factor)) * abs(user_geom["temple_span_norm"] - asset_row["temple_span_ratio"])
        + (16.0 * (1.0 - 0.55 * side_factor)) * abs(user_geom["lower_span_norm"] - asset_row["lower_span_ratio"])
        + (12.0 * (1.0 - 0.35 * side_factor)) * abs(user_geom["crown_offset_norm"] - asset_row["crown_offset_ratio"])
        + (12.0 * (1.0 - 0.50 * side_factor)) * abs(user_geom["face_ratio"] - asset_row["face_ratio"])
    )
    return round(pose_score + geom_score, 6)


def asset_rank_score(user_row: dict[str, Any], asset_row: dict[str, Any]) -> float:
    user_pose = user_row["pose"]
    user_pitch = float(user_pose.get("pitch_1deg", 0.0))
    user_yaw = float(user_pose.get("yaw_1deg", 0.0))
    down_pitch_factor = float(np.clip((user_pitch - 14.0) / 10.0, 0.0, 1.0))
    up_pitch_factor = float(np.clip((-user_pitch - 8.0) / 10.0, 0.0, 1.0))
    yaw_factor = float(np.clip((abs(user_yaw) - 8.0) / 20.0, 0.0, 1.0))
    quality_score = float(asset_row.get("quality_score") or 0.0)
    hair_confidence = float(asset_row.get("hair_mean_confidence") or 0.0)
    failure_penalty = 0.6 * len(asset_row.get("failure_tags") or [])
    naturalness_risk = float(asset_row.get("naturalness_risk_v1") or 0.0)
    naturalness_failure_tags = asset_row.get("naturalness_failure_tags_v1") or []
    naturalness_failure_penalty = 0.5 * len(naturalness_failure_tags)
    face_overlap_ratio = float(asset_row.get("face_overlap_ratio") or 0.0)
    quality_status = str(asset_row.get("quality_status") or "")
    approved_runtime_bonus = 0.7 if asset_row.get("approved_runtime") else 0.0
    downward_face_overlap_penalty = 0.0
    if down_pitch_factor > 0.0:
        downward_face_overlap_penalty += 720.0 * face_overlap_ratio * down_pitch_factor
        downward_face_overlap_penalty += 18.0 * naturalness_risk * down_pitch_factor
        if "face_skin_overlap_risk" in naturalness_failure_tags:
            downward_face_overlap_penalty += 6.0 * down_pitch_factor
        if "downward_face_cover_risk" in naturalness_failure_tags:
            downward_face_overlap_penalty += 12.0 * down_pitch_factor
        if quality_status != "approved" and user_pitch >= 18.0:
            downward_face_overlap_penalty += 3.5 * down_pitch_factor
    approved_bonus = 1.0 if asset_row.get("approved") else 0.0
    runtime_fit_context = user_row.get("_runtime_fit_context") or {}
    runtime_fit_penalty = 0.0
    if runtime_fit_context.get("enabled"):
        user_ear_left = float(runtime_fit_context.get("ear_left_area_ratio") or 0.0)
        user_ear_right = float(runtime_fit_context.get("ear_right_area_ratio") or 0.0)
        asset_ear_left = float(asset_row.get("ear_visibility_left") or 0.0)
        asset_ear_right = float(asset_row.get("ear_visibility_right") or 0.0)
        if user_yaw >= 0.0:
            near_ear_penalty = abs(user_ear_right - asset_ear_right)
            far_ear_penalty = abs(user_ear_left - asset_ear_left)
        else:
            near_ear_penalty = abs(user_ear_left - asset_ear_left)
            far_ear_penalty = abs(user_ear_right - asset_ear_right)
        runtime_fit_penalty += 88.0 * yaw_factor * (1.15 * near_ear_penalty + 0.75 * far_ear_penalty)

        user_forehead_ratio = float(runtime_fit_context.get("forehead_area_ratio") or 0.0)
        asset_forehead_ratio = float(asset_row.get("forehead_visible_ratio") or 0.0)
        runtime_fit_penalty += 96.0 * (0.35 + up_pitch_factor + 0.40 * down_pitch_factor) * abs(
            user_forehead_ratio - asset_forehead_ratio
        )

        user_head_ratio = float(runtime_fit_context.get("head_area_ratio") or 0.0)
        asset_alpha_ratio = float(asset_row.get("alpha_area_ratio") or 0.0)
        if user_head_ratio > 0.0:
            shell_excess = max(0.0, asset_alpha_ratio - user_head_ratio * (1.04 + 0.16 * yaw_factor))
            runtime_fit_penalty += 84.0 * (0.35 + yaw_factor) * shell_excess

        user_neck_ratio = float(runtime_fit_context.get("neck_area_ratio") or 0.0)
        asset_hair_height_ratio = float(asset_row.get("hair_height_ratio") or 0.0)
        expected_neck_cover = float(np.clip((asset_hair_height_ratio - 0.25) * 0.22, 0.0, 0.06))
        runtime_fit_penalty += 72.0 * (0.25 + yaw_factor + 0.55 * down_pitch_factor) * abs(
            user_neck_ratio - expected_neck_cover
        )

        protect_face_ratio = float(runtime_fit_context.get("protect_face_area_ratio") or 0.0)
        runtime_fit_penalty += 55.0 * (0.35 + yaw_factor + down_pitch_factor) * max(
            0.0,
            face_overlap_ratio - protect_face_ratio * 0.16,
        )
    return round(
        retrieval_score(user_row, asset_row)
        - 1.8 * quality_score
        - 0.8 * hair_confidence
        - approved_bonus
        - approved_runtime_bonus
        + failure_penalty
        + 4.5 * naturalness_risk
        + naturalness_failure_penalty,
        6,
    ) + round(
        downward_face_overlap_penalty + runtime_fit_penalty,
        6,
    )


def asset_preference_key(asset_row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        0 if asset_row.get("approved") else 1,
        -float(asset_row.get("quality_score") or 0.0),
        float(asset_row.get("naturalness_risk_v1") or 0.0),
        len(asset_row.get("naturalness_failure_tags_v1") or []),
        len(asset_row.get("critical_failure_tags") or []),
        len(asset_row.get("failure_tags") or []),
        -float(asset_row.get("hair_mean_confidence") or 0.0),
        asset_row["asset_id"],
    )


def build_runtime_asset_rows(asset_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_pose_key: dict[str, dict[str, Any]] = {}
    for row in asset_rows:
        current = by_pose_key.get(row["pose_key"])
        if current is None or asset_preference_key(row) < asset_preference_key(current):
            by_pose_key[row["pose_key"]] = row
    return sorted(
        by_pose_key.values(),
        key=lambda row: (row["pitch_1deg"], row["yaw_1deg"], row["roll_1deg"], row["asset_id"]),
    )


def select_candidate_assets(
    user_row: dict[str, Any],
    asset_rows: list[dict[str, Any]],
    limit: int = 256,
) -> list[dict[str, Any]]:
    user_pose = user_row["pose"]
    windows = [
        (2, 2, 2),
        (4, 3, 3),
        (6, 5, 4),
        (8, 7, 5),
        (12, 10, 6),
    ]
    minimum_candidates = min(limit, 18)

    for yaw_tol, pitch_tol, roll_tol in windows:
        candidates = [
            row
            for row in asset_rows
            if abs(user_pose["yaw_1deg"] - row["yaw_1deg"]) <= yaw_tol
            and abs(user_pose["pitch_1deg"] - row["pitch_1deg"]) <= pitch_tol
            and abs(user_pose["roll_1deg"] - row["roll_1deg"]) <= roll_tol
        ]
        if len(candidates) >= minimum_candidates:
            candidates.sort(
                key=lambda row: (
                    pose_distance(user_pose, row),
                    asset_rank_score(user_row, row),
                    -float(row.get("quality_score") or 0.0),
                    row["asset_id"],
                )
            )
            return candidates[:limit]

    ranked = sorted(
        asset_rows,
        key=lambda row: (
            pose_distance(user_pose, row),
            asset_rank_score(user_row, row),
            -float(row.get("quality_score") or 0.0),
            row["asset_id"],
        ),
    )
    return ranked[:limit]


def select_best_assets(
    user_row: dict[str, Any],
    asset_rows: list[dict[str, Any]],
    limit: int = 3,
    candidate_limit: int = 256,
) -> list[tuple[dict[str, Any], float]]:
    user_row["_geom"] = derive_geom_from_feature(user_row)
    candidates = select_candidate_assets(user_row, asset_rows, limit=max(limit * 8, candidate_limit))
    ranked_rows = sorted(
        candidates,
        key=lambda row: (
            asset_rank_score(user_row, row),
            pose_distance(user_row["pose"], row),
            -float(row.get("quality_score") or 0.0),
            row["asset_id"],
        ),
    )
    ranked_assets = [(row, asset_rank_score(user_row, row)) for row in ranked_rows[:limit]]
    if ranked_assets:
        user_row["_best_score"] = ranked_assets[0][1]
    return ranked_assets


def protect_face_mask(height: int, width: int, bbox: dict[str, Any]) -> np.ndarray:
    mask = np.zeros((height, width), dtype=np.uint8)
    center = (int(round(bbox["x"] + bbox["w"] * 0.5)), int(round(bbox["y"] + bbox["h"] * 0.60)))
    axes = (int(round(bbox["w"] * 0.34)), int(round(bbox["h"] * 0.38)))
    cv2.ellipse(mask, center, axes, 0, 0, 360, 255, -1)
    return opencv_gaussian_blur(mask, (0, 0), sigma_x=5.0, sigma_y=5.0, min_pixels=24_000)


def hair_bbox_from_mask(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.where(mask > 0)
    if xs.size == 0 or ys.size == 0:
        height, width = mask.shape[:2]
        return (0, 0, width, height)
    x0 = int(xs.min())
    y0 = int(ys.min())
    x1 = int(xs.max()) + 1
    y1 = int(ys.max()) + 1
    return (x0, y0, x1, y1)


def clamp_roi(x0: int, y0: int, x1: int, y1: int, width: int, height: int) -> tuple[int, int, int, int] | None:
    x0 = max(0, min(width, x0))
    y0 = max(0, min(height, y0))
    x1 = max(0, min(width, x1))
    y1 = max(0, min(height, y1))
    if x1 <= x0 or y1 <= y0:
        return None
    return (x0, y0, x1, y1)


def transform_points(matrix: np.ndarray, points: np.ndarray) -> np.ndarray:
    return cv2.transform(points.reshape(-1, 1, 2).astype(np.float32), matrix).reshape(-1, 2)


def roi_affine_from_crop(
    matrix: np.ndarray,
    src_x0: int,
    src_y0: int,
    dst_x0: int,
    dst_y0: int,
) -> np.ndarray:
    roi_matrix = matrix.copy()
    linear = matrix[:, :2]
    offset = linear @ np.array([src_x0, src_y0], dtype=np.float32) + matrix[:, 2] - np.array([dst_x0, dst_y0], dtype=np.float32)
    roi_matrix[:, 2] = offset
    return roi_matrix


def expanded_hair_crop(
    hair_bbox: tuple[int, int, int, int],
    image_width: int,
    image_height: int,
) -> tuple[int, int, int, int]:
    src_x0, src_y0, src_x1, src_y1 = hair_bbox
    bbox_width = max(1, src_x1 - src_x0)
    bbox_height = max(1, src_y1 - src_y0)
    side_margin = max(24, int(round(bbox_width * 0.10)))
    top_margin = max(30, int(round(bbox_height * 0.18)))
    bottom_margin = max(34, int(round(bbox_height * 0.20)))
    return (
        max(0, src_x0 - side_margin),
        max(0, src_y0 - top_margin),
        min(image_width, src_x1 + side_margin),
        min(image_height, src_y1 + bottom_margin),
    )


def render_roi_margin(span_width: int, span_height: int) -> int:
    return max(18, int(round(max(span_width, span_height) * 0.06)))


def clamp_point_to_crop(
    point: tuple[float, float],
    crop_box: tuple[int, int, int, int],
) -> tuple[float, float]:
    x0, y0, x1, y1 = crop_box
    local_x = float(point[0]) - float(x0)
    local_y = float(point[1]) - float(y0)
    return (
        float(np.clip(local_x, 0.0, max(0.0, float(x1 - x0 - 1)))),
        float(np.clip(local_y, 0.0, max(0.0, float(y1 - y0 - 1)))),
    )


def weighted_anchor_point(
    anchors: dict[str, Any],
    weights: dict[str, float],
) -> tuple[float, float]:
    total = max(1e-6, sum(float(weight) for weight in weights.values()))
    x_value = sum(float(anchors[name]["x"]) * float(weight) for name, weight in weights.items()) / total
    y_value = sum(float(anchors[name]["y"]) * float(weight) for name, weight in weights.items()) / total
    return (x_value, y_value)


def build_mesh_boundary_points(crop_width: int, crop_height: int) -> list[tuple[float, float]]:
    max_x = max(0.0, float(crop_width - 1))
    max_y = max(0.0, float(crop_height - 1))
    return [
        (0.0, 0.0),
        (max_x * 0.5, 0.0),
        (max_x, 0.0),
        (max_x, max_y * 0.30),
        (max_x, max_y * 0.62),
        (max_x, max_y),
        (max_x * 0.5, max_y),
        (0.0, max_y),
        (0.0, max_y * 0.62),
        (0.0, max_y * 0.30),
    ]


def build_dense_mesh_boundary_points(crop_width: int, crop_height: int) -> list[tuple[float, float]]:
    max_x = max(0.0, float(crop_width - 1))
    max_y = max(0.0, float(crop_height - 1))
    return [
        (0.0, 0.0),
        (max_x * 0.25, 0.0),
        (max_x * 0.5, 0.0),
        (max_x * 0.75, 0.0),
        (max_x, 0.0),
        (max_x, max_y * 0.22),
        (max_x, max_y * 0.48),
        (max_x, max_y * 0.76),
        (max_x, max_y),
        (max_x * 0.75, max_y),
        (max_x * 0.5, max_y),
        (max_x * 0.25, max_y),
        (0.0, max_y),
        (0.0, max_y * 0.76),
        (0.0, max_y * 0.48),
        (0.0, max_y * 0.22),
    ]


def build_mesh_source_points(
    anchors: dict[str, Any],
    crop_box: tuple[int, int, int, int],
) -> list[tuple[float, float]]:
    x0, y0, x1, y1 = crop_box
    crop_width = max(1, x1 - x0)
    crop_height = max(1, y1 - y0)
    source_points = [
        clamp_point_to_crop((float(anchors[name]["x"]), float(anchors[name]["y"])), crop_box)
        for name in MESH_ANCHOR_NAMES
    ]
    source_points.extend(build_mesh_boundary_points(crop_width, crop_height))
    return source_points


def build_dense_mesh_source_points(
    anchors: dict[str, Any],
    crop_box: tuple[int, int, int, int],
) -> list[tuple[float, float]]:
    x0, y0, x1, y1 = crop_box
    crop_width = max(1, x1 - x0)
    crop_height = max(1, y1 - y0)
    source_points = [
        clamp_point_to_crop(weighted_anchor_point(anchors, weights), crop_box)
        for _, weights in MESH_V2_CONTROL_POINT_SPECS
    ]
    source_points.extend(build_dense_mesh_boundary_points(crop_width, crop_height))
    return source_points


def build_mesh_triangles(
    source_points: list[tuple[float, float]],
    crop_width: int,
    crop_height: int,
) -> list[tuple[int, int, int]]:
    rect = (0, 0, max(1, int(crop_width)), max(1, int(crop_height)))
    subdiv = cv2.Subdiv2D(rect)
    for x_value, y_value in source_points:
        px = float(np.clip(x_value, 0.0, max(0.0, float(crop_width - 1))))
        py = float(np.clip(y_value, 0.0, max(0.0, float(crop_height - 1))))
        try:
            subdiv.insert((px, py))
        except cv2.error:
            continue

    triangles: list[tuple[int, int, int]] = []
    seen: set[tuple[int, int, int]] = set()
    for triangle in subdiv.getTriangleList():
        coords = [
            (float(triangle[0]), float(triangle[1])),
            (float(triangle[2]), float(triangle[3])),
            (float(triangle[4]), float(triangle[5])),
        ]
        if any(
            x_value < -0.5 or y_value < -0.5 or x_value > crop_width - 0.5 or y_value > crop_height - 0.5
            for x_value, y_value in coords
        ):
            continue

        indices: list[int] = []
        for x_value, y_value in coords:
            best_index = min(
                range(len(source_points)),
                key=lambda idx: (source_points[idx][0] - x_value) ** 2 + (source_points[idx][1] - y_value) ** 2,
            )
            best_distance = (source_points[best_index][0] - x_value) ** 2 + (source_points[best_index][1] - y_value) ** 2
            if best_distance > 1.25:
                indices = []
                break
            indices.append(best_index)
        if len(indices) != 3 or len(set(indices)) != 3:
            continue
        triangle_key = tuple(sorted(indices))
        if triangle_key in seen:
            continue
        seen.add(triangle_key)
        triangles.append(tuple(indices))
    return triangles


def warp_mesh_layer(
    source_layer: np.ndarray,
    source_points: list[tuple[float, float]],
    destination_points: list[tuple[float, float]],
    triangles: list[tuple[int, int, int]],
    output_size: tuple[int, int],
    interpolation: int,
) -> np.ndarray:
    output_width, output_height = output_size
    if source_layer.ndim == 2:
        output = np.zeros((output_height, output_width), dtype=np.float32)
    else:
        output = np.zeros((output_height, output_width, source_layer.shape[2]), dtype=np.float32)

    for i0, i1, i2 in triangles:
        src_triangle = np.float32([source_points[i0], source_points[i1], source_points[i2]])
        dst_triangle = np.float32([destination_points[i0], destination_points[i1], destination_points[i2]])

        src_rect = cv2.boundingRect(src_triangle)
        dst_rect = cv2.boundingRect(dst_triangle)
        if src_rect[2] <= 0 or src_rect[3] <= 0 or dst_rect[2] <= 0 or dst_rect[3] <= 0:
            continue
        if dst_rect[0] >= output_width or dst_rect[1] >= output_height or dst_rect[0] + dst_rect[2] <= 0 or dst_rect[1] + dst_rect[3] <= 0:
            continue

        src_x, src_y, src_w, src_h = src_rect
        dst_x, dst_y, dst_w, dst_h = dst_rect
        source_patch = source_layer[src_y : src_y + src_h, src_x : src_x + src_w]
        if source_patch.size == 0:
            continue

        src_triangle_local = src_triangle - np.array([src_x, src_y], dtype=np.float32)
        dst_triangle_local = dst_triangle - np.array([dst_x, dst_y], dtype=np.float32)
        warp_matrix = cv2.getAffineTransform(src_triangle_local, dst_triangle_local)
        warped_patch = opencv_warp_affine(
            source_patch,
            warp_matrix,
            (dst_w, dst_h),
            flags=interpolation,
            borderMode=cv2.BORDER_REFLECT_101,
        )

        triangle_mask = np.zeros((dst_h, dst_w), dtype=np.float32)
        cv2.fillConvexPoly(triangle_mask, np.int32(np.round(dst_triangle_local)), 1.0, lineType=cv2.LINE_AA)

        dst_x0 = max(0, dst_x)
        dst_y0 = max(0, dst_y)
        dst_x1 = min(output_width, dst_x + dst_w)
        dst_y1 = min(output_height, dst_y + dst_h)
        if dst_x1 <= dst_x0 or dst_y1 <= dst_y0:
            continue

        patch_x0 = dst_x0 - dst_x
        patch_y0 = dst_y0 - dst_y
        patch_x1 = patch_x0 + (dst_x1 - dst_x0)
        patch_y1 = patch_y0 + (dst_y1 - dst_y0)

        clipped_mask = triangle_mask[patch_y0:patch_y1, patch_x0:patch_x1]
        clipped_patch = warped_patch[patch_y0:patch_y1, patch_x0:patch_x1]
        target_view = output[dst_y0:dst_y1, dst_x0:dst_x1]
        if output.ndim == 2:
            output[dst_y0:dst_y1, dst_x0:dst_x1] = target_view * (1.0 - clipped_mask) + clipped_patch.astype(np.float32) * clipped_mask
        else:
            mask_3d = clipped_mask[..., None]
            output[dst_y0:dst_y1, dst_x0:dst_x1] = target_view * (1.0 - mask_3d) + clipped_patch.astype(np.float32) * mask_3d

    return output


def triangle_area(
    points: list[tuple[float, float]],
    i0: int,
    i1: int,
    i2: int,
) -> float:
    x0, y0 = points[i0]
    x1, y1 = points[i1]
    x2, y2 = points[i2]
    return abs((x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)) * 0.5


def mesh_distortion_metrics(
    source_points: list[tuple[float, float]],
    destination_points: list[tuple[float, float]],
    triangles: list[tuple[int, int, int]],
) -> dict[str, float]:
    area_ratios: list[float] = []
    collapsed_count = 0
    for i0, i1, i2 in triangles:
        src_area = triangle_area(source_points, i0, i1, i2)
        dst_area = triangle_area(destination_points, i0, i1, i2)
        if src_area < 1.0 or dst_area < 1.0:
            collapsed_count += 1
            continue
        area_ratios.append(dst_area / src_area)

    if not area_ratios:
        return {
            "triangle_count": 0.0,
            "p90_ratio": 999.0,
            "max_ratio": 999.0,
            "extreme_fraction": 1.0,
            "collapsed_fraction": 1.0,
        }

    ratios = np.array(area_ratios, dtype=np.float32)
    extreme_fraction = float(np.mean((ratios < 0.22) | (ratios > 5.4)))
    collapsed_fraction = float(collapsed_count / max(1, len(triangles)))
    return {
        "triangle_count": float(len(area_ratios)),
        "p90_ratio": float(np.percentile(ratios, 90)),
        "max_ratio": float(np.max(ratios)),
        "extreme_fraction": extreme_fraction,
        "collapsed_fraction": collapsed_fraction,
    }


def output_codec_params(output_format: str, jpeg_quality: int) -> list[int]:
    if output_format == "jpg":
        return [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality]
    return []


def output_suffix(output_format: str) -> str:
    return ".jpg" if output_format == "jpg" else ".png"


def estimate_transform(src_anchors: dict[str, Any], dst_anchors: dict[str, Any]) -> np.ndarray:
    src_pts = np.float32(
        [
            [src_anchors["left_temple"]["x"], src_anchors["left_temple"]["y"]],
            [src_anchors["right_temple"]["x"], src_anchors["right_temple"]["y"]],
            [src_anchors["forehead_center"]["x"], src_anchors["forehead_center"]["y"]],
            [src_anchors["crown"]["x"], src_anchors["crown"]["y"]],
        ]
    )
    dst_pts = np.float32(
        [
            [dst_anchors["left_temple"]["x"], dst_anchors["left_temple"]["y"]],
            [dst_anchors["right_temple"]["x"], dst_anchors["right_temple"]["y"]],
            [dst_anchors["forehead_center"]["x"], dst_anchors["forehead_center"]["y"]],
            [dst_anchors["crown"]["x"], dst_anchors["crown"]["y"]],
        ]
    )
    matrix, _ = cv2.estimateAffinePartial2D(src_pts, dst_pts, method=cv2.LMEDS)
    if matrix is not None:
        return matrix
    return cv2.getAffineTransform(src_pts[:3], dst_pts[:3])


def _anchor_xy_array(anchors: dict[str, Any], name: str) -> np.ndarray | None:
    payload = anchors.get(name)
    if not isinstance(payload, dict):
        return None
    try:
        return np.array([float(payload["x"]), float(payload["y"])], dtype=np.float32)
    except (KeyError, TypeError, ValueError):
        return None


def _x_scaled_affine_about_pivot(
    matrix: np.ndarray,
    scale_x: float,
    pivot: tuple[float, float],
) -> np.ndarray:
    if abs(scale_x - 1.0) < 1e-4:
        return matrix
    pivot_x, pivot_y = pivot
    scale_matrix = np.array(
        [
            [float(scale_x), 0.0, (1.0 - float(scale_x)) * float(pivot_x)],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )
    matrix_3x3 = np.vstack([matrix.astype(np.float32), np.array([0.0, 0.0, 1.0], dtype=np.float32)])
    return (scale_matrix @ matrix_3x3)[:2, :]


def _translated_affine(
    matrix: np.ndarray,
    shift_x: float,
    shift_y: float,
) -> np.ndarray:
    if abs(shift_x) < 1e-4 and abs(shift_y) < 1e-4:
        return matrix
    translated = np.array(matrix, copy=True, dtype=np.float32)
    translated[0, 2] += float(shift_x)
    translated[1, 2] += float(shift_y)
    return translated


def _refine_legacy_transform_with_aux_anchors(
    matrix: np.ndarray,
    src_anchors: dict[str, Any],
    dst_anchors: dict[str, Any],
    *,
    face_bbox: dict[str, Any] | None,
    pose: dict[str, Any] | None,
) -> tuple[np.ndarray, dict[str, float] | None]:
    if not LEGACY_AUX_ALIGN_ENABLED:
        return matrix, None
    if not isinstance(face_bbox, dict):
        return matrix, None

    try:
        yaw_abs = abs(float((pose or {}).get("yaw_1deg", 0.0)))
        roll_abs = abs(float((pose or {}).get("roll_1deg", 0.0)))
    except (TypeError, ValueError):
        yaw_abs = 0.0
        roll_abs = 0.0
    if yaw_abs > 18.0 or roll_abs > 12.0:
        return matrix, None

    src_left_ear = _anchor_xy_array(src_anchors, "left_ear_root")
    src_right_ear = _anchor_xy_array(src_anchors, "right_ear_root")
    src_crown = _anchor_xy_array(src_anchors, "crown")
    dst_left_ear = _anchor_xy_array(dst_anchors, "left_ear_root")
    dst_right_ear = _anchor_xy_array(dst_anchors, "right_ear_root")
    dst_crown = _anchor_xy_array(dst_anchors, "crown")
    if (
        src_left_ear is None
        or src_right_ear is None
        or src_crown is None
        or dst_left_ear is None
        or dst_right_ear is None
        or dst_crown is None
    ):
        return matrix, None

    transformed = transform_points(
        matrix,
        np.vstack([src_left_ear, src_right_ear, src_crown]).astype(np.float32),
    )
    transformed_left_ear = transformed[0]
    transformed_right_ear = transformed[1]
    transformed_crown = transformed[2]

    dst_ear_center = (dst_left_ear + dst_right_ear) * 0.5
    transformed_ear_center = (transformed_left_ear + transformed_right_ear) * 0.5
    dst_ear_span = max(1.0, float(abs(dst_right_ear[0] - dst_left_ear[0])))
    transformed_ear_span = max(1.0, float(abs(transformed_right_ear[0] - transformed_left_ear[0])))
    face_width = max(
        1.0,
        float(face_bbox.get("w", 0.0)) or dst_ear_span,
    )
    face_height = max(
        1.0,
        float(face_bbox.get("h", 0.0))
        or abs(float(dst_crown[1]) - float((dst_left_ear[1] + dst_right_ear[1]) * 0.5)),
    )

    raw_scale_x = dst_ear_span / transformed_ear_span
    scale_x = float(
        np.clip(
            raw_scale_x,
            1.0 - LEGACY_AUX_ALIGN_MAX_XSCALE_DELTA,
            1.0 + LEGACY_AUX_ALIGN_MAX_XSCALE_DELTA,
        )
    )
    refined = _x_scaled_affine_about_pivot(
        matrix,
        scale_x,
        (float(dst_ear_center[0]), float(dst_crown[1])),
    )

    transformed_after_scale = transform_points(
        refined,
        np.vstack([src_left_ear, src_right_ear, src_crown]).astype(np.float32),
    )
    scaled_ear_center = (transformed_after_scale[0] + transformed_after_scale[1]) * 0.5
    scaled_crown = transformed_after_scale[2]

    raw_shift_x = 0.88 * float(dst_ear_center[0] - scaled_ear_center[0]) + 0.12 * float(dst_crown[0] - scaled_crown[0])
    raw_shift_y = 0.72 * float(dst_crown[1] - scaled_crown[1]) + 0.28 * float(dst_ear_center[1] - scaled_ear_center[1])
    max_shift_x = face_width * LEGACY_AUX_ALIGN_MAX_SHIFT_RATIO
    max_shift_y = face_height * LEGACY_AUX_ALIGN_MAX_YSHIFT_RATIO
    shift_x = float(np.clip(raw_shift_x, -max_shift_x, max_shift_x))
    shift_y = float(np.clip(raw_shift_y, -max_shift_y, max_shift_y))
    refined = _translated_affine(refined, shift_x, shift_y)

    return refined, {
        "aux_scale_x": round(float(scale_x), 5),
        "aux_shift_x": round(float(shift_x), 3),
        "aux_shift_y": round(float(shift_y), 3),
    }


def _synthesize_full_frame_from_hair_rgba(
    hair_rgba: np.ndarray,
    *,
    bbox: dict[str, Any] | None,
    image_size: dict[str, Any] | None,
    path_key: str,
) -> np.ndarray | None:
    if hair_rgba.ndim != 3:
        return None
    if path_key == "image_path" and hair_rgba.shape[2] < 3:
        return None
    if path_key == "alpha_path" and hair_rgba.shape[2] < 4:
        return None
    if not isinstance(bbox, dict) or not isinstance(image_size, dict):
        return None

    canvas_width = int(image_size.get("width") or 0)
    canvas_height = int(image_size.get("height") or 0)
    bbox_x = int(bbox.get("x") or 0)
    bbox_y = int(bbox.get("y") or 0)
    bbox_w = int(bbox.get("w") or 0)
    bbox_h = int(bbox.get("h") or 0)
    if canvas_width <= 0 or canvas_height <= 0 or bbox_w <= 0 or bbox_h <= 0:
        return None

    if path_key == "image_path":
        crop = hair_rgba[:, :, :3]
        if crop.shape[:2] != (bbox_h, bbox_w):
            crop = opencv_resize(crop, (bbox_w, bbox_h), interpolation=cv2.INTER_LINEAR, min_pixels=8_192)
        canvas = np.zeros((canvas_height, canvas_width, 3), dtype=np.uint8)
    else:
        crop = hair_rgba[:, :, 3]
        if crop.shape[:2] != (bbox_h, bbox_w):
            crop = opencv_resize(crop, (bbox_w, bbox_h), interpolation=cv2.INTER_LINEAR, min_pixels=8_192)
        canvas = np.zeros((canvas_height, canvas_width), dtype=np.uint8)

    dst_x0 = max(0, bbox_x)
    dst_y0 = max(0, bbox_y)
    dst_x1 = min(canvas_width, bbox_x + bbox_w)
    dst_y1 = min(canvas_height, bbox_y + bbox_h)
    if dst_x1 <= dst_x0 or dst_y1 <= dst_y0:
        return None

    src_x0 = dst_x0 - bbox_x
    src_y0 = dst_y0 - bbox_y
    src_x1 = src_x0 + (dst_x1 - dst_x0)
    src_y1 = src_y0 + (dst_y1 - dst_y0)
    canvas[dst_y0:dst_y1, dst_x0:dst_x1] = crop[src_y0:src_y1, src_x0:src_x1]
    return canvas


@lru_cache(maxsize=ASSET_BUNDLE_CACHE_SIZE)
def load_asset_bundle(
    asset_root_str: str,
    metadata_path_str: str,
    profile: str = BUNDLE_PROFILE_FULL,
) -> dict[str, Any]:
    asset_root = Path(asset_root_str)
    bundle_profile = _normalize_bundle_profile(profile)
    required_keys = _BUNDLE_PROFILE_REQUIRED_KEYS[bundle_profile]
    metadata = read_json(resolve_asset_path(asset_root, metadata_path_str))
    packed_payload = _load_packed_asset_bundle(asset_root, metadata_path_str, metadata, bundle_profile)
    if packed_payload is not None:
        return packed_payload
    anchors = read_json(resolve_asset_path(asset_root, metadata["anchors_path"]))["anchors"]
    hair_rgba_path = metadata.get("hair_rgba_path")
    hair_rgba_bbox = metadata.get("hair_rgba_bbox")
    image_size = metadata.get("image_size")
    cached_hair_rgba: Any | None = None

    def load_required_image(path_key: str, flags: int) -> Any:
        nonlocal cached_hair_rgba
        if path_key not in required_keys:
            return None

        raw_value = metadata.get(path_key)
        if raw_value not in (None, ""):
            resolved_path = resolve_asset_path(asset_root, raw_value)
            if resolved_path.is_file():
                image = cv2.imread(str(resolved_path), flags)
                if image is not None:
                    return image

        if hair_rgba_path not in (None, ""):
            hair_rgba_resolved = resolve_asset_path(asset_root, hair_rgba_path)
            if cached_hair_rgba is None and hair_rgba_resolved.is_file():
                cached_hair_rgba = cv2.imread(str(hair_rgba_resolved), cv2.IMREAD_UNCHANGED)
            if cached_hair_rgba is not None and getattr(cached_hair_rgba, "ndim", 0) == 3:
                synthesized_full_frame = _synthesize_full_frame_from_hair_rgba(
                    cached_hair_rgba,
                    bbox=hair_rgba_bbox,
                    image_size=image_size,
                    path_key=path_key,
                )
                if synthesized_full_frame is not None:
                    return synthesized_full_frame
                if path_key == "image_path" and cached_hair_rgba.shape[2] >= 3:
                    return cached_hair_rgba[:, :, :3].copy()
                if path_key == "alpha_path" and cached_hair_rgba.shape[2] >= 4:
                    return cached_hair_rgba[:, :, 3].copy()

        if raw_value not in (None, ""):
            raise FileNotFoundError(f"failed to load {path_key}: {resolve_asset_path(asset_root, raw_value)}")
        if hair_rgba_path not in (None, ""):
            raise FileNotFoundError(
                f"failed to load {path_key} and hair_rgba fallback: {resolve_asset_path(asset_root, hair_rgba_path)}"
            )
        raise FileNotFoundError(f"missing metadata field: {path_key}")

    image = load_required_image("image_path", cv2.IMREAD_COLOR)
    alpha = load_required_image("alpha_path", cv2.IMREAD_GRAYSCALE)
    hair_mask = load_required_image("hair_mask_path", cv2.IMREAD_GRAYSCALE)
    face_mask = load_required_image("face_mask_path", cv2.IMREAD_GRAYSCALE)
    forehead_mask = load_required_image("forehead_mask_path", cv2.IMREAD_GRAYSCALE)
    ear_mask_left = load_required_image("ear_mask_left_path", cv2.IMREAD_GRAYSCALE)
    ear_mask_right = load_required_image("ear_mask_right_path", cv2.IMREAD_GRAYSCALE)
    neck_shoulder_mask = load_required_image("neck_shoulder_mask_path", cv2.IMREAD_GRAYSCALE)
    protect_face_mask = load_required_image("protect_face_mask_path", cv2.IMREAD_GRAYSCALE)
    hair_bbox = hair_bbox_from_mask(hair_mask)
    image_for_bounds = image
    if image_for_bounds is None and alpha is not None:
        image_for_bounds = alpha
    if image_for_bounds is None and hair_mask is not None:
        image_for_bounds = hair_mask
    if image_for_bounds is None:
        raise FileNotFoundError(f"unable to determine image bounds for {metadata_path_str}")
    crop_box = expanded_hair_crop(hair_bbox, image_for_bounds.shape[1], image_for_bounds.shape[0])
    hair_luma = _masked_mean_luma(image, hair_mask) if image is not None and hair_mask is not None else None
    return {
        "metadata": metadata,
        "anchors": anchors,
        "image": image,
        "alpha": alpha,
        "hair_mask": hair_mask,
        "face_mask": face_mask,
        "forehead_mask": forehead_mask,
        "ear_mask_left": ear_mask_left,
        "ear_mask_right": ear_mask_right,
        "neck_shoulder_mask": neck_shoulder_mask,
        "protect_face_mask": protect_face_mask,
        "hair_bbox": hair_bbox,
        "hair_luma": hair_luma,
        "crop_box": crop_box,
        "bundle_profile": bundle_profile,
    }


def _ensure_asset_bundle_mesh_geometry(
    asset_bundle: dict[str, Any],
    mesh_key: str,
) -> tuple[list[tuple[float, float]], list[tuple[int, int, int]]]:
    crop_box = asset_bundle["crop_box"]
    crop_width = crop_box[2] - crop_box[0]
    crop_height = crop_box[3] - crop_box[1]
    if mesh_key == "mesh_v2":
        source_points = asset_bundle.get("mesh_v2_source_points")
        mesh_triangles = asset_bundle.get("mesh_v2_triangles")
        if source_points is None or mesh_triangles is None:
            source_points = build_dense_mesh_source_points(asset_bundle["anchors"], crop_box)
            mesh_triangles = build_mesh_triangles(source_points, crop_width, crop_height)
            asset_bundle["mesh_v2_source_points"] = source_points
            asset_bundle["mesh_v2_triangles"] = mesh_triangles
        return source_points, mesh_triangles

    source_points = asset_bundle.get("mesh_source_points")
    mesh_triangles = asset_bundle.get("mesh_triangles")
    if source_points is None or mesh_triangles is None:
        source_points = build_mesh_source_points(asset_bundle["anchors"], crop_box)
        mesh_triangles = build_mesh_triangles(source_points, crop_width, crop_height)
        asset_bundle["mesh_source_points"] = source_points
        asset_bundle["mesh_triangles"] = mesh_triangles
    return source_points, mesh_triangles


@lru_cache(maxsize=ASSET_EDGE_RISK_CACHE_SIZE)
def asset_crop_edge_risk(asset_root_str: str, metadata_path_str: str) -> float:
    asset_bundle = load_asset_bundle(asset_root_str, metadata_path_str, BUNDLE_PROFILE_EDGE_RISK)
    hair_mask = asset_bundle["hair_mask"]
    alpha = asset_bundle["alpha"]
    x0, y0, x1, y1 = asset_bundle["crop_box"]
    if bool(asset_bundle.get("packed_crop_only")):
        crop_mask = hair_mask > 0
        crop_alpha = alpha > 0
        image_height, image_width = asset_bundle.get("image_size") or hair_mask.shape[:2]
    else:
        crop_mask = hair_mask[y0:y1, x0:x1] > 0
        crop_alpha = alpha[y0:y1, x0:x1] > 0
        image_height, image_width = hair_mask.shape[:2]
    mask_pixels = int(np.count_nonzero(crop_mask))
    alpha_pixels = int(np.count_nonzero(crop_alpha))
    if mask_pixels <= 0 or crop_mask.size == 0:
        return 0.0

    crop_height, crop_width = crop_mask.shape[:2]
    band = max(4, int(round(min(crop_height, crop_width) * 0.025)))
    top_ratio = float(np.count_nonzero(crop_mask[:band, :]) / mask_pixels)
    bottom_ratio = float(np.count_nonzero(crop_mask[-band:, :]) / mask_pixels)
    left_ratio = float(np.count_nonzero(crop_mask[:, :band]) / mask_pixels)
    right_ratio = float(np.count_nonzero(crop_mask[:, -band:]) / mask_pixels)

    edge_mask = np.zeros_like(crop_mask, dtype=np.uint8)
    edge_mask[:band, :] = 1
    edge_mask[-band:, :] = 1
    edge_mask[:, :band] = 1
    edge_mask[:, -band:] = 1
    mask_edge_ratio = float(np.count_nonzero(crop_mask & (edge_mask > 0)) / mask_pixels)
    alpha_edge_ratio = (
        float(np.count_nonzero(crop_alpha & (edge_mask > 0)) / alpha_pixels)
        if alpha_pixels > 0
        else 0.0
    )

    image_edge_penalty = 0.0
    if y0 <= 0:
        image_edge_penalty += 0.10
    if y1 >= image_height:
        image_edge_penalty += 0.08
    if x0 <= 0 or x1 >= image_width:
        image_edge_penalty += 0.06

    return round(
        top_ratio * 7.0
        + bottom_ratio * 5.0
        + max(left_ratio, right_ratio) * 4.0
        + mask_edge_ratio * 2.0
        + alpha_edge_ratio * 1.5
        + image_edge_penalty,
        6,
    )


def build_effective_alpha(
    warped_alpha: np.ndarray,
    warped_hair: np.ndarray,
    soft_sigma: float = 1.8,
    alpha_gain: np.ndarray | None = None,
    hair_sigma: float = 2.2,
) -> np.ndarray:
    effective_alpha = np.minimum(
        warped_alpha,
        opencv_gaussian_blur(
            warped_hair,
            (0, 0),
            sigma_x=hair_sigma,
            sigma_y=hair_sigma,
            min_pixels=24_000,
        ),
    )
    effective_alpha = effective_alpha.astype(np.float32) / 255.0
    effective_alpha = opencv_gaussian_blur(
        effective_alpha,
        (0, 0),
        sigma_x=soft_sigma,
        sigma_y=soft_sigma,
        min_pixels=24_000,
    )
    if alpha_gain is not None:
        effective_alpha *= np.clip(alpha_gain.astype(np.float32), 0.0, 1.0)
    return np.clip(effective_alpha, 0.0, 1.0)


def smoothstep_array(edge0: float, edge1: float, values: np.ndarray) -> np.ndarray:
    if abs(edge1 - edge0) < 1e-6:
        return np.zeros_like(values, dtype=np.float32)
    t_value = np.clip((values.astype(np.float32) - float(edge0)) / float(edge1 - edge0), 0.0, 1.0)
    return t_value * t_value * (3.0 - 2.0 * t_value)


def build_mesh_v2_alpha_gain(
    user_row: dict[str, Any],
    roi: tuple[int, int, int, int],
    roi_shape: tuple[int, int],
) -> np.ndarray:
    roi_height, roi_width = roi_shape
    if roi_width <= 0 or roi_height <= 0:
        return np.ones((max(roi_height, 1), max(roi_width, 1)), dtype=np.float32)

    dst_x0, dst_y0, _, _ = roi
    anchors = user_row["anchors"]
    pose = user_row.get("pose", {})
    face_bbox = user_row.get("face_bbox", {})

    face_height = max(
        1.0,
        float(face_bbox.get("h", 0.0))
        or abs(float(anchors["neck_left"]["y"]) - float(anchors["crown"]["y"])),
    )
    face_width = max(
        1.0,
        float(face_bbox.get("w", 0.0))
        or abs(float(anchors["right_temple"]["x"]) - float(anchors["left_temple"]["x"])),
    )
    abs_yaw = min(45.0, abs(float(pose.get("yaw_1deg", 0.0))))
    yaw_factor = abs_yaw / 45.0
    pitch_value = float(pose.get("pitch_1deg", 0.0))
    up_pitch_factor = float(np.clip((pitch_value - 6.0) / 20.0, 0.0, 1.0))
    down_pitch_factor = float(np.clip((-pitch_value - 5.0) / 18.0, 0.0, 1.0))

    y_coords = np.arange(dst_y0, dst_y0 + roi_height, dtype=np.float32)
    x_coords = np.arange(dst_x0, dst_x0 + roi_width, dtype=np.float32)

    crown_y = float(anchors["crown"]["y"])
    forehead_y = float(anchors["forehead_center"]["y"])
    temple_y = 0.5 * (float(anchors["left_temple"]["y"]) + float(anchors["right_temple"]["y"]))
    jaw_y = 0.5 * (float(anchors["lower_left"]["y"]) + float(anchors["lower_right"]["y"]))
    neck_y = 0.5 * (float(anchors["neck_left"]["y"]) + float(anchors["neck_right"]["y"]))
    face_center_x = (
        float(anchors["left_temple"]["x"])
        + float(anchors["right_temple"]["x"])
        + float(anchors["lower_left"]["x"])
        + float(anchors["lower_right"]["x"])
        + float(anchors["forehead_center"]["x"])
    ) / 5.0

    temple_half_span = abs(float(anchors["right_temple"]["x"]) - float(anchors["left_temple"]["x"])) * 0.5
    lower_half_span = abs(float(anchors["lower_right"]["x"]) - float(anchors["lower_left"]["x"])) * 0.5
    face_half_width = max(0.5 * face_width, temple_half_span, lower_half_span, 1.0)

    # Keep the overall hair volume, but soften regions that most often read as a pasted overlay.
    global_gain = float(np.clip(0.98 - 0.05 * yaw_factor - 0.04 * up_pitch_factor - 0.02 * down_pitch_factor, 0.84, 1.0))

    top_min_gain = float(np.clip(0.97 - 0.02 * up_pitch_factor - 0.01 * yaw_factor, 0.93, 0.99))
    top_center = forehead_y + 0.03 * face_height
    top_sigma = max(6.0, 0.26 * face_height)
    top_profile = np.exp(-0.5 * ((y_coords - top_center) / top_sigma) ** 2).astype(np.float32)
    top_gate = 1.0 - smoothstep_array(jaw_y + 0.05 * face_height, neck_y + 0.18 * face_height, y_coords)
    top_gain_y = 1.0 - (1.0 - top_min_gain) * top_profile * top_gate

    side_min_gain = float(np.clip(0.95 - 0.12 * yaw_factor, 0.80, 0.96))
    side_inner = max(8.0, face_half_width * (0.92 - 0.08 * yaw_factor))
    side_outer = max(side_inner + 1.0, face_half_width * (1.42 + 0.14 * yaw_factor))
    side_distance = np.abs(x_coords - face_center_x)
    side_strength = smoothstep_array(side_inner, side_outer, side_distance)
    side_gain_x = 1.0 - (1.0 - side_min_gain) * side_strength

    bottom_min_gain = float(np.clip(0.90 - 0.07 * yaw_factor - 0.06 * up_pitch_factor, 0.76, 0.94))
    bottom_start = jaw_y + 0.08 * face_height
    bottom_end = neck_y + 0.26 * face_height
    bottom_strength = smoothstep_array(bottom_start, bottom_end, y_coords)
    bottom_gain_y = 1.0 - (1.0 - bottom_min_gain) * bottom_strength

    gain_map = global_gain * top_gain_y[:, None] * side_gain_x[None, :] * bottom_gain_y[:, None]
    return np.clip(gain_map.astype(np.float32), 0.72, 1.0)


def smooth_mask_layer(mask_layer: np.ndarray | None, sigma: float, grow_radius: int = 0) -> np.ndarray | None:
    if mask_layer is None or mask_layer.size == 0:
        return None
    normalized = np.clip(mask_layer.astype(np.float32) / 255.0, 0.0, 1.0)
    if not bool(np.any(normalized > 0.0)):
        return None
    if grow_radius > 0:
        kernel_size = max(1, int(grow_radius) * 2 + 1)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        normalized = opencv_dilate(normalized, kernel, iterations=1, min_pixels=24_000)
        if not bool(np.any(normalized > 0.0)):
            return None
    return opencv_gaussian_blur(normalized, (0, 0), sigma_x=sigma, sigma_y=sigma, min_pixels=24_000)


def crop_runtime_mask_layer(
    mask_layer: np.ndarray | None,
    roi: tuple[int, int, int, int],
) -> np.ndarray | None:
    if mask_layer is None or mask_layer.size == 0:
        return None
    x0, y0, x1, y1 = roi
    if x1 <= x0 or y1 <= y0:
        return None
    cropped = mask_layer[y0:y1, x0:x1]
    if cropped.size == 0:
        return None
    return cropped


def _resize_runtime_mask_layer(
    mask_layer: np.ndarray | None,
    image_shape: tuple[int, int],
) -> np.ndarray | None:
    if mask_layer is None:
        return None
    image_height, image_width = image_shape
    array = np.asarray(mask_layer)
    if array.size == 0:
        return None
    if array.shape[:2] != (image_height, image_width):
        interpolation = cv2.INTER_LINEAR if array.dtype.kind == "f" else cv2.INTER_NEAREST
        array = cv2.resize(array, (image_width, image_height), interpolation=interpolation)
    return array


def _mask_layer_bbox(mask_layer: np.ndarray | None) -> tuple[int, int, int, int] | None:
    if mask_layer is None or mask_layer.size == 0:
        return None
    ys, xs = np.where(np.asarray(mask_layer) > 0)
    if xs.size == 0 or ys.size == 0:
        return None
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


def _expand_runtime_mask_roi(
    mask_layers: list[np.ndarray | None],
    image_shape: tuple[int, int],
    padding: int,
) -> tuple[int, int, int, int] | None:
    image_height, image_width = image_shape
    boxes = [box for box in (_mask_layer_bbox(mask_layer) for mask_layer in mask_layers) if box is not None]
    if not boxes:
        return None
    x0 = min(box[0] for box in boxes) - padding
    y0 = min(box[1] for box in boxes) - padding
    x1 = max(box[2] for box in boxes) + padding
    y1 = max(box[3] for box in boxes) + padding
    return clamp_roi(x0, y0, x1, y1, image_width, image_height)


def _scaled_points_about_pivot(
    points: np.ndarray,
    scale: float,
    pivot: tuple[float, float],
) -> np.ndarray:
    if points.size == 0 or abs(scale - 1.0) < 1e-4:
        return points
    pivot_array = np.array(pivot, dtype=np.float32).reshape(1, 2)
    return ((points.astype(np.float32) - pivot_array) * float(scale) + pivot_array).astype(np.float32)


def _scaled_affine_about_pivot(
    matrix: np.ndarray,
    scale: float,
    pivot: tuple[float, float],
) -> np.ndarray:
    if abs(scale - 1.0) < 1e-4:
        return matrix
    pivot_x, pivot_y = pivot
    scale_matrix = np.array(
        [
            [float(scale), 0.0, (1.0 - float(scale)) * float(pivot_x)],
            [0.0, float(scale), (1.0 - float(scale)) * float(pivot_y)],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )
    matrix_3x3 = np.vstack([matrix.astype(np.float32), np.array([0.0, 0.0, 1.0], dtype=np.float32)])
    return (scale_matrix @ matrix_3x3)[:2, :]


def compute_conservative_head_size_scale(
    user_row: dict[str, Any],
    user_mask_bundle: dict[str, Any] | None,
    image_shape: tuple[int, int],
) -> tuple[float, tuple[float, float]]:
    anchors = user_row.get("anchors", {})
    face_bbox = user_row.get("face_bbox", {})
    face_width = max(
        1.0,
        float(face_bbox.get("w", 0.0))
        or abs(float(anchors["right_temple"]["x"]) - float(anchors["left_temple"]["x"])),
    )
    face_height = max(
        1.0,
        float(face_bbox.get("h", 0.0))
        or abs(float(anchors["neck_left"]["y"]) - float(anchors["crown"]["y"])),
    )
    temple_span = max(
        1.0,
        abs(float(anchors["right_temple"]["x"]) - float(anchors["left_temple"]["x"])),
    )
    face_center_x = (
        float(anchors["left_temple"]["x"])
        + float(anchors["right_temple"]["x"])
        + float(anchors["lower_left"]["x"])
        + float(anchors["lower_right"]["x"])
        + float(anchors["forehead_center"]["x"])
    ) / 5.0
    forehead_y = float(anchors["forehead_center"]["y"])
    crown_y = float(anchors["crown"]["y"])
    jaw_y = 0.5 * (float(anchors["lower_left"]["y"]) + float(anchors["lower_right"]["y"]))
    pivot = (face_center_x, forehead_y + 0.14 * face_height)
    pose = user_row.get("pose", {})
    if abs(float(pose.get("yaw_1deg", 0.0))) > 16.0 or abs(float(pose.get("pitch_1deg", 0.0))) > 10.0:
        return 1.0, pivot
    if int(user_row.get("candidate_face_count") or 1) > 1:
        return 1.0, pivot

    if user_mask_bundle is None:
        return 1.0, pivot
    metrics = user_mask_bundle.get("metrics") or {}
    head_area_ratio = float(metrics.get("head_area_ratio") or 0.0)
    if head_area_ratio <= 0.02 or head_area_ratio >= 0.42:
        return 1.0, pivot

    head_mask = _resize_runtime_mask_layer(
        user_mask_bundle.get("head_silhouette_mask"),
        image_shape,
    )
    if head_mask is None:
        return 1.0, pivot

    head_layer = smooth_mask_layer(head_mask, sigma=4.2, grow_radius=1)
    if head_layer is None:
        return 1.0, pivot

    binary_mask = np.asarray(head_layer, dtype=np.float32) > 0.34
    if not np.any(binary_mask):
        return 1.0, pivot

    image_height, image_width = image_shape
    focus_x0 = max(0, int(round(face_center_x - 0.92 * face_width)))
    focus_x1 = min(image_width, int(round(face_center_x + 0.92 * face_width)))
    focus_y0 = max(0, int(round(crown_y - 0.08 * face_height)))
    focus_y1 = min(image_height, int(round(jaw_y + 0.06 * face_height)))
    if focus_x1 <= focus_x0 or focus_y1 <= focus_y0:
        return 1.0, pivot

    focus_mask = binary_mask[focus_y0:focus_y1, focus_x0:focus_x1]
    if np.count_nonzero(focus_mask) < 48:
        return 1.0, pivot
    focus_area = max(1, (focus_y1 - focus_y0) * (focus_x1 - focus_x0))
    focus_occupancy = float(np.count_nonzero(focus_mask)) / float(focus_area)
    if focus_occupancy >= 0.72:
        return 1.0, pivot

    ys, xs = np.where(focus_mask)
    observed_width = float(xs.max() - xs.min() + 1)
    observed_height = float(ys.max() - ys.min() + 1)
    expected_width = max(face_width * 1.12, temple_span * 1.16, 1.0)
    expected_height = max((forehead_y - crown_y) + 0.54 * face_height, 0.82 * face_height, 1.0)
    width_ratio = observed_width / expected_width
    height_ratio = observed_height / expected_height
    combined_ratio = 0.62 * width_ratio + 0.38 * height_ratio

    if combined_ratio >= 0.995:
        return 1.0, pivot

    # Only allow a subtle shrink. Expanding based on the user's current silhouette
    # can easily overestimate head volume because the silhouette already contains hair.
    conservative_scale = 1.0 + 0.22 * (combined_ratio - 1.0)
    conservative_scale = float(np.clip(conservative_scale, 0.965, 1.0))
    return conservative_scale, pivot


def apply_user_mask_occlusion_gain(
    user_row: dict[str, Any],
    roi: tuple[int, int, int, int],
    effective_alpha: np.ndarray,
    user_mask_bundle: dict[str, Any] | None,
    strength_scale: float = 1.0,
) -> np.ndarray:
    if user_mask_bundle is None or effective_alpha.size == 0:
        return effective_alpha

    pose = user_row.get("pose", {})
    abs_yaw = min(45.0, abs(float(pose.get("yaw_1deg", 0.0))))
    yaw_factor = abs_yaw / 45.0
    pitch_value = float(pose.get("pitch_1deg", 0.0))
    up_pitch_factor = float(np.clip((pitch_value - 6.0) / 20.0, 0.0, 1.0))
    down_pitch_factor = float(np.clip((-pitch_value - 4.0) / 16.0, 0.0, 1.0))
    anchors = user_row.get("anchors", {})
    face_bbox = user_row.get("face_bbox", {})
    face_height = max(
        1.0,
        float(face_bbox.get("h", 0.0))
        or abs(float(anchors["neck_left"]["y"]) - float(anchors["crown"]["y"])),
    )

    ear_left_layer = smooth_mask_layer(crop_runtime_mask_layer(user_mask_bundle.get("ear_left_mask"), roi), sigma=6.5, grow_radius=4)
    ear_right_layer = smooth_mask_layer(crop_runtime_mask_layer(user_mask_bundle.get("ear_right_mask"), roi), sigma=6.5, grow_radius=4)
    forehead_layer = smooth_mask_layer(crop_runtime_mask_layer(user_mask_bundle.get("forehead_mask"), roi), sigma=6.0, grow_radius=2)
    neck_layer = smooth_mask_layer(crop_runtime_mask_layer(user_mask_bundle.get("neck_shoulder_mask"), roi), sigma=7.5, grow_radius=4)
    protect_layer = smooth_mask_layer(crop_runtime_mask_layer(user_mask_bundle.get("protect_face_mask"), roi), sigma=6.0, grow_radius=2)

    combined_gain = np.ones_like(effective_alpha, dtype=np.float32)
    ear_layers = [layer for layer in (ear_left_layer, ear_right_layer) if layer is not None]
    if ear_layers:
        ear_layer = np.maximum.reduce(ear_layers)
        dst_x0, dst_y0, _, _ = roi
        y_coords = np.arange(dst_y0, dst_y0 + effective_alpha.shape[0], dtype=np.float32)
        temple_y = 0.5 * (float(anchors["left_temple"]["y"]) + float(anchors["right_temple"]["y"]))
        jaw_y = 0.5 * (float(anchors["lower_left"]["y"]) + float(anchors["lower_right"]["y"]))
        neck_y = 0.5 * (float(anchors["neck_left"]["y"]) + float(anchors["neck_right"]["y"]))
        ear_upper = smoothstep_array(temple_y - 0.18 * face_height, temple_y + 0.02 * face_height, y_coords)
        ear_lower = 1.0 - smoothstep_array(jaw_y + 0.10 * face_height, neck_y + 0.14 * face_height, y_coords)
        ear_vertical_gate = np.clip(ear_upper * ear_lower, 0.0, 1.0)[:, None]
        ear_strength = float(np.clip((0.04 + 0.20 * yaw_factor) * strength_scale, 0.02, 0.24))
        combined_gain *= 1.0 - ear_strength * ear_layer * ear_vertical_gate
    if forehead_layer is not None:
        forehead_strength = float(
            np.clip((0.035 + 0.04 * up_pitch_factor + 0.015 * (1.0 - yaw_factor)) * strength_scale, 0.02, 0.09)
        )
        combined_gain *= 1.0 - forehead_strength * forehead_layer
    if protect_layer is not None:
        protect_strength = float(np.clip((0.03 + 0.05 * yaw_factor + 0.05 * down_pitch_factor) * strength_scale, 0.02, 0.10))
        combined_gain *= 1.0 - protect_strength * protect_layer
    if neck_layer is not None:
        neck_strength = float(np.clip((0.035 + 0.04 * yaw_factor + 0.03 * down_pitch_factor) * strength_scale, 0.02, 0.10))
        combined_gain *= 1.0 - neck_strength * neck_layer
    floor_value = float(np.clip(1.0 - 0.22 * max(0.4, strength_scale), 0.70, 0.92))
    return np.clip(effective_alpha * np.clip(combined_gain, floor_value, 1.0), 0.0, 1.0)


def apply_user_side_silhouette_gain(
    user_row: dict[str, Any],
    roi: tuple[int, int, int, int],
    effective_alpha: np.ndarray,
    user_mask_bundle: dict[str, Any] | None,
) -> np.ndarray:
    if user_mask_bundle is None or effective_alpha.size == 0:
        return effective_alpha

    pose = user_row.get("pose", {})
    yaw_value = float(pose.get("yaw_1deg", 0.0))
    abs_yaw = abs(yaw_value)
    if abs_yaw < 14.0:
        return effective_alpha

    head_layer = smooth_mask_layer(
        crop_runtime_mask_layer(user_mask_bundle.get("head_silhouette_mask"), roi),
        sigma=7.0,
        grow_radius=5,
    )
    if head_layer is None:
        return effective_alpha

    face_bbox = user_row.get("face_bbox", {})
    anchors = user_row.get("anchors", {})
    face_width = max(
        1.0,
        float(face_bbox.get("w", 0.0))
        or abs(float(anchors["right_temple"]["x"]) - float(anchors["left_temple"]["x"])),
    )
    face_center_x = (
        float(face_bbox.get("x", 0.0)) + 0.5 * float(face_bbox.get("w", 0.0))
        if face_bbox.get("w")
        else 0.5 * (float(anchors["left_temple"]["x"]) + float(anchors["right_temple"]["x"]))
    )
    dst_x0, dst_y0, _, _ = roi
    x_coords = np.arange(dst_x0, dst_x0 + effective_alpha.shape[1], dtype=np.float32)
    y_coords = np.arange(dst_y0, dst_y0 + effective_alpha.shape[0], dtype=np.float32)
    if yaw_value >= 0.0:
        far_gate = smoothstep_array(
            face_center_x + 0.06 * face_width,
            face_center_x + 0.48 * face_width,
            x_coords,
        )[None, :]
    else:
        far_gate = (
            1.0
            - smoothstep_array(
                face_center_x - 0.48 * face_width,
                face_center_x - 0.06 * face_width,
                x_coords,
            )
        )[None, :]

    outside_head = np.clip(1.0 - np.clip(head_layer.astype(np.float32), 0.0, 1.0), 0.0, 1.0)
    temple_y = 0.5 * (float(anchors["left_temple"]["y"]) + float(anchors["right_temple"]["y"]))
    jaw_y = 0.5 * (float(anchors["lower_left"]["y"]) + float(anchors["lower_right"]["y"]))
    neck_y = 0.5 * (float(anchors["neck_left"]["y"]) + float(anchors["neck_right"]["y"]))
    upper_gate = smoothstep_array(temple_y - 0.22 * float(face_bbox.get("h", face_width)), temple_y + 0.06 * float(face_bbox.get("h", face_width)), y_coords)
    lower_gate = 1.0 - smoothstep_array(jaw_y + 0.08 * float(face_bbox.get("h", face_width)), neck_y + 0.16 * float(face_bbox.get("h", face_width)), y_coords)
    vertical_gate = np.clip(upper_gate * lower_gate, 0.0, 1.0)[:, None]
    silhouette_strength = float(np.clip(0.14 + 0.26 * ((abs_yaw - 14.0) / 22.0), 0.14, 0.40))
    gain = 1.0 - silhouette_strength * outside_head * far_gate * vertical_gate
    return np.clip(effective_alpha * np.clip(gain, 0.62, 1.0), 0.0, 1.0)


def apply_user_head_blur_underlay(
    user_image: np.ndarray,
    user_row: dict[str, Any],
    user_mask_bundle: dict[str, Any] | None,
    strength_scale: float = 1.0,
) -> np.ndarray:
    if user_mask_bundle is None:
        return user_image.copy()

    image_height, image_width = user_image.shape[:2]
    image_shape = (image_height, image_width)
    face_bbox = user_row.get("face_bbox", {})
    face_width = max(1.0, float(face_bbox.get("w", 0.0)))
    pose = user_row.get("pose", {})
    yaw_factor = min(1.0, abs(float(pose.get("yaw_1deg", 0.0))) / 35.0)
    up_pitch_factor = float(np.clip((float(pose.get("pitch_1deg", 0.0)) - 4.0) / 20.0, 0.0, 1.0))
    blur_strength = float(np.clip((0.44 + 0.16 * yaw_factor + 0.06 * up_pitch_factor) * strength_scale, 0.22, 0.68))
    sigma = max(6.0, face_width * 0.085)
    roi_padding = max(
        24,
        int(round(face_width * 0.18)),
        int(round(sigma * 3.2)),
    )
    resized_masks = {
        key: _resize_runtime_mask_layer(user_mask_bundle.get(key), image_shape)
        for key in (
            "blur_mask",
            "hair_mask",
            "alpha_mask",
            "suppress_prior_mask",
            "hair_confidence",
            "protect_face_mask",
            "ear_left_mask",
            "ear_right_mask",
            "head_silhouette_mask",
        )
    }
    processing_roi = _expand_runtime_mask_roi(
        list(resized_masks.values()),
        image_shape,
        roi_padding,
    )
    if processing_roi is None:
        return user_image.copy()
    crop_x0, crop_y0, crop_x1, crop_y1 = processing_roi
    user_image_roi = user_image[crop_y0:crop_y1, crop_x0:crop_x1]

    def _coerce_mask_layer(mask_layer: np.ndarray | None) -> np.ndarray | None:
        if mask_layer is None:
            return None
        return crop_runtime_mask_layer(mask_layer, processing_roi)

    blur_layer = smooth_mask_layer(_coerce_mask_layer(resized_masks["blur_mask"]), sigma=8.5, grow_radius=0)
    hair_core_layer = smooth_mask_layer(_coerce_mask_layer(resized_masks["hair_mask"]), sigma=5.8, grow_radius=2)
    alpha_layer = smooth_mask_layer(_coerce_mask_layer(resized_masks["alpha_mask"]), sigma=6.2, grow_radius=0)
    suppress_layer = smooth_mask_layer(_coerce_mask_layer(resized_masks["suppress_prior_mask"]), sigma=7.0, grow_radius=1)
    confidence_layer = _coerce_mask_layer(resized_masks["hair_confidence"])
    if confidence_layer is not None and np.asarray(confidence_layer).size > 0:
        confidence_layer = np.clip(np.asarray(confidence_layer).astype(np.float32), 0.0, 1.0)
    else:
        confidence_layer = None

    base_layers = [layer for layer in (blur_layer, hair_core_layer, alpha_layer, suppress_layer) if layer is not None]
    if not base_layers:
        return user_image.copy()
    blur_layer = np.clip(
        0.42 * (blur_layer if blur_layer is not None else 0.0)
        + 0.28 * (hair_core_layer if hair_core_layer is not None else 0.0)
        + 0.18 * (alpha_layer if alpha_layer is not None else 0.0)
        + 0.12 * (suppress_layer if suppress_layer is not None else 0.0),
        0.0,
        1.0,
    )
    if float(np.max(blur_layer)) <= 0.01:
        return user_image.copy()

    blur_mask = np.clip(blur_layer.astype(np.float32) * blur_strength, 0.0, 1.0)
    if confidence_layer is not None:
        blur_mask *= np.clip(0.74 + 0.26 * confidence_layer, 0.58, 1.0)
    hair_mask = _coerce_mask_layer(resized_masks["hair_mask"])
    hair_mask = np.asarray(hair_mask, dtype=np.uint8) if hair_mask is not None else None
    ring_color = None
    if hair_mask is not None and hair_mask.size:
        ring_outer = opencv_dilate(hair_mask, np.ones((13, 13), np.uint8), iterations=1, min_pixels=24_000)
        ring_inner = opencv_dilate(hair_mask, np.ones((5, 5), np.uint8), iterations=1, min_pixels=24_000)
        ring_mask = (ring_outer > 0) & ~(ring_inner > 0)
        if np.count_nonzero(ring_mask) >= 64:
            ring_color = np.median(user_image_roi[ring_mask], axis=0).astype(np.float32)

    protect_mask = _coerce_mask_layer(resized_masks["protect_face_mask"])
    if protect_mask is not None:
        protect_layer = smooth_mask_layer(protect_mask, sigma=5.0, grow_radius=2)
        if protect_layer is not None:
            blur_mask *= np.clip(1.0 - 0.82 * protect_layer, 0.0, 1.0)
    ear_left_mask = _coerce_mask_layer(resized_masks["ear_left_mask"])
    ear_right_mask = _coerce_mask_layer(resized_masks["ear_right_mask"])
    ear_layers = [
        smooth_mask_layer(mask_layer, sigma=4.5, grow_radius=1)
        for mask_layer in (ear_left_mask, ear_right_mask)
        if mask_layer is not None
    ]
    ear_layers = [layer for layer in ear_layers if layer is not None]
    if ear_layers:
        ear_layer = np.maximum.reduce(ear_layers)
        blur_mask *= np.clip(1.0 - 0.60 * ear_layer, 0.0, 1.0)
    head_silhouette_mask = _coerce_mask_layer(resized_masks["head_silhouette_mask"])
    if head_silhouette_mask is not None:
        head_layer = smooth_mask_layer(head_silhouette_mask, sigma=5.6, grow_radius=2)
        if head_layer is not None:
            blur_mask *= np.clip(0.55 + 0.45 * head_layer, 0.0, 1.0)

    blur_mask = opencv_gaussian_blur(
        np.clip(blur_mask, 0.0, 1.0),
        (0, 0),
        sigma_x=2.6,
        sigma_y=2.6,
        min_pixels=24_000,
    )

    blur_active = blur_mask > 0.01
    if not np.any(blur_active):
        return user_image.copy()

    ys, xs = np.where(blur_active)
    pad = max(12, int(round(face_width * 0.12)))
    blur_height, blur_width = blur_mask.shape[:2]
    x0 = max(0, int(xs.min()) - pad)
    y0 = max(0, int(ys.min()) - pad)
    x1 = min(blur_width, int(xs.max()) + pad + 1)
    y1 = min(blur_height, int(ys.max()) + pad + 1)

    user_roi = user_image_roi[y0:y1, x0:x1]
    blurred_roi = opencv_gaussian_blur(
        user_roi,
        (0, 0),
        sigma_x=sigma,
        sigma_y=sigma,
        min_pixels=24_000,
    )
    if ring_color is not None:
        blurred_roi = np.clip(
            blurred_roi.astype(np.float32) * 0.92 + ring_color.reshape(1, 1, 3) * 0.08,
            0.0,
            255.0,
        ).astype(np.uint8)
    blur_mask_roi = blur_mask[y0:y1, x0:x1]

    blended_roi = user_roi.astype(np.float32) * (1.0 - blur_mask_roi[..., None]) + blurred_roi.astype(np.float32) * blur_mask_roi[..., None]
    composite = user_image.copy()
    dst_x0 = crop_x0 + x0
    dst_y0 = crop_y0 + y0
    dst_x1 = crop_x0 + x1
    dst_y1 = crop_y0 + y1
    composite[dst_y0:dst_y1, dst_x0:dst_x1] = np.clip(blended_roi, 0.0, 255.0).astype(np.uint8)
    return composite


def warp_cropped_mask_layer(
    mask_layer: np.ndarray | None,
    crop_box: tuple[int, int, int, int],
    source_points: list[tuple[float, float]],
    destination_points: list[tuple[float, float]],
    triangles: list[tuple[int, int, int]],
    output_size: tuple[int, int],
) -> np.ndarray | None:
    if mask_layer is None:
        return None
    src_x0, src_y0, src_x1, src_y1 = crop_box
    cropped_mask = mask_layer[src_y0:src_y1, src_x0:src_x1]
    if cropped_mask.size == 0:
        return None
    if not np.any(cropped_mask):
        return None
    warped_mask = warp_mesh_layer(
        cropped_mask,
        source_points,
        destination_points,
        triangles,
        output_size,
        cv2.INTER_NEAREST,
    )
    return np.clip(warped_mask, 0.0, 255.0).astype(np.uint8)


def build_mesh_v3_alpha_gain(
    user_row: dict[str, Any],
    roi: tuple[int, int, int, int],
    roi_shape: tuple[int, int],
    warped_forehead_mask: np.ndarray | None,
    warped_ear_left_mask: np.ndarray | None,
    warped_ear_right_mask: np.ndarray | None,
    warped_neck_mask: np.ndarray | None,
) -> np.ndarray:
    geom_gain = build_mesh_v2_alpha_gain(user_row, roi, roi_shape)
    pose = user_row.get("pose", {})
    abs_yaw = min(45.0, abs(float(pose.get("yaw_1deg", 0.0))))
    yaw_factor = abs_yaw / 45.0
    pitch_value = float(pose.get("pitch_1deg", 0.0))
    up_pitch_factor = float(np.clip((pitch_value - 6.0) / 20.0, 0.0, 1.0))
    down_pitch_factor = float(np.clip((-pitch_value - 5.0) / 18.0, 0.0, 1.0))

    forehead_layer = smooth_mask_layer(warped_forehead_mask, sigma=8.0, grow_radius=4)
    ear_left_layer = smooth_mask_layer(warped_ear_left_mask, sigma=7.5, grow_radius=5)
    ear_right_layer = smooth_mask_layer(warped_ear_right_mask, sigma=7.5, grow_radius=5)
    neck_layer = smooth_mask_layer(warped_neck_mask, sigma=9.0, grow_radius=6)

    combined_gain = geom_gain.astype(np.float32).copy()
    if forehead_layer is not None:
        forehead_strength = float(np.clip(0.08 + 0.08 * up_pitch_factor + 0.04 * (1.0 - yaw_factor), 0.08, 0.20))
        combined_gain *= 1.0 - forehead_strength * forehead_layer
    ear_layers = [layer for layer in (ear_left_layer, ear_right_layer) if layer is not None]
    if ear_layers:
        ear_layer = np.maximum.reduce(ear_layers)
        ear_strength = float(np.clip(0.06 + 0.18 * yaw_factor, 0.06, 0.24))
        combined_gain *= 1.0 - ear_strength * ear_layer
    if neck_layer is not None:
        neck_strength = float(np.clip(0.07 + 0.08 * yaw_factor + 0.05 * up_pitch_factor + 0.03 * down_pitch_factor, 0.07, 0.20))
        combined_gain *= 1.0 - neck_strength * neck_layer
    combined_gain *= build_frontal_head_envelope_gain(user_row, roi, roi_shape)
    combined_gain *= build_frontal_side_cap_gain(user_row, roi, roi_shape)
    combined_gain *= build_far_side_shell_gain(user_row, roi, roi_shape)
    return np.clip(combined_gain, 0.64, 1.0)


def apply_asset_skin_suppression_gain(
    user_row: dict[str, Any],
    roi: tuple[int, int, int, int],
    effective_alpha: np.ndarray,
    warped_face_mask: np.ndarray | None,
    warped_protect_face_mask: np.ndarray | None,
    warped_ear_left_mask: np.ndarray | None,
    warped_ear_right_mask: np.ndarray | None,
    *,
    include_ears: bool = True,
    prefer_protect_face_only: bool = False,
    layer_sigma_scale: float = 1.0,
) -> np.ndarray:
    if effective_alpha.size == 0:
        return effective_alpha

    sigma_scale = float(np.clip(layer_sigma_scale, 0.4, 1.0))
    face_layer = smooth_mask_layer(warped_face_mask, sigma=5.5 * sigma_scale, grow_radius=1 if sigma_scale >= 0.85 else 0)
    protect_layer = smooth_mask_layer(
        warped_protect_face_mask,
        sigma=6.2 * sigma_scale,
        grow_radius=2 if sigma_scale >= 0.85 else 1,
    )
    ear_left_layer = None
    ear_right_layer = None
    if include_ears:
        ear_left_layer = smooth_mask_layer(warped_ear_left_mask, sigma=5.2 * sigma_scale, grow_radius=2 if sigma_scale >= 0.85 else 1)
        ear_right_layer = smooth_mask_layer(warped_ear_right_mask, sigma=5.2 * sigma_scale, grow_radius=2 if sigma_scale >= 0.85 else 1)
    if face_layer is None and protect_layer is None and ear_left_layer is None and ear_right_layer is None:
        return effective_alpha

    pose = user_row.get("pose", {})
    anchors = user_row.get("anchors", {})
    face_bbox = user_row.get("face_bbox", {})
    abs_yaw = min(45.0, abs(float(pose.get("yaw_1deg", 0.0))))
    yaw_factor = abs_yaw / 45.0
    face_height = max(
        1.0,
        float(face_bbox.get("h", 0.0))
        or abs(float(anchors["neck_left"]["y"]) - float(anchors["crown"]["y"])),
    )
    face_width = max(
        1.0,
        float(face_bbox.get("w", 0.0))
        or abs(float(anchors["right_temple"]["x"]) - float(anchors["left_temple"]["x"])),
    )

    dst_x0, dst_y0, _, _ = roi
    y_coords = np.arange(dst_y0, dst_y0 + effective_alpha.shape[0], dtype=np.float32)
    x_coords = np.arange(dst_x0, dst_x0 + effective_alpha.shape[1], dtype=np.float32)
    face_center_x = (
        float(anchors["left_temple"]["x"])
        + float(anchors["right_temple"]["x"])
        + float(anchors["lower_left"]["x"])
        + float(anchors["lower_right"]["x"])
        + float(anchors["forehead_center"]["x"])
    ) / 5.0
    temple_y = 0.5 * (float(anchors["left_temple"]["y"]) + float(anchors["right_temple"]["y"]))
    jaw_y = 0.5 * (float(anchors["lower_left"]["y"]) + float(anchors["lower_right"]["y"]))
    neck_y = 0.5 * (float(anchors["neck_left"]["y"]) + float(anchors["neck_right"]["y"]))
    side_distance = np.abs(x_coords - face_center_x)
    face_half_width = max(0.5 * face_width, 1.0)
    side_gate = smoothstep_array(face_half_width * 0.58, face_half_width * 0.96, side_distance)[None, :]
    upper_gate = smoothstep_array(temple_y - 0.10 * face_height, temple_y + 0.08 * face_height, y_coords)[:, None]
    lower_gate = 1.0 - smoothstep_array(jaw_y + 0.12 * face_height, neck_y + 0.10 * face_height, y_coords)[:, None]
    vertical_gate = np.clip(upper_gate * lower_gate, 0.0, 1.0)

    combined_gain = np.ones_like(effective_alpha, dtype=np.float32)
    face_combined = None
    if prefer_protect_face_only and protect_layer is not None:
        face_combined = protect_layer
    elif face_layer is not None and protect_layer is not None:
        face_combined = np.maximum(face_layer, protect_layer)
    else:
        face_combined = face_layer if face_layer is not None else protect_layer
    if face_combined is not None:
        face_strength = float(np.clip(0.10 + 0.06 * yaw_factor, 0.10, 0.18))
        combined_gain *= 1.0 - face_strength * face_combined * side_gate * vertical_gate

    ear_layers = [layer for layer in (ear_left_layer, ear_right_layer) if layer is not None]
    if ear_layers:
        ear_layer = np.maximum.reduce(ear_layers)
        ear_strength = float(np.clip(0.16 + 0.10 * yaw_factor, 0.16, 0.26))
        combined_gain *= 1.0 - ear_strength * ear_layer * vertical_gate

    return np.clip(effective_alpha * np.clip(combined_gain, 0.74, 1.0), 0.0, 1.0)


def _warp_mask_stack(
    mask_layers: list[np.ndarray],
    matrix: np.ndarray,
    dsize: tuple[int, int],
    *,
    min_pixels: int = 16_384,
) -> list[np.ndarray]:
    if not mask_layers:
        return []
    if len(mask_layers) == 1:
        return [
            opencv_warp_affine(
                mask_layers[0],
                matrix,
                dsize,
                flags=cv2.INTER_NEAREST,
                borderMode=cv2.BORDER_CONSTANT,
                min_pixels=min_pixels,
            )
        ]
    stacked = np.dstack(mask_layers)
    warped = opencv_warp_affine(
        stacked,
        matrix,
        dsize,
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        min_pixels=min_pixels,
    )
    if warped.ndim == 2:
        warped = warped[:, :, None]
    return [warped[:, :, idx] for idx in range(warped.shape[2])]


def build_frontal_head_envelope_gain(
    user_row: dict[str, Any],
    roi: tuple[int, int, int, int],
    roi_shape: tuple[int, int],
) -> np.ndarray:
    roi_height, roi_width = roi_shape
    if roi_width <= 0 or roi_height <= 0:
        return np.ones((max(roi_height, 1), max(roi_width, 1)), dtype=np.float32)

    pose = user_row.get("pose", {})
    yaw_value = abs(float(pose.get("yaw_1deg", 0.0)))
    roll_value = abs(float(pose.get("roll_1deg", 0.0)))
    frontal_factor = float(np.clip(1.0 - yaw_value / 18.0, 0.0, 1.0)) * float(np.clip(1.0 - roll_value / 10.0, 0.0, 1.0))
    if frontal_factor <= 0.0:
        return np.ones((roi_height, roi_width), dtype=np.float32)

    anchors = user_row["anchors"]
    face_bbox = user_row.get("face_bbox", {})
    face_height = max(
        1.0,
        float(face_bbox.get("h", 0.0))
        or abs(float(anchors["neck_left"]["y"]) - float(anchors["crown"]["y"])),
    )
    face_width = max(
        1.0,
        float(face_bbox.get("w", 0.0))
        or abs(float(anchors["right_temple"]["x"]) - float(anchors["left_temple"]["x"])),
    )

    dst_x0, dst_y0, _, _ = roi
    y_coords = np.arange(dst_y0, dst_y0 + roi_height, dtype=np.float32)
    x_coords = np.arange(dst_x0, dst_x0 + roi_width, dtype=np.float32)
    crown_y = float(anchors["crown"]["y"])
    forehead_y = float(anchors["forehead_center"]["y"])
    jaw_y = 0.5 * (float(anchors["lower_left"]["y"]) + float(anchors["lower_right"]["y"]))
    neck_y = 0.5 * (float(anchors["neck_left"]["y"]) + float(anchors["neck_right"]["y"]))
    face_center_x = (
        float(anchors["left_temple"]["x"])
        + float(anchors["right_temple"]["x"])
        + float(anchors["lower_left"]["x"])
        + float(anchors["lower_right"]["x"])
        + float(anchors["forehead_center"]["x"])
    ) / 5.0

    head_center_y = forehead_y + 0.12 * face_height
    side_radius = max(18.0, face_width * 0.62)
    top_radius = max(22.0, max(forehead_y - crown_y, 0.16 * face_height) + 0.62 * face_height)
    ellipse_distance = (
        ((x_coords - face_center_x) / side_radius) ** 2
        + ((y_coords[:, None] - head_center_y) / top_radius) ** 2
    ).astype(np.float32)
    ellipse_keep = 1.0 - smoothstep_array(1.0, 1.10, ellipse_distance)
    upper_gate = 1.0 - smoothstep_array(jaw_y + 0.02 * face_height, neck_y + 0.10 * face_height, y_coords)
    envelope_strength = float(np.clip(0.22 + 0.18 * frontal_factor, 0.22, 0.40))
    envelope_gain = 1.0 - envelope_strength * upper_gate[:, None] * (1.0 - ellipse_keep)
    return np.clip(envelope_gain.astype(np.float32), 0.56, 1.0)


def build_frontal_side_cap_gain(
    user_row: dict[str, Any],
    roi: tuple[int, int, int, int],
    roi_shape: tuple[int, int],
) -> np.ndarray:
    roi_height, roi_width = roi_shape
    if roi_width <= 0 or roi_height <= 0:
        return np.ones((max(roi_height, 1), max(roi_width, 1)), dtype=np.float32)

    pose = user_row.get("pose", {})
    yaw_value = abs(float(pose.get("yaw_1deg", 0.0)))
    roll_value = abs(float(pose.get("roll_1deg", 0.0)))
    frontal_factor = float(np.clip(1.0 - yaw_value / 20.0, 0.0, 1.0)) * float(np.clip(1.0 - roll_value / 12.0, 0.0, 1.0))
    if frontal_factor <= 0.0:
        return np.ones((roi_height, roi_width), dtype=np.float32)

    anchors = user_row["anchors"]
    face_bbox = user_row.get("face_bbox", {})
    face_height = max(
        1.0,
        float(face_bbox.get("h", 0.0))
        or abs(float(anchors["neck_left"]["y"]) - float(anchors["crown"]["y"])),
    )
    face_half_width = max(
        1.0,
        (float(face_bbox.get("w", 0.0)) or abs(float(anchors["right_temple"]["x"]) - float(anchors["left_temple"]["x"]))) * 0.5,
    )

    dst_x0, dst_y0, _, _ = roi
    y_coords = np.arange(dst_y0, dst_y0 + roi_height, dtype=np.float32)
    x_coords = np.arange(dst_x0, dst_x0 + roi_width, dtype=np.float32)
    jaw_y = 0.5 * (float(anchors["lower_left"]["y"]) + float(anchors["lower_right"]["y"]))
    neck_y = 0.5 * (float(anchors["neck_left"]["y"]) + float(anchors["neck_right"]["y"]))
    face_center_x = (
        float(anchors["left_temple"]["x"])
        + float(anchors["right_temple"]["x"])
        + float(anchors["lower_left"]["x"])
        + float(anchors["lower_right"]["x"])
        + float(anchors["forehead_center"]["x"])
    ) / 5.0

    side_distance = np.abs(x_coords - face_center_x)
    cap_inner = max(8.0, face_half_width * 0.96)
    cap_outer = max(cap_inner + 1.0, face_half_width * 1.08)
    cap_strength = smoothstep_array(cap_inner, cap_outer, side_distance)
    upper_gate = 1.0 - smoothstep_array(jaw_y + 0.02 * face_height, neck_y + 0.08 * face_height, y_coords)
    cap_gain = 1.0 - (0.56 + 0.26 * frontal_factor) * upper_gate[:, None] * cap_strength[None, :]
    return np.clip(cap_gain.astype(np.float32), 0.18, 1.0)


def build_far_side_shell_gain(
    user_row: dict[str, Any],
    roi: tuple[int, int, int, int],
    roi_shape: tuple[int, int],
) -> np.ndarray:
    roi_height, roi_width = roi_shape
    if roi_width <= 0 or roi_height <= 0:
        return np.ones((max(roi_height, 1), max(roi_width, 1)), dtype=np.float32)

    pose = user_row.get("pose", {})
    yaw_value = float(pose.get("yaw_1deg", 0.0))
    abs_yaw = abs(yaw_value)
    side_factor = float(np.clip((abs_yaw - 6.0) / 18.0, 0.0, 1.0))
    if side_factor <= 0.0:
        return np.ones((roi_height, roi_width), dtype=np.float32)

    anchors = user_row["anchors"]
    face_bbox = user_row.get("face_bbox", {})
    face_height = max(
        1.0,
        float(face_bbox.get("h", 0.0))
        or abs(float(anchors["neck_left"]["y"]) - float(anchors["crown"]["y"])),
    )
    face_width = max(
        1.0,
        float(face_bbox.get("w", 0.0))
        or abs(float(anchors["right_temple"]["x"]) - float(anchors["left_temple"]["x"])),
    )

    dst_x0, dst_y0, _, _ = roi
    y_coords = np.arange(dst_y0, dst_y0 + roi_height, dtype=np.float32)
    x_coords = np.arange(dst_x0, dst_x0 + roi_width, dtype=np.float32)
    jaw_y = 0.5 * (float(anchors["lower_left"]["y"]) + float(anchors["lower_right"]["y"]))
    neck_y = 0.5 * (float(anchors["neck_left"]["y"]) + float(anchors["neck_right"]["y"]))

    if yaw_value >= 0.0:
        far_anchor_x = max(
            float(anchors["right_temple"]["x"]),
            float(anchors["right_side"]["x"]),
            float(anchors["right_ear_root"]["x"]),
        )
        far_distance = x_coords - far_anchor_x
    else:
        far_anchor_x = min(
            float(anchors["left_temple"]["x"]),
            float(anchors["left_side"]["x"]),
            float(anchors["left_ear_root"]["x"]),
        )
        far_distance = far_anchor_x - x_coords

    side_inner = max(5.0, face_width * 0.03)
    side_outer = max(side_inner + 1.0, side_inner + face_width * (0.12 + 0.14 * side_factor))
    far_strength = smoothstep_array(side_inner, side_outer, far_distance)
    upper_gate = 1.0 - smoothstep_array(jaw_y + 0.02 * face_height, neck_y + 0.12 * face_height, y_coords)
    shell_strength = float(np.clip(0.18 + 0.24 * side_factor, 0.18, 0.42))
    shell_gain = 1.0 - shell_strength * upper_gate[:, None] * far_strength[None, :]
    return np.clip(shell_gain.astype(np.float32), 0.48, 1.0)


def suppress_frontal_lateral_spikes(
    user_row: dict[str, Any],
    roi: tuple[int, int, int, int],
    effective_alpha: np.ndarray,
) -> np.ndarray:
    pose = user_row.get("pose", {})
    yaw_value = abs(float(pose.get("yaw_1deg", 0.0)))
    roll_value = abs(float(pose.get("roll_1deg", 0.0)))
    if yaw_value > 10.0 or roll_value > 8.0:
        return effective_alpha

    alpha_mask = effective_alpha > 0.02
    if np.count_nonzero(alpha_mask) <= 0:
        return effective_alpha

    anchors = user_row.get("anchors", {})
    face_bbox = user_row.get("face_bbox", {})
    face_width = max(
        1.0,
        float(face_bbox.get("w", 0.0))
        or abs(float(anchors["right_temple"]["x"]) - float(anchors["left_temple"]["x"])),
    )
    face_center_x = (
        float(anchors["left_temple"]["x"])
        + float(anchors["right_temple"]["x"])
        + float(anchors["lower_left"]["x"])
        + float(anchors["lower_right"]["x"])
        + float(anchors["forehead_center"]["x"])
    ) / 5.0
    local_center_x = float(np.clip(face_center_x - float(roi[0]), 0.0, max(0.0, float(effective_alpha.shape[1] - 1))))
    feather = max(12, int(round(face_width * 0.05)))
    gain_mask = np.ones_like(effective_alpha, dtype=np.float32)

    for row_index in range(effective_alpha.shape[0]):
        row_mask = alpha_mask[row_index]
        if not np.any(row_mask):
            continue
        row_pixels = np.flatnonzero(row_mask)
        left_edge = float(row_pixels[0])
        right_edge = float(row_pixels[-1])
        left_extent = local_center_x - left_edge
        right_extent = right_edge - local_center_x
        vertical_factor = row_index / max(1, effective_alpha.shape[0] - 1)
        tolerance = 6.0 + face_width * (0.10 + 0.34 * (vertical_factor ** 1.7))

        if right_extent > left_extent + tolerance:
            allowed_right = local_center_x + left_extent + tolerance
            if right_edge - allowed_right > feather * 0.75:
                ramp_start = max(0, int(np.floor(allowed_right)) - feather)
                ramp_end = min(effective_alpha.shape[1], int(np.ceil(right_edge)) + 1)
                coords = np.arange(ramp_start, ramp_end, dtype=np.float32)
                row_gain = np.clip((allowed_right + feather - coords) / max(1.0, float(feather)), 0.0, 1.0)
                gain_mask[row_index, ramp_start:ramp_end] = np.minimum(gain_mask[row_index, ramp_start:ramp_end], row_gain)
        elif left_extent > right_extent + tolerance:
            allowed_left = local_center_x - right_extent - tolerance
            if allowed_left - left_edge > feather * 0.75:
                ramp_start = max(0, int(np.floor(left_edge)))
                ramp_end = min(effective_alpha.shape[1], int(np.ceil(allowed_left)) + feather + 1)
                coords = np.arange(ramp_start, ramp_end, dtype=np.float32)
                row_gain = np.clip((coords - (allowed_left - feather)) / max(1.0, float(feather)), 0.0, 1.0)
                gain_mask[row_index, ramp_start:ramp_end] = np.minimum(gain_mask[row_index, ramp_start:ramp_end], row_gain)

    suppressed_fraction = float(np.mean(gain_mask < 0.999))
    if suppressed_fraction <= 0.0:
        return effective_alpha
    if suppressed_fraction > 0.18:
        return effective_alpha
    return np.clip(effective_alpha * gain_mask, 0.0, 1.0)


def mesh_v3_requires_silhouette_fallback(
    user_row: dict[str, Any],
    roi: tuple[int, int, int, int],
    effective_alpha: np.ndarray,
) -> bool:
    pose = user_row.get("pose", {})
    yaw_value = abs(float(pose.get("yaw_1deg", 0.0)))
    roll_value = abs(float(pose.get("roll_1deg", 0.0)))
    if yaw_value > 22.0 or roll_value > 12.0:
        return False

    alpha_mask = effective_alpha > 0.02
    if np.count_nonzero(alpha_mask) <= 0:
        return False

    anchors = user_row.get("anchors", {})
    face_bbox = user_row.get("face_bbox", {})
    face_width = max(
        1.0,
        float(face_bbox.get("w", 0.0))
        or abs(float(anchors["right_temple"]["x"]) - float(anchors["left_temple"]["x"])),
    )
    face_height = max(
        1.0,
        float(face_bbox.get("h", 0.0))
        or abs(float(anchors["neck_left"]["y"]) - float(anchors["crown"]["y"])),
    )
    face_center_x = (
        float(anchors["left_temple"]["x"])
        + float(anchors["right_temple"]["x"])
        + float(anchors["lower_left"]["x"])
        + float(anchors["lower_right"]["x"])
        + float(anchors["forehead_center"]["x"])
    ) / 5.0
    local_center_x = float(np.clip(face_center_x - float(roi[0]), 0.0, max(0.0, float(effective_alpha.shape[1] - 1))))
    crown_local_y = int(np.clip(round(float(anchors["crown"]["y"]) - float(roi[1])), 0, max(0, effective_alpha.shape[0] - 1)))
    jaw_y = 0.5 * (float(anchors["lower_left"]["y"]) + float(anchors["lower_right"]["y"]))
    jaw_local_y = int(np.clip(round(jaw_y - float(roi[1]) + 0.08 * face_height), 0, effective_alpha.shape[0]))
    if jaw_local_y - crown_local_y < max(8, int(round(face_height * 0.14))):
        return False

    severe_rows = 0
    sampled_rows = 0
    extreme_extent = max(10.0, face_width * 0.62)
    asym_gap = max(8.0, face_width * 0.14)
    for row_index in range(crown_local_y, jaw_local_y):
        row_mask = alpha_mask[row_index]
        if not np.any(row_mask):
            continue
        row_pixels = np.flatnonzero(row_mask)
        if row_pixels.size < 6:
            continue
        sampled_rows += 1
        left_extent = local_center_x - float(row_pixels[0])
        right_extent = float(row_pixels[-1]) - local_center_x
        larger_extent = max(left_extent, right_extent)
        smaller_extent = min(left_extent, right_extent)
        if larger_extent > extreme_extent and larger_extent > smaller_extent + asym_gap:
            severe_rows += 1

    if sampled_rows >= 10 and (severe_rows / sampled_rows) >= 0.16:
        return True

    if yaw_value <= 14.0:
        dst_x0, dst_y0, _, _ = roi
        y_coords = np.arange(dst_y0, dst_y0 + effective_alpha.shape[0], dtype=np.float32)
        x_coords = np.arange(dst_x0, dst_x0 + effective_alpha.shape[1], dtype=np.float32)
        forehead_y = float(anchors["forehead_center"]["y"])
        head_center_y = forehead_y + 0.10 * face_height
        side_radius = max(16.0, face_width * 0.58)
        top_radius = max(20.0, max(forehead_y - float(anchors["crown"]["y"]), 0.14 * face_height) + 0.56 * face_height)
        ellipse_distance = (
            ((x_coords - face_center_x) / side_radius) ** 2
            + ((y_coords[:, None] - head_center_y) / top_radius) ** 2
        )
        upper_mask = (y_coords[:, None] <= (jaw_y + 0.04 * face_height))
        frontal_shell_mask = upper_mask & alpha_mask
        frontal_shell_pixels = int(np.count_nonzero(frontal_shell_mask))
        if frontal_shell_pixels >= max(48, int(round(face_width * 0.18))):
            outside_shell = frontal_shell_mask & (ellipse_distance > 1.06)
            outside_fraction = float(np.count_nonzero(outside_shell)) / float(frontal_shell_pixels)
            if outside_fraction >= 0.12:
                return True

    return False


def composite_effective_layer(
    result_image: np.ndarray,
    roi: tuple[int, int, int, int] | None,
    warped_rgb: np.ndarray,
    effective_alpha: np.ndarray,
) -> np.ndarray:
    if roi is None:
        return result_image

    dst_x0, dst_y0, dst_x1, dst_y1 = roi
    user_roi = result_image[dst_y0:dst_y1, dst_x0:dst_x1].astype(np.float32)
    user_roi *= (1.0 - 0.10 * effective_alpha[..., None])
    blended_roi = warped_rgb.astype(np.float32) * effective_alpha[..., None] + user_roi * (1.0 - effective_alpha[..., None])
    result_image[dst_y0:dst_y1, dst_x0:dst_x1] = np.clip(blended_roi, 0, 255).astype(np.uint8)
    return result_image


def composite_overlay_roi(
    result_image: np.ndarray,
    roi: tuple[int, int, int, int] | None,
    warped_rgb: np.ndarray,
    warped_alpha: np.ndarray,
    warped_hair: np.ndarray,
) -> np.ndarray:
    effective_alpha = build_effective_alpha(warped_alpha, warped_hair)
    return composite_effective_layer(result_image, roi, warped_rgb, effective_alpha)


def build_legacy_overlay_layer(
    user_row: dict[str, Any],
    user_image: np.ndarray,
    asset_bundle: dict[str, Any],
    user_mask_bundle: dict[str, Any] | None = None,
    debug_payload: dict[str, object] | None = None,
) -> dict[str, Any] | None:
    started_at = time.perf_counter()
    asset_image = asset_bundle["image"]
    asset_alpha = asset_bundle["alpha"]
    asset_hair = asset_bundle["hair_mask"]
    asset_anchors = asset_bundle["anchors"]
    src_x0, src_y0, src_x1, src_y1 = asset_bundle["crop_box"]

    height, width = user_image.shape[:2]
    setup_started_at = time.perf_counter()
    matrix = estimate_transform(asset_anchors, user_row["anchors"])
    head_size_scale, head_scale_pivot = compute_conservative_head_size_scale(
        user_row,
        user_mask_bundle,
        (height, width),
    )
    matrix = _scaled_affine_about_pivot(matrix, head_size_scale, head_scale_pivot)
    matrix, aux_refine_debug = _refine_legacy_transform_with_aux_anchors(
        matrix,
        asset_anchors,
        user_row["anchors"],
        face_bbox=user_row.get("face_bbox"),
        pose=user_row.get("pose"),
    )
    src_corners = np.array(
        [
            [src_x0, src_y0],
            [src_x1, src_y0],
            [src_x1, src_y1],
            [src_x0, src_y1],
        ],
        dtype=np.float32,
    )
    dst_corners = transform_points(matrix, src_corners)
    dst_margin = render_roi_margin(src_x1 - src_x0, src_y1 - src_y0)
    roi = clamp_roi(
        int(np.floor(dst_corners[:, 0].min())) - dst_margin,
        int(np.floor(dst_corners[:, 1].min())) - dst_margin,
        int(np.ceil(dst_corners[:, 0].max())) + dst_margin,
        int(np.ceil(dst_corners[:, 1].max())) + dst_margin,
        width,
        height,
    )
    if roi is None:
        return None
    roi_setup_ms = round((time.perf_counter() - setup_started_at) * 1000.0, 3)

    dst_x0, dst_y0, dst_x1, dst_y1 = roi
    roi_width = dst_x1 - dst_x0
    roi_height = dst_y1 - dst_y0
    if bool(asset_bundle.get("_legacy_static_sources_ready")):
        src_rgb = asset_bundle["_legacy_src_rgb"]
        src_alpha = asset_bundle["_legacy_src_alpha"]
        src_hair = asset_bundle["_legacy_src_hair"]
        src_face = asset_bundle["_legacy_src_face"]
        src_protect_face = asset_bundle["_legacy_src_protect_face"]
        src_mask_stack = asset_bundle["_legacy_src_mask_stack"]
    else:
        if bool(asset_bundle.get("packed_crop_only")):
            src_rgb = asset_image
            src_alpha = asset_alpha
            src_hair = asset_hair
            src_face = asset_bundle["face_mask"]
            src_protect_face = asset_bundle["protect_face_mask"]
        else:
            src_rgb = asset_image[src_y0:src_y1, src_x0:src_x1]
            src_alpha = asset_alpha[src_y0:src_y1, src_x0:src_x1]
            src_hair = asset_hair[src_y0:src_y1, src_x0:src_x1]
            src_face = asset_bundle["face_mask"][src_y0:src_y1, src_x0:src_x1]
            src_protect_face = asset_bundle["protect_face_mask"][src_y0:src_y1, src_x0:src_x1]
        src_mask_stack = np.dstack([src_face, src_protect_face])
        asset_bundle["_legacy_src_rgb"] = src_rgb
        asset_bundle["_legacy_src_alpha"] = src_alpha
        asset_bundle["_legacy_src_hair"] = src_hair
        asset_bundle["_legacy_src_face"] = src_face
        asset_bundle["_legacy_src_protect_face"] = src_protect_face
        asset_bundle["_legacy_src_mask_stack"] = src_mask_stack
        asset_bundle["_legacy_static_sources_ready"] = True
    roi_matrix = roi_affine_from_crop(matrix, src_x0, src_y0, dst_x0, dst_y0)
    with _LEGACY_GPU_CACHE_LOCK:
        if bool(asset_bundle.get("_legacy_gpu_upload_ready")):
            gpu_src_rgb = asset_bundle.get("_legacy_gpu_src_rgb")
            gpu_src_alpha = asset_bundle.get("_legacy_gpu_src_alpha")
            gpu_src_hair = asset_bundle.get("_legacy_gpu_src_hair")
            gpu_src_mask_stack = asset_bundle.get("_legacy_gpu_src_mask_stack")
        else:
            gpu_src_rgb = opencv_cuda_upload(src_rgb, min_pixels=16_384)
            gpu_src_alpha = opencv_cuda_upload(src_alpha, min_pixels=16_384)
            gpu_src_hair = opencv_cuda_upload(src_hair, min_pixels=16_384)
            gpu_src_mask_stack = opencv_cuda_upload(src_mask_stack, min_pixels=16_384)
            asset_bundle["_legacy_gpu_src_rgb"] = gpu_src_rgb
            asset_bundle["_legacy_gpu_src_alpha"] = gpu_src_alpha
            asset_bundle["_legacy_gpu_src_hair"] = gpu_src_hair
            asset_bundle["_legacy_gpu_src_mask_stack"] = gpu_src_mask_stack
            asset_bundle["_legacy_gpu_upload_ready"] = True
    warp_rgb_started_at = time.perf_counter()
    warped_rgb_gpu = opencv_warp_affine_uploaded(
        gpu_src_rgb,
        roi_matrix,
        (roi_width, roi_height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
    )
    if warped_rgb_gpu is not None:
        warped_rgb = opencv_cuda_download(warped_rgb_gpu)
    else:
        warped_rgb = opencv_warp_affine(
            src_rgb,
            roi_matrix,
            (roi_width, roi_height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            min_pixels=16_384,
        )
    warp_rgb_ms = round((time.perf_counter() - warp_rgb_started_at) * 1000.0, 3)
    warp_alpha_started_at = time.perf_counter()
    warped_alpha_gpu = opencv_warp_affine_uploaded(
        gpu_src_alpha,
        roi_matrix,
        (roi_width, roi_height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
    )
    if warped_alpha_gpu is not None:
        warped_alpha = opencv_cuda_download(warped_alpha_gpu)
    else:
        warped_alpha = opencv_warp_affine(
            src_alpha,
            roi_matrix,
            (roi_width, roi_height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            min_pixels=16_384,
        )
    warp_alpha_ms = round((time.perf_counter() - warp_alpha_started_at) * 1000.0, 3)
    warp_hair_started_at = time.perf_counter()
    warped_hair_gpu = opencv_warp_affine_uploaded(
        gpu_src_hair,
        roi_matrix,
        (roi_width, roi_height),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
    )
    if warped_hair_gpu is not None:
        warped_hair = opencv_cuda_download(warped_hair_gpu)
    else:
        warped_hair = opencv_warp_affine(
            src_hair,
            roi_matrix,
            (roi_width, roi_height),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            min_pixels=16_384,
        )
    warp_hair_ms = round((time.perf_counter() - warp_hair_started_at) * 1000.0, 3)
    warp_masks_started_at = time.perf_counter()
    warped_mask_stack_gpu = opencv_warp_affine_uploaded(
        gpu_src_mask_stack,
        roi_matrix,
        (roi_width, roi_height),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
    )
    if warped_mask_stack_gpu is not None:
        warped_mask_stack = opencv_cuda_download(warped_mask_stack_gpu)
        if warped_mask_stack.ndim == 2:
            warped_mask_stack = warped_mask_stack[:, :, None]
        warped_face = warped_mask_stack[:, :, 0]
        warped_protect_face = warped_mask_stack[:, :, 1] if warped_mask_stack.shape[2] > 1 else np.zeros_like(warped_face)
    else:
        warped_face, warped_protect_face = _warp_mask_stack(
            [src_face, src_protect_face],
            roi_matrix,
            (roi_width, roi_height),
            min_pixels=16_384,
        )
    warp_masks_ms = round((time.perf_counter() - warp_masks_started_at) * 1000.0, 3)
    rgb_gain = resolve_hair_tone_gain(user_row, asset_bundle.get("hair_luma"))
    rgb_gain_started_at = time.perf_counter()
    warped_rgb = apply_masked_rgb_gain(warped_rgb, warped_hair, rgb_gain)
    rgb_gain_ms = round((time.perf_counter() - rgb_gain_started_at) * 1000.0, 3)
    hard_coverage = np.where(
        np.maximum(warped_alpha, warped_hair) >= 24,
        np.uint8(255),
        np.uint8(0),
    )
    effective_alpha_started_at = time.perf_counter()
    effective_alpha = build_effective_alpha(
        warped_alpha,
        warped_hair,
        soft_sigma=1.45,
        hair_sigma=1.65,
    )
    effective_alpha_ms = round((time.perf_counter() - effective_alpha_started_at) * 1000.0, 3)
    skin_suppression_started_at = time.perf_counter()
    effective_alpha = apply_asset_skin_suppression_gain(
        user_row,
        roi,
        effective_alpha,
        warped_face,
        warped_protect_face,
        None,
        None,
        include_ears=False,
        prefer_protect_face_only=True,
        layer_sigma_scale=0.72,
    )
    skin_suppression_ms = round((time.perf_counter() - skin_suppression_started_at) * 1000.0, 3)
    if debug_payload is not None:
        debug_payload.update(
            {
                "roi_setup_ms": roi_setup_ms,
                "aux_anchor_refine": aux_refine_debug or {},
                "warp_rgb_ms": warp_rgb_ms,
                "warp_alpha_ms": warp_alpha_ms,
                "warp_hair_ms": warp_hair_ms,
                "warp_masks_ms": warp_masks_ms,
                "rgb_gain_ms": rgb_gain_ms,
                "effective_alpha_ms": effective_alpha_ms,
                "skin_suppression_ms": skin_suppression_ms,
                "legacy_layer_total_ms": round((time.perf_counter() - started_at) * 1000.0, 3),
            }
        )
    return {
        "roi": roi,
        "rgb": np.clip(warped_rgb, 0.0, 255.0).astype(np.uint8),
        "alpha": effective_alpha,
        "coverage": hard_coverage,
        "render_kind": "legacy",
    }


def _legacy_layer_coverage_mask(
    layer: dict[str, Any] | None,
    frame_shape: tuple[int, int],
) -> np.ndarray | None:
    if not isinstance(layer, dict):
        return None
    roi = layer.get("roi")
    alpha = layer.get("alpha")
    coverage = layer.get("coverage")
    if (
        not isinstance(roi, tuple)
        or len(roi) != 4
        or frame_shape[0] <= 0
        or frame_shape[1] <= 0
    ):
        return None

    x0, y0, x1, y1 = (int(roi[0]), int(roi[1]), int(roi[2]), int(roi[3]))
    if x1 <= x0 or y1 <= y0:
        return None

    if isinstance(coverage, np.ndarray) and coverage.ndim == 2 and coverage.shape[:2] == (y1 - y0, x1 - x0):
        coverage_roi = np.where(coverage > 0, np.uint8(255), np.uint8(0))
    elif isinstance(alpha, np.ndarray) and alpha.ndim == 2 and alpha.shape[:2] == (y1 - y0, x1 - x0):
        coverage_roi = np.where(alpha > 0.08, np.uint8(255), np.uint8(0))
    else:
        return None

    if int(np.count_nonzero(coverage_roi)) < 4:
        return None

    coverage_mask = np.zeros(frame_shape, dtype=np.uint8)
    coverage_mask[y0:y1, x0:x1] = coverage_roi
    return coverage_mask


def build_mesh_target_points(
    user_row: dict[str, Any],
    renderer_name: str,
) -> list[tuple[float, float]]:
    if renderer_name in {"mesh_v2", "mesh_v3", "mesh_v4"}:
        return [weighted_anchor_point(user_row["anchors"], weights) for _, weights in MESH_V2_CONTROL_POINT_SPECS]
    return [
        (float(user_row["anchors"][name]["x"]), float(user_row["anchors"][name]["y"]))
        for name in MESH_ANCHOR_NAMES
    ]


def build_mesh_overlay_layer(
    user_row: dict[str, Any],
    user_image: np.ndarray,
    asset_bundle: dict[str, Any],
    renderer_name: str,
    user_mask_bundle: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    dense_mesh_renderer = renderer_name in {"mesh_v2", "mesh_v3", "mesh_v4"}
    mesh_key = "mesh_v2" if dense_mesh_renderer else "mesh"
    source_points, mesh_triangles = _ensure_asset_bundle_mesh_geometry(asset_bundle, mesh_key)
    if not mesh_triangles:
        return build_legacy_overlay_layer(
            user_row,
            user_image,
            asset_bundle,
            user_mask_bundle=user_mask_bundle,
        )

    asset_image = asset_bundle["image"]
    asset_alpha = asset_bundle["alpha"]
    asset_hair = asset_bundle["hair_mask"]
    asset_anchors = asset_bundle["anchors"]
    src_x0, src_y0, src_x1, src_y1 = asset_bundle["crop_box"]
    src_rgb = asset_image[src_y0:src_y1, src_x0:src_x1]
    src_alpha = asset_alpha[src_y0:src_y1, src_x0:src_x1]
    src_hair = asset_hair[src_y0:src_y1, src_x0:src_x1]

    height, width = user_image.shape[:2]
    matrix = estimate_transform(asset_anchors, user_row["anchors"])
    head_size_scale, head_scale_pivot = compute_conservative_head_size_scale(
        user_row,
        user_mask_bundle,
        (height, width),
    )
    matrix = _scaled_affine_about_pivot(matrix, head_size_scale, head_scale_pivot)
    control_point_count = len(MESH_V2_CONTROL_POINT_SPECS) if dense_mesh_renderer else len(MESH_ANCHOR_NAMES)
    boundary_points = source_points[control_point_count:]
    boundary_points_array = np.float32(boundary_points)
    target_control_points = _scaled_points_about_pivot(
        np.float32(build_mesh_target_points(user_row, renderer_name)),
        head_size_scale,
        head_scale_pivot,
    )
    transformed_boundary = transform_points(
        matrix,
        boundary_points_array + np.float32([[src_x0, src_y0]]),
    )
    all_target_points = np.vstack([target_control_points, transformed_boundary])

    dst_margin = render_roi_margin(src_x1 - src_x0, src_y1 - src_y0)
    roi = clamp_roi(
        int(np.floor(all_target_points[:, 0].min())) - dst_margin,
        int(np.floor(all_target_points[:, 1].min())) - dst_margin,
        int(np.ceil(all_target_points[:, 0].max())) + dst_margin,
        int(np.ceil(all_target_points[:, 1].max())) + dst_margin,
        width,
        height,
    )
    if roi is None:
        return None

    dst_x0, dst_y0, dst_x1, dst_y1 = roi
    roi_width = dst_x1 - dst_x0
    roi_height = dst_y1 - dst_y0
    destination_points = [
        (float(x_value) - float(dst_x0), float(y_value) - float(dst_y0))
        for x_value, y_value in target_control_points
    ]
    destination_points.extend(
        [
            tuple(point)
            for point in (transformed_boundary - np.float32([[dst_x0, dst_y0]]))
        ]
    )

    if dense_mesh_renderer:
        distortion = mesh_distortion_metrics(source_points, destination_points, mesh_triangles)
        if (
            distortion["triangle_count"] < 20.0
            or distortion["p90_ratio"] > 4.6
            or distortion["extreme_fraction"] > 0.18
            or distortion["collapsed_fraction"] > 0.12
        ):
            legacy_layer = build_legacy_overlay_layer(
                user_row,
                user_image,
                asset_bundle,
                user_mask_bundle=user_mask_bundle,
            )
            if legacy_layer is not None:
                legacy_layer["render_kind"] = f"{renderer_name}_fallback_legacy"
                legacy_layer["fallback_reason"] = "distortion_guard"
            return legacy_layer

    warped_rgb = warp_mesh_layer(src_rgb, source_points, destination_points, mesh_triangles, (roi_width, roi_height), cv2.INTER_LINEAR)
    warped_alpha = warp_mesh_layer(src_alpha, source_points, destination_points, mesh_triangles, (roi_width, roi_height), cv2.INTER_LINEAR)
    warped_hair = warp_mesh_layer(src_hair, source_points, destination_points, mesh_triangles, (roi_width, roi_height), cv2.INTER_NEAREST)
    warped_rgb = np.clip(warped_rgb, 0.0, 255.0).astype(np.uint8)
    warped_alpha = np.clip(warped_alpha, 0.0, 255.0).astype(np.uint8)
    warped_hair = np.clip(warped_hair, 0.0, 255.0).astype(np.uint8)
    rgb_gain = resolve_hair_tone_gain(user_row, asset_bundle.get("hair_luma"))
    warped_rgb = apply_masked_rgb_gain(warped_rgb, warped_hair, rgb_gain)
    warped_face_mask = warp_cropped_mask_layer(
        asset_bundle.get("face_mask"),
        asset_bundle["crop_box"],
        source_points,
        destination_points,
        mesh_triangles,
        (roi_width, roi_height),
    )
    warped_protect_face_mask = warp_cropped_mask_layer(
        asset_bundle.get("protect_face_mask"),
        asset_bundle["crop_box"],
        source_points,
        destination_points,
        mesh_triangles,
        (roi_width, roi_height),
    )
    warped_ear_left_mask = warp_cropped_mask_layer(
        asset_bundle.get("ear_mask_left"),
        asset_bundle["crop_box"],
        source_points,
        destination_points,
        mesh_triangles,
        (roi_width, roi_height),
    )
    warped_ear_right_mask = warp_cropped_mask_layer(
        asset_bundle.get("ear_mask_right"),
        asset_bundle["crop_box"],
        source_points,
        destination_points,
        mesh_triangles,
        (roi_width, roi_height),
    )
    alpha_gain = None
    if renderer_name == "mesh_v2":
        alpha_gain = build_mesh_v2_alpha_gain(user_row, roi, (roi_height, roi_width))
    elif renderer_name in {"mesh_v3", "mesh_v4"}:
        alpha_gain = build_mesh_v3_alpha_gain(
            user_row,
            roi,
            (roi_height, roi_width),
            warp_cropped_mask_layer(
                asset_bundle.get("forehead_mask"),
                asset_bundle["crop_box"],
                source_points,
                destination_points,
                mesh_triangles,
                (roi_width, roi_height),
            ),
            warped_ear_left_mask,
            warped_ear_right_mask,
            warp_cropped_mask_layer(
                asset_bundle.get("neck_shoulder_mask"),
                asset_bundle["crop_box"],
                source_points,
                destination_points,
                mesh_triangles,
                (roi_width, roi_height),
            ),
        )
    effective_alpha = build_effective_alpha(
        warped_alpha,
        warped_hair,
        soft_sigma=1.6 if dense_mesh_renderer else 1.8,
        alpha_gain=alpha_gain,
    )
    effective_alpha = apply_asset_skin_suppression_gain(
        user_row,
        roi,
        effective_alpha,
        warped_face_mask,
        warped_protect_face_mask,
        warped_ear_left_mask,
        warped_ear_right_mask,
    )
    if renderer_name in {"mesh_v3", "mesh_v4"}:
        effective_alpha = apply_user_side_silhouette_gain(user_row, roi, effective_alpha, user_mask_bundle)
        effective_alpha = suppress_frontal_lateral_spikes(user_row, roi, effective_alpha)
        if renderer_name == "mesh_v4":
            effective_alpha = apply_user_mask_occlusion_gain(user_row, roi, effective_alpha, user_mask_bundle, strength_scale=1.0)
        else:
            effective_alpha = apply_user_mask_occlusion_gain(user_row, roi, effective_alpha, user_mask_bundle, strength_scale=0.58)
        if mesh_v3_requires_silhouette_fallback(user_row, roi, effective_alpha):
            legacy_layer = build_legacy_overlay_layer(
                user_row,
                user_image,
                asset_bundle,
                user_mask_bundle=user_mask_bundle,
            )
            if legacy_layer is not None:
                legacy_layer["render_kind"] = f"{renderer_name}_fallback_legacy"
                legacy_layer["fallback_reason"] = "silhouette_guard"
            return legacy_layer
    if dense_mesh_renderer:
        alpha_coverage = float(np.mean(effective_alpha > 0.015))
        if alpha_coverage < 0.01:
            legacy_layer = build_legacy_overlay_layer(
                user_row,
                user_image,
                asset_bundle,
                user_mask_bundle=user_mask_bundle,
            )
            if legacy_layer is not None:
                legacy_layer["render_kind"] = f"{renderer_name}_fallback_legacy"
                legacy_layer["fallback_reason"] = "alpha_guard"
            return legacy_layer
    return {
        "roi": roi,
        "rgb": warped_rgb,
        "alpha": effective_alpha,
        "render_kind": renderer_name,
    }


def blend_overlay_layers(
    user_image: np.ndarray,
    weighted_layers: list[tuple[dict[str, Any], float]],
) -> np.ndarray:
    if not weighted_layers:
        return user_image.copy()

    union_x0 = min(int(layer["roi"][0]) for layer, _ in weighted_layers)
    union_y0 = min(int(layer["roi"][1]) for layer, _ in weighted_layers)
    union_x1 = max(int(layer["roi"][2]) for layer, _ in weighted_layers)
    union_y1 = max(int(layer["roi"][3]) for layer, _ in weighted_layers)
    union_width = union_x1 - union_x0
    union_height = union_y1 - union_y0
    if union_width <= 0 or union_height <= 0:
        return user_image.copy()

    total_weight = sum(float(weight) for _, weight in weighted_layers)
    if total_weight <= 0.0:
        return user_image.copy()

    accum_rgb = np.zeros((union_height, union_width, 3), dtype=np.float32)
    accum_alpha = np.zeros((union_height, union_width), dtype=np.float32)
    for layer, weight in weighted_layers:
        normalized_weight = float(weight) / total_weight
        x0, y0, x1, y1 = layer["roi"]
        offset_x = int(x0) - union_x0
        offset_y = int(y0) - union_y0
        layer_rgb = layer["rgb"].astype(np.float32)
        layer_alpha = np.clip(layer["alpha"].astype(np.float32) * normalized_weight, 0.0, 1.0)
        view_rgb = accum_rgb[offset_y : offset_y + (y1 - y0), offset_x : offset_x + (x1 - x0)]
        view_alpha = accum_alpha[offset_y : offset_y + (y1 - y0), offset_x : offset_x + (x1 - x0)]
        view_rgb += layer_rgb * layer_alpha[..., None]
        view_alpha += layer_alpha

    final_alpha = np.clip(accum_alpha, 0.0, 1.0)
    color_denominator = np.maximum(accum_alpha[..., None], 1e-6)
    final_rgb = np.clip(accum_rgb / color_denominator, 0.0, 255.0)
    result = user_image.copy()
    return composite_effective_layer(result, (union_x0, union_y0, union_x1, union_y1), final_rgb.astype(np.uint8), final_alpha)


def compose_overlay_legacy_frame(
    user_row: dict[str, Any],
    user_image: np.ndarray,
    asset_row: dict[str, Any],
    asset_root: Path,
    user_mask_bundle: dict[str, Any] | None = None,
    debug_payload: dict[str, object] | None = None,
) -> np.ndarray:
    started_at = time.perf_counter()
    asset_load_started_at = time.perf_counter()
    asset_bundle = load_asset_bundle(str(asset_root), asset_row["metadata_path"], BUNDLE_PROFILE_LEGACY)
    asset_load_ms = round((time.perf_counter() - asset_load_started_at) * 1000.0, 3)
    layer_detail_ms: dict[str, object] = {}
    build_layer_started_at = time.perf_counter()
    layer = build_legacy_overlay_layer(
        user_row,
        user_image,
        asset_bundle,
        user_mask_bundle=user_mask_bundle,
        debug_payload=layer_detail_ms,
    )
    build_layer_ms = round((time.perf_counter() - build_layer_started_at) * 1000.0, 3)
    if layer is None:
        if debug_payload is not None:
            debug_payload.update(
                {
                    "asset_load_ms": asset_load_ms,
                    "build_layer_ms": build_layer_ms,
                    "composite_ms": 0.0,
                    "legacy_frame_total_ms": round((time.perf_counter() - started_at) * 1000.0, 3),
                    "legacy_layer_detail_ms": layer_detail_ms,
                    "layer_missing": True,
                }
            )
        return user_image.copy()
    composite_started_at = time.perf_counter()
    composed = composite_effective_layer(user_image.copy(), layer["roi"], layer["rgb"], layer["alpha"])
    composite_ms = round((time.perf_counter() - composite_started_at) * 1000.0, 3)
    coverage_mask = _legacy_layer_coverage_mask(layer, user_image.shape[:2])
    if debug_payload is not None:
        debug_payload.update(
            {
                "asset_load_ms": asset_load_ms,
                "build_layer_ms": build_layer_ms,
                "composite_ms": composite_ms,
                "legacy_frame_total_ms": round((time.perf_counter() - started_at) * 1000.0, 3),
                "legacy_layer_detail_ms": layer_detail_ms,
                "_coverage_mask": coverage_mask,
            }
        )
    return composed


def _compose_mesh_base_image(
    user_row: dict[str, Any],
    user_image: np.ndarray,
    renderer_name: str,
    user_mask_bundle: dict[str, Any] | None,
) -> np.ndarray:
    if renderer_name in {"mesh_v3", "mesh_v4"} and user_mask_bundle is not None:
        return apply_user_head_blur_underlay(
            user_image,
            user_row,
            user_mask_bundle,
            strength_scale=1.0 if renderer_name == "mesh_v4" else 0.56,
        )
    return user_image.copy()


def _build_mesh_weighted_layers(
    user_row: dict[str, Any],
    user_image: np.ndarray,
    active_assets: list[tuple[dict[str, Any], float]],
    asset_root: Path,
    renderer_name: str,
    user_mask_bundle: dict[str, Any] | None,
) -> list[tuple[dict[str, Any], float]]:
    weighted_layers: list[tuple[dict[str, Any], float]] = []
    asset_root_str = str(asset_root)
    for asset_row, weight in active_assets:
        asset_bundle = load_asset_bundle(asset_root_str, asset_row["metadata_path"], BUNDLE_PROFILE_MESH)
        layer = build_mesh_overlay_layer(
            user_row,
            user_image,
            asset_bundle,
            renderer_name=renderer_name,
            user_mask_bundle=user_mask_bundle,
        )
        if layer is None:
            continue
        weighted_layers.append((layer, float(weight)))
    return weighted_layers


def _compose_mesh_blend_frame_from_active_assets(
    user_row: dict[str, Any],
    user_image: np.ndarray,
    active_assets: list[tuple[dict[str, Any], float]],
    asset_root: Path,
    renderer_name: str,
    user_mask_bundle: dict[str, Any] | None,
    *,
    base_image: np.ndarray | None = None,
) -> np.ndarray:
    if not active_assets:
        return user_image.copy()
    weighted_layers = _build_mesh_weighted_layers(
        user_row,
        user_image,
        active_assets,
        asset_root,
        renderer_name,
        user_mask_bundle,
    )
    if not weighted_layers:
        return user_image.copy()
    resolved_base_image = (
        base_image
        if base_image is not None
        else _compose_mesh_base_image(user_row, user_image, renderer_name, user_mask_bundle)
    )
    if len(active_assets) == 1 and active_assets[0][1] >= 0.999 and len(weighted_layers) == 1:
        layer, _ = weighted_layers[0]
        return composite_effective_layer(resolved_base_image.copy(), layer["roi"], layer["rgb"], layer["alpha"])
    return blend_overlay_layers(resolved_base_image, weighted_layers)


def compose_overlay_mesh_frame(
    user_row: dict[str, Any],
    user_image: np.ndarray,
    asset_row: dict[str, Any],
    asset_root: Path,
    renderer_name: str = "mesh_v1",
    user_mask_bundle: dict[str, Any] | None = None,
) -> np.ndarray:
    return _compose_mesh_blend_frame_from_active_assets(
        user_row,
        user_image,
        [(asset_row, 1.0)],
        asset_root,
        renderer_name,
        user_mask_bundle,
    )


def compose_overlay_frame(
    user_row: dict[str, Any],
    user_image: np.ndarray,
    asset_row: dict[str, Any],
    asset_root: Path,
    renderer_name: str = DEFAULT_RENDERER,
    user_mask_bundle: dict[str, Any] | None = None,
    debug_payload: dict[str, object] | None = None,
) -> np.ndarray:
    resolved_renderer = normalize_renderer_name(renderer_name)
    if resolved_renderer in {"mesh_v1", "mesh_v2", "mesh_v3", "mesh_v4"}:
        return compose_overlay_mesh_frame(
            user_row,
            user_image,
            asset_row,
            asset_root,
            renderer_name=resolved_renderer,
            user_mask_bundle=user_mask_bundle,
        )
    return compose_overlay_legacy_frame(
        user_row,
        user_image,
        asset_row,
        asset_root,
        user_mask_bundle=user_mask_bundle,
        debug_payload=debug_payload,
    )


def compose_overlay_blend_frame(
    user_row: dict[str, Any],
    user_image: np.ndarray,
    weighted_assets: list[tuple[dict[str, Any], float]],
    asset_root: Path,
    renderer_name: str = DEFAULT_RENDERER,
    user_mask_bundle: dict[str, Any] | None = None,
    debug_payload: dict[str, object] | None = None,
) -> np.ndarray:
    started_at = time.perf_counter()
    resolved_renderer = normalize_renderer_name(renderer_name)
    active_assets = [(asset_row, float(weight)) for asset_row, weight in weighted_assets if float(weight) > 0.0]
    if not active_assets:
        return user_image.copy()
    if len(active_assets) == 1 and active_assets[0][1] >= 0.999:
        single_asset, _ = active_assets[0]
        single_asset_detail_ms: dict[str, object] = {}
        composed = compose_overlay_frame(
            user_row,
            user_image,
            single_asset,
            asset_root,
            renderer_name=resolved_renderer,
            user_mask_bundle=user_mask_bundle,
            debug_payload=single_asset_detail_ms,
        )
        coverage_mask = single_asset_detail_ms.pop("_coverage_mask", None)
        if debug_payload is not None:
            debug_payload.update(
                {
                    "blend_path": "single_asset_fast",
                    "asset_count": 1,
                    "single_asset_detail_ms": single_asset_detail_ms,
                    "overlay_blend_total_ms": round((time.perf_counter() - started_at) * 1000.0, 3),
                    "_coverage_mask": coverage_mask,
                }
            )
        return composed
    if resolved_renderer in {"mesh_v2", "mesh_v3", "mesh_v4"}:
        return _compose_mesh_blend_frame_from_active_assets(
            user_row,
            user_image,
            active_assets,
            asset_root,
            resolved_renderer,
            user_mask_bundle,
        )

    base = user_image.astype(np.float32)
    delta = np.zeros_like(base, dtype=np.float32)
    total_weight = sum(weight for _, weight in active_assets)
    if total_weight <= 0.0:
        return user_image.copy()
    accumulated_coverage_mask: np.ndarray | None = None

    for asset_row, weight in active_assets:
        normalized_weight = weight / total_weight
        asset_detail_ms: dict[str, object] = {}
        overlay_frame = compose_overlay_frame(
            user_row,
            user_image,
            asset_row,
            asset_root,
            renderer_name=resolved_renderer,
            user_mask_bundle=user_mask_bundle,
            debug_payload=asset_detail_ms,
        ).astype(np.float32)
        asset_coverage_mask = asset_detail_ms.pop("_coverage_mask", None)
        if isinstance(asset_coverage_mask, np.ndarray) and asset_coverage_mask.shape == user_image.shape[:2]:
            if accumulated_coverage_mask is None:
                accumulated_coverage_mask = np.array(asset_coverage_mask, copy=True)
            else:
                accumulated_coverage_mask = np.maximum(accumulated_coverage_mask, asset_coverage_mask)
        delta += (overlay_frame - base) * normalized_weight
    result = np.clip(base + delta, 0.0, 255.0).astype(np.uint8)
    if debug_payload is not None:
        debug_payload.update(
            {
                "blend_path": "multi_asset_delta",
                "asset_count": len(active_assets),
                "overlay_blend_total_ms": round((time.perf_counter() - started_at) * 1000.0, 3),
                "_coverage_mask": accumulated_coverage_mask,
            }
        )
    return result


def compose_overlay_transition_frames(
    user_row: dict[str, Any],
    user_image: np.ndarray,
    from_weighted_assets: list[tuple[dict[str, Any], float]],
    to_weighted_assets: list[tuple[dict[str, Any], float]],
    asset_root: Path,
    renderer_name: str = DEFAULT_RENDERER,
    user_mask_bundle: dict[str, Any] | None = None,
    debug_payload: dict[str, object] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    resolved_renderer = normalize_renderer_name(renderer_name)
    if resolved_renderer not in {"mesh_v2", "mesh_v3", "mesh_v4"}:
        from_detail_ms: dict[str, object] = {}
        to_detail_ms: dict[str, object] = {}
        from_frame = compose_overlay_blend_frame(
            user_row,
            user_image,
            from_weighted_assets,
            asset_root,
            renderer_name=resolved_renderer,
            user_mask_bundle=user_mask_bundle,
            debug_payload=from_detail_ms,
        )
        to_frame = compose_overlay_blend_frame(
            user_row,
            user_image,
            to_weighted_assets,
            asset_root,
            renderer_name=resolved_renderer,
            user_mask_bundle=user_mask_bundle,
            debug_payload=to_detail_ms,
        )
        if debug_payload is not None:
            from_coverage_mask = from_detail_ms.pop("_coverage_mask", None)
            to_coverage_mask = to_detail_ms.pop("_coverage_mask", None)
            coverage_mask = None
            if isinstance(from_coverage_mask, np.ndarray) and from_coverage_mask.shape == user_image.shape[:2]:
                coverage_mask = np.array(from_coverage_mask, copy=True)
            if isinstance(to_coverage_mask, np.ndarray) and to_coverage_mask.shape == user_image.shape[:2]:
                coverage_mask = (
                    np.array(to_coverage_mask, copy=True)
                    if coverage_mask is None
                    else np.maximum(coverage_mask, to_coverage_mask)
                )
            debug_payload.update(
                {
                    "from_blend_detail_ms": from_detail_ms,
                    "to_blend_detail_ms": to_detail_ms,
                    "_coverage_mask": coverage_mask,
                }
            )
        return (
            from_frame,
            to_frame,
        )

    shared_base_image = _compose_mesh_base_image(
        user_row,
        user_image,
        resolved_renderer,
        user_mask_bundle,
    )
    from_active_assets = [
        (asset_row, float(weight))
        for asset_row, weight in from_weighted_assets
        if float(weight) > 0.0
    ]
    to_active_assets = [
        (asset_row, float(weight))
        for asset_row, weight in to_weighted_assets
        if float(weight) > 0.0
    ]
    from_frame = _compose_mesh_blend_frame_from_active_assets(
        user_row,
        user_image,
        from_active_assets,
        asset_root,
        resolved_renderer,
        user_mask_bundle,
        base_image=shared_base_image,
    )
    to_frame = _compose_mesh_blend_frame_from_active_assets(
        user_row,
        user_image,
        to_active_assets,
        asset_root,
        resolved_renderer,
        user_mask_bundle,
        base_image=shared_base_image,
    )
    return from_frame, to_frame


def select_best_asset(user_row: dict[str, Any], asset_rows: list[dict[str, Any]]) -> tuple[dict[str, Any], float]:
    ranked_assets = select_best_assets(user_row, asset_rows, limit=1)
    if not ranked_assets:
        raise RuntimeError("No candidate assets available")
    return ranked_assets[0]


def run_overlay(
    user_row: dict[str, Any],
    asset_row: dict[str, Any],
    asset_root: Path,
    output_dir: Path,
    save_debug: bool,
    output_format: str,
    jpeg_quality: int,
    renderer_name: str,
    skip_image_write: bool,
) -> dict[str, Any]:
    user_image = cv2.imread(user_row["image_path"], cv2.IMREAD_COLOR)
    result = compose_overlay_frame(user_row, user_image, asset_row, asset_root, renderer_name=renderer_name)

    output_name = Path(user_row["file"]).stem + "__overlay" + output_suffix(output_format)
    output_path = output_dir / "outputs" / output_name
    if not skip_image_write:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), result, output_codec_params(output_format, jpeg_quality))

    debug_path = None
    if save_debug:
        debug = user_image.copy()
        cv2.putText(debug, f"asset={asset_row['asset_id']}", (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)
        cv2.putText(debug, f"score={user_row['_best_score']:.2f}", (8, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)
        overlay = cv2.addWeighted(debug, 0.55, result, 0.45, 0)
        debug_path = output_dir / "debug" / output_name
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(debug_path), overlay, output_codec_params(output_format, jpeg_quality))

    return {
        "user_file": user_row["file"],
        "user_image_path": user_row["image_path"],
        "output_path": None if skip_image_write else str(output_path),
        "debug_path": str(debug_path) if debug_path else None,
        "selected_asset_id": asset_row["asset_id"],
        "selected_pose_key": asset_row["pose_key"],
        "renderer": renderer_name,
        "score": user_row["_best_score"],
        "user_pose": user_row["pose"],
        "asset_pose": {
            "yaw_1deg": asset_row["yaw_1deg"],
            "pitch_1deg": asset_row["pitch_1deg"],
            "roll_1deg": asset_row["roll_1deg"],
        },
    }


def main() -> None:
    args = parse_args()
    asset_root = Path(args.asset_root).resolve()
    user_feature_json = Path(args.user_feature_json).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    asset_index = read_json(asset_root / "manifests" / "asset_index_v0.json")["items"]
    approved_assets = [row for row in asset_index if row.get("approved")]
    runtime_assets = build_runtime_asset_rows(asset_index)
    for row in runtime_assets:
        row["_bundle_key"] = row["metadata_path"]

    user_payload = read_json(user_feature_json)
    user_rows = [row for row in user_payload["items"] if row.get("ok")]
    if args.limit > 0:
        user_rows = user_rows[: args.limit]

    selection_counter: Counter[str] = Counter()
    results = []

    for user_row in user_rows:
        best_asset, best_score = select_best_asset(user_row, runtime_assets)
        selection_counter[best_asset["asset_id"]] += 1
        results.append(
            run_overlay(
                user_row,
                best_asset,
                asset_root,
                output_dir,
                args.save_debug,
                args.output_format,
                args.jpeg_quality,
                args.renderer,
                args.skip_image_write,
            )
        )

    summary = {
        "asset_root": str(asset_root),
        "user_feature_json": str(user_feature_json),
        "output_dir": str(output_dir),
        "renderer": args.renderer,
        "processed_user_frames": len(user_rows),
        "approved_assets": len(approved_assets),
        "runtime_assets": len(runtime_assets),
        "unique_selected_assets": len(selection_counter),
        "top_selected_assets": selection_counter.most_common(20),
        "average_score": round(sum(item["score"] for item in results) / len(results), 6) if results else None,
    }

    write_json(output_dir / "overlay_results.json", {"summary": summary, "items": results})
    write_json(output_dir / "overlay_summary.json", summary)


if __name__ == "__main__":
    main()
