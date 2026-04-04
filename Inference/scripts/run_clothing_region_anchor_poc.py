from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
import json
import sys
import time

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.face_tracking import ServerFaceTracker
from app.hair_segmentation import HairSegmenter

INPUT_PATH = REPO_ROOT / "artifacts" / "test_test.png"
FACE_MODEL_PATH = REPO_ROOT / "models" / "face_landmarker.task"
HAIR_MODEL_PATH = REPO_ROOT / "models" / "mediapipe" / "hair_segmenter.tflite"
OUT_MASK_PATH = REPO_ROOT / "artifacts" / "test_test_clothing_region_mask.png"
OUT_OVERLAY_PATH = REPO_ROOT / "artifacts" / "test_test_clothing_region_overlay.png"
OUT_DEBUG_PATH = REPO_ROOT / "artifacts" / "test_test_clothing_region_debug.png"
OUT_METRICS_PATH = REPO_ROOT / "artifacts" / "test_test_clothing_region_metrics.json"

DEFAULT_TUNING: dict[str, float] = {
    "shoulder_x_expand": 0.28,
    "shoulder_y_drop": 0.24,
    "lower_depth_face": 1.42,
    "lower_depth_shoulder": 0.92,
    "lateral_expand_face": 0.30,
    "lateral_expand_shoulder": 0.16,
    "outer_shoulder_drop_face": 0.05,
    "shoulder_peak_rise_face": 0.06,
    "neckline_drop_face": 0.14,
    "outer_expand_face": 0.18,
    "outer_expand_shoulder": 0.08,
    "inner_inset_face": 0.06,
    "inner_inset_shoulder": 0.03,
    "curve_power": 1.55,
}

PRESET_TUNINGS: dict[str, dict[str, float]] = {
    "1": {
        "shoulder_x_expand": 0.26,
        "shoulder_y_drop": 0.20,
        "outer_shoulder_drop_face": 0.02,
        "shoulder_peak_rise_face": 0.10,
        "neckline_drop_face": 0.24,
        "outer_expand_face": 0.10,
        "outer_expand_shoulder": 0.05,
        "inner_inset_face": 0.03,
        "inner_inset_shoulder": 0.01,
        "curve_power": 1.35,
    },
    "2": {
        "shoulder_x_expand": 0.24,
        "shoulder_y_drop": 0.18,
        "outer_shoulder_drop_face": 0.00,
        "shoulder_peak_rise_face": 0.12,
        "neckline_drop_face": 0.29,
        "outer_expand_face": 0.08,
        "outer_expand_shoulder": 0.04,
        "inner_inset_face": 0.02,
        "inner_inset_shoulder": 0.00,
        "curve_power": 1.15,
    },
    "3": {
        "shoulder_x_expand": 0.27,
        "shoulder_y_drop": 0.19,
        "outer_shoulder_drop_face": 0.01,
        "shoulder_peak_rise_face": 0.11,
        "neckline_drop_face": 0.25,
        "outer_expand_face": 0.12,
        "outer_expand_shoulder": 0.05,
        "inner_inset_face": 0.03,
        "inner_inset_shoulder": 0.01,
        "curve_power": 1.25,
    },
    "4": {
        "shoulder_x_expand": 0.23,
        "shoulder_y_drop": 0.17,
        "outer_shoulder_drop_face": 0.00,
        "shoulder_peak_rise_face": 0.14,
        "neckline_drop_face": 0.36,
        "outer_expand_face": 0.07,
        "outer_expand_shoulder": 0.03,
        "inner_inset_face": 0.01,
        "inner_inset_shoulder": 0.00,
        "curve_power": 1.05,
    },
    "5": {
        "shoulder_x_expand": 0.25,
        "shoulder_y_drop": 0.18,
        "outer_shoulder_drop_face": 0.01,
        "shoulder_peak_rise_face": 0.13,
        "neckline_drop_face": 0.33,
        "outer_expand_face": 0.09,
        "outer_expand_shoulder": 0.04,
        "inner_inset_face": 0.02,
        "inner_inset_shoulder": 0.00,
        "curve_power": 1.10,
    },
    "6": {
        "shoulder_x_expand": 0.26,
        "shoulder_y_drop": 0.18,
        "lower_depth_face": 1.45,
        "lower_depth_shoulder": 0.95,
        "lateral_expand_face": 0.52,
        "lateral_expand_shoulder": 0.34,
        "outer_shoulder_drop_face": 0.03,
        "shoulder_peak_rise_face": 0.12,
        "neckline_drop_face": 0.31,
        "outer_expand_face": 0.28,
        "outer_expand_shoulder": 0.14,
        "inner_inset_face": 0.02,
        "inner_inset_shoulder": 0.01,
        "curve_power": 1.12,
    },
    "7": {
        "shoulder_x_expand": 0.28,
        "shoulder_y_drop": 0.18,
        "lower_depth_face": 1.45,
        "lower_depth_shoulder": 0.95,
        "lateral_expand_face": 0.56,
        "lateral_expand_shoulder": 0.36,
        "outer_shoulder_drop_face": 0.03,
        "shoulder_peak_rise_face": 0.12,
        "neckline_drop_face": 0.31,
        "outer_expand_face": 0.34,
        "outer_expand_shoulder": 0.18,
        "inner_inset_face": 0.02,
        "inner_inset_shoulder": 0.01,
        "curve_power": 1.12,
    },
}


def _tuning_value(tuning: dict[str, float] | None, key: str) -> float:
    if tuning is None:
        return DEFAULT_TUNING[key]
    return float(tuning.get(key, DEFAULT_TUNING[key]))


def _anchor_xy(user_row: dict[str, object], name: str) -> tuple[float, float] | None:
    anchors = user_row.get("anchors")
    if not isinstance(anchors, dict):
        return None
    payload = anchors.get(name)
    if not isinstance(payload, dict):
        return None
    try:
        x_value = float(payload["x"])
        y_value = float(payload["y"])
    except (KeyError, TypeError, ValueError):
        return None
    if not np.isfinite(x_value) or not np.isfinite(y_value):
        return None
    return x_value, y_value


def _build_shoulder_points(
    user_row: dict[str, object],
    shape: tuple[int, int],
    tuning: dict[str, float] | None = None,
) -> tuple[np.ndarray, np.ndarray] | None:
    face_bbox = user_row.get("face_bbox")
    if not isinstance(face_bbox, dict):
        return None
    try:
        face_x = float(face_bbox["x"])
        face_y = float(face_bbox["y"])
        face_w = float(face_bbox["w"])
        face_h = float(face_bbox["h"])
    except (KeyError, TypeError, ValueError):
        return None
    if face_w <= 1.0 or face_h <= 1.0:
        return None

    lower_left = _anchor_xy(user_row, "lower_left")
    lower_right = _anchor_xy(user_row, "lower_right")
    neck_left = _anchor_xy(user_row, "neck_left")
    neck_right = _anchor_xy(user_row, "neck_right")
    if lower_left is None:
        lower_left = (face_x + face_w * 0.28, face_y + face_h * 0.95)
    if lower_right is None:
        lower_right = (face_x + face_w * 0.72, face_y + face_h * 0.95)
    if neck_left is None:
        neck_left = (lower_left[0], lower_left[1] + face_h * 0.22)
    if neck_right is None:
        neck_right = (lower_right[0], lower_right[1] + face_h * 0.22)

    frame_h, frame_w = shape
    left_shoulder = np.array(
        [
            np.clip(neck_left[0] - face_w * _tuning_value(tuning, "shoulder_x_expand"), 0.0, frame_w - 1.0),
            np.clip(neck_left[1] + face_h * _tuning_value(tuning, "shoulder_y_drop"), 0.0, frame_h - 1.0),
        ],
        dtype=np.float32,
    )
    right_shoulder = np.array(
        [
            np.clip(neck_right[0] + face_w * _tuning_value(tuning, "shoulder_x_expand"), 0.0, frame_w - 1.0),
            np.clip(neck_right[1] + face_h * _tuning_value(tuning, "shoulder_y_drop"), 0.0, frame_h - 1.0),
        ],
        dtype=np.float32,
    )
    return left_shoulder, right_shoulder


def _build_torso_polygon(
    user_row: dict[str, object],
    shape: tuple[int, int],
    tuning: dict[str, float] | None = None,
) -> np.ndarray | None:
    face_bbox = user_row.get("face_bbox")
    if not isinstance(face_bbox, dict):
        return None
    try:
        face_w = float(face_bbox["w"])
        face_h = float(face_bbox["h"])
    except (KeyError, TypeError, ValueError):
        return None
    shoulders = _build_shoulder_points(user_row, shape, tuning)
    if shoulders is None:
        return None

    frame_h, frame_w = shape
    left_shoulder, right_shoulder = shoulders
    shoulder_vec = right_shoulder - left_shoulder
    shoulder_len = max(1.0, float(np.linalg.norm(shoulder_vec)))
    shoulder_dir = shoulder_vec / shoulder_len
    down_normal = np.array([-shoulder_dir[1], shoulder_dir[0]], dtype=np.float32)
    if down_normal[1] < 0.0:
        down_normal *= -1.0

    neck_left = _anchor_xy(user_row, "neck_left")
    neck_right = _anchor_xy(user_row, "neck_right")
    if neck_left is None:
        neck_left = (left_shoulder[0] + face_w * 0.10, left_shoulder[1] - face_h * 0.18)
    if neck_right is None:
        neck_right = (right_shoulder[0] - face_w * 0.10, right_shoulder[1] - face_h * 0.18)
    neck_center = np.array(
        [
            (neck_left[0] + neck_right[0]) * 0.5,
            (neck_left[1] + neck_right[1]) * 0.5,
        ],
        dtype=np.float32,
    )

    lower_depth = max(
        face_h * _tuning_value(tuning, "lower_depth_face"),
        shoulder_len * _tuning_value(tuning, "lower_depth_shoulder"),
    )
    lateral_expand = max(
        face_w * _tuning_value(tuning, "lateral_expand_face"),
        shoulder_len * _tuning_value(tuning, "lateral_expand_shoulder"),
    )
    outer_shoulder_drop = max(face_h * _tuning_value(tuning, "outer_shoulder_drop_face"), 0.0)
    shoulder_peak_rise = max(face_h * _tuning_value(tuning, "shoulder_peak_rise_face"), 7.0)
    neckline_drop = max(face_h * _tuning_value(tuning, "neckline_drop_face"), 14.0)
    outer_expand = max(
        face_w * _tuning_value(tuning, "outer_expand_face"),
        shoulder_len * _tuning_value(tuning, "outer_expand_shoulder"),
    )
    inner_inset = max(
        face_w * _tuning_value(tuning, "inner_inset_face"),
        shoulder_len * _tuning_value(tuning, "inner_inset_shoulder"),
    )
    curve_power = max(0.85, _tuning_value(tuning, "curve_power"))

    bottom_left = left_shoulder + down_normal * lower_depth - shoulder_dir * lateral_expand
    bottom_right = right_shoulder + down_normal * lower_depth + shoulder_dir * lateral_expand
    bottom_left[0] = 0.0
    bottom_right[0] = float(frame_w - 1.0)

    outer_left = left_shoulder + down_normal * outer_shoulder_drop - shoulder_dir * outer_expand
    outer_right = right_shoulder + down_normal * outer_shoulder_drop + shoulder_dir * outer_expand
    left_peak = left_shoulder - down_normal * shoulder_peak_rise + shoulder_dir * inner_inset
    right_peak = right_shoulder - down_normal * shoulder_peak_rise - shoulder_dir * inner_inset
    neckline = neck_center + down_normal * neckline_drop

    top_curve_points: list[np.ndarray] = [outer_left, left_peak]
    for t_value in np.linspace(0.0, 1.0, 17)[1:-1]:
        base_point = ((1.0 - t_value) * left_peak) + (t_value * right_peak)
        depth = neckline_drop * (np.sin(np.pi * t_value) ** curve_power)
        curve_point = base_point + down_normal * depth
        top_curve_points.append(curve_point.astype(np.float32))
    top_curve_points.extend([right_peak, outer_right])

    polygon = np.vstack(
        [
            np.asarray(top_curve_points, dtype=np.float32),
            np.asarray([bottom_right, bottom_left], dtype=np.float32),
        ]
    )
    polygon[:, 0] = np.clip(polygon[:, 0], 0.0, frame_w - 1.0)
    polygon[:, 1] = np.clip(polygon[:, 1], 0.0, frame_h - 1.0)
    return np.round(polygon).astype(np.int32)


def _build_seed_masks(
    candidate_mask: np.ndarray,
    user_row: dict[str, object],
) -> tuple[list[np.ndarray], np.ndarray]:
    seed_masks: list[np.ndarray] = []
    combined_seed_mask = np.zeros_like(candidate_mask, dtype=np.uint8)
    polygon = _build_torso_polygon(user_row, candidate_mask.shape)
    shoulders = _build_shoulder_points(user_row, candidate_mask.shape)
    if polygon is None or shoulders is None:
        return seed_masks, combined_seed_mask

    left_shoulder, right_shoulder = shoulders
    shoulder_vec = right_shoulder - left_shoulder
    shoulder_len = max(1.0, float(np.linalg.norm(shoulder_vec)))
    shoulder_dir = shoulder_vec / shoulder_len
    down_normal = np.array([-shoulder_dir[1], shoulder_dir[0]], dtype=np.float32)
    if down_normal[1] < 0.0:
        down_normal *= -1.0

    face_bbox = user_row.get("face_bbox")
    if not isinstance(face_bbox, dict):
        return seed_masks, combined_seed_mask
    try:
        face_x = float(face_bbox["x"])
        face_y = float(face_bbox["y"])
        face_w = float(face_bbox["w"])
        face_h = float(face_bbox["h"])
    except (KeyError, TypeError, ValueError):
        return seed_masks, combined_seed_mask

    neck_left = _anchor_xy(user_row, "neck_left")
    neck_right = _anchor_xy(user_row, "neck_right")
    if neck_left is None:
        neck_left = (face_x + face_w * 0.38, face_y + face_h * 1.03)
    if neck_right is None:
        neck_right = (face_x + face_w * 0.62, face_y + face_h * 1.03)
    neck_center = np.array(
        [
            (neck_left[0] + neck_right[0]) * 0.5,
            (neck_left[1] + neck_right[1]) * 0.5,
        ],
        dtype=np.float32,
    )

    patch_specs = [
        (
            neck_center + down_normal * max(face_h * 0.18, 14.0),
            (
                max(12, int(round(face_w * 0.15))),
                max(10, int(round(face_h * 0.10))),
            ),
            0.0,
        ),
        (
            left_shoulder + down_normal * max(face_h * 0.12, 10.0) + shoulder_dir * max(face_w * 0.08, 8.0),
            (
                max(12, int(round(face_w * 0.14))),
                max(10, int(round(face_h * 0.09))),
            ),
            float(np.degrees(np.arctan2(shoulder_dir[1], shoulder_dir[0]))),
        ),
        (
            right_shoulder + down_normal * max(face_h * 0.12, 10.0) - shoulder_dir * max(face_w * 0.08, 8.0),
            (
                max(12, int(round(face_w * 0.14))),
                max(10, int(round(face_h * 0.09))),
            ),
            float(np.degrees(np.arctan2(shoulder_dir[1], shoulder_dir[0]))),
        ),
    ]

    for center, axes, angle in patch_specs:
        patch_mask = np.zeros_like(candidate_mask, dtype=np.uint8)
        cv2.ellipse(
            patch_mask,
            (int(round(float(center[0]))), int(round(float(center[1])))),
            axes,
            angle,
            0,
            360,
            255,
            -1,
            cv2.LINE_AA,
        )
        patch_mask = cv2.bitwise_and(patch_mask, candidate_mask)
        if int(np.count_nonzero(patch_mask)) < 24:
            continue
        seed_masks.append(patch_mask)
        combined_seed_mask = cv2.bitwise_or(combined_seed_mask, patch_mask)
    return seed_masks, combined_seed_mask


def _estimate_clothing_region(
    frame_bgr: np.ndarray,
    hair_mask: np.ndarray,
    user_row: dict[str, object],
    tuning: dict[str, float] | None = None,
) -> tuple[np.ndarray, dict[str, object]]:
    started_at = time.perf_counter()
    polygon = _build_torso_polygon(user_row, frame_bgr.shape[:2], tuning)
    if polygon is None:
        return np.zeros(frame_bgr.shape[:2], dtype=np.uint8), {"reason": "missing_polygon"}

    full_mask = np.zeros(frame_bgr.shape[:2], dtype=np.uint8)
    cv2.fillPoly(full_mask, [polygon.astype(np.int32)], 255)
    full_mask = cv2.morphologyEx(
        full_mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)),
        iterations=1,
    )

    elapsed_ms = round((time.perf_counter() - started_at) * 1000.0, 3)
    metrics = {
        "estimate_ms": elapsed_ms,
        "candidate_nonzero": int(np.count_nonzero(full_mask)),
        "seed_nonzero": 0,
        "mask_nonzero": int(np.count_nonzero(full_mask)),
        "seed_count": 0,
        "seed_median_bgr_like": [],
        "seed_models_lab": [],
        "seed_scale_lab": [],
        "polygon": polygon.astype(int).tolist(),
        "mode": "geometry_envelope",
    }
    return full_mask, metrics


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=INPUT_PATH)
    parser.add_argument("--output-prefix", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    input_path = args.input
    output_prefix = args.output_prefix
    if output_prefix is None:
        input_stem = input_path.stem.replace(" ", "_")
        output_prefix = REPO_ROOT / "artifacts" / f"{input_stem}_clothing_region"
    out_mask_path = Path(str(output_prefix) + "_mask.png")
    out_overlay_path = Path(str(output_prefix) + "_overlay.png")
    out_debug_path = Path(str(output_prefix) + "_debug.png")
    out_metrics_path = Path(str(output_prefix) + "_metrics.json")

    frame_bgr = cv2.imread(str(input_path), cv2.IMREAD_COLOR)
    if frame_bgr is None:
        raise FileNotFoundError(input_path)
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

    face_tracker = ServerFaceTracker(FACE_MODEL_PATH, delegate="gpu")
    hair_segmenter = HairSegmenter(HAIR_MODEL_PATH, delegate="gpu")
    claims = SimpleNamespace(apply_session_id="clothing-poc", hair_id=1)
    settings = SimpleNamespace(feature_schema_version=2, transform_version="pixel_v1")

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            def _run_tracking() -> tuple[object, float]:
                started_at = time.perf_counter()
                result = face_tracker.extract_tracking_result_from_rgb(
                    frame_rgb,
                    claims=claims,
                    settings=settings,
                    seq=1,
                    ts_ms=int(time.time() * 1000),
                    hair_id_override=1,
                    reference_face_bbox=None,
                )
                return result, round((time.perf_counter() - started_at) * 1000.0, 3)

            def _run_hair_seg() -> tuple[np.ndarray | None, float]:
                started_at = time.perf_counter()
                result = hair_segmenter.segment_hair_confidence_from_rgb(
                    frame_rgb,
                    timestamp_ms=int(time.time() * 1000),
                )
                return result, round((time.perf_counter() - started_at) * 1000.0, 3)

            tracking_future = executor.submit(_run_tracking)
            hair_future = executor.submit(_run_hair_seg)
            tracking_result, tracking_ms = tracking_future.result()
            hair_confidence, hair_segmentation_ms = hair_future.result()

        if tracking_result is None:
            raise RuntimeError("face tracking failed")
        if hair_confidence is None:
            raise RuntimeError("hair segmentation failed")

        hair_mask = np.where(hair_confidence >= 0.35, np.uint8(255), np.uint8(0))
        clothing_mask, clothing_metrics = _estimate_clothing_region(frame_bgr, hair_mask, tracking_result.user_row)
        stable_times_ms: list[float] = []
        for _ in range(5):
            started_at = time.perf_counter()
            clothing_mask, clothing_metrics = _estimate_clothing_region(frame_bgr, hair_mask, tracking_result.user_row)
            stable_times_ms.append(round((time.perf_counter() - started_at) * 1000.0, 3))

        overlay = frame_bgr.copy()
        overlay[clothing_mask > 0] = (
            overlay[clothing_mask > 0].astype(np.float32) * 0.5
            + np.array([0, 220, 255], dtype=np.float32) * 0.5
        ).astype(np.uint8)

        debug = overlay.copy()
        polygon = np.asarray(clothing_metrics.get("polygon") or [], dtype=np.int32)
        if polygon.size > 0:
            cv2.polylines(debug, [polygon], True, (0, 255, 255), 2, cv2.LINE_AA)

        cv2.imwrite(str(out_mask_path), clothing_mask)
        cv2.imwrite(str(out_overlay_path), overlay)
        cv2.imwrite(str(out_debug_path), debug)

        payload = {
            "input": str(input_path),
            "tracking_ms": tracking_ms,
            "hair_segmentation_ms": hair_segmentation_ms,
            "hair_mask_nonzero": int(np.count_nonzero(hair_mask)),
            "clothing_estimate_steady_avg_ms": round(float(sum(stable_times_ms) / max(1, len(stable_times_ms))), 3),
            "clothing_estimate_steady_p50_ms": round(float(sorted(stable_times_ms)[len(stable_times_ms) // 2]), 3),
            "clothing_estimate_steady_max_ms": round(float(max(stable_times_ms)), 3),
            **clothing_metrics,
        }
        out_metrics_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print(f"saved_mask={out_mask_path}")
        print(f"saved_overlay={out_overlay_path}")
        print(f"saved_debug={out_debug_path}")
    finally:
        face_tracker.close()
        hair_segmenter.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
