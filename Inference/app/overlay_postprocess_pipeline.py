from __future__ import annotations

import os
from typing import Any

import cv2
import numpy as np
from functools import lru_cache

from cv2_cuda_utils import (
    opencv_absdiff,
    opencv_bitwise_and,
    opencv_bitwise_not,
    opencv_bitwise_or,
    opencv_dilate,
    opencv_gaussian_blur,
)

def _outer_background_ring_px() -> int:
    raw_value = str(os.getenv("INFERENCE_OUTER_BACKGROUND_RING_PX", "5") or "5").strip()
    try:
        return max(0, int(raw_value))
    except ValueError:
        return 5


OUTER_BACKGROUND_RING_PX = _outer_background_ring_px()


def _as_mask(mask: object, shape: tuple[int, int]) -> np.ndarray | None:
    if not isinstance(mask, np.ndarray):
        return None
    if mask.shape != shape:
        return None
    return np.where(mask > 0, np.uint8(255), np.uint8(0))


@lru_cache(maxsize=8)
def _coord_grids(shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    frame_height, frame_width = shape
    x_coords = np.broadcast_to(
        np.arange(frame_width, dtype=np.float32)[None, :],
        (frame_height, frame_width),
    )
    y_coords = np.broadcast_to(
        np.arange(frame_height, dtype=np.float32)[:, None],
        (frame_height, frame_width),
    )
    return x_coords, y_coords


def _as_color(color: object) -> np.ndarray | None:
    if color is None:
        return None
    color_array = np.asarray(color, dtype=np.float32).reshape(-1)
    if color_array.size < 3 or not bool(np.all(np.isfinite(color_array[:3]))):
        return None
    return np.clip(color_array[:3], 0.0, 255.0).astype(np.float32)


def _anchor_xy(anchors: object, name: str) -> tuple[float, float] | None:
    if not isinstance(anchors, dict):
        return None
    point = anchors.get(name)
    if not isinstance(point, dict):
        return None
    try:
        x_value = float(point["x"])
        y_value = float(point["y"])
    except (KeyError, TypeError, ValueError):
        return None
    if not bool(np.isfinite(x_value) and np.isfinite(y_value)):
        return None
    return x_value, y_value


def _sample_patch_median_with_mask(
    frame_bgr: np.ndarray,
    valid_mask: np.ndarray,
    *,
    center_x: int,
    center_y: int,
    radius: int,
) -> np.ndarray | None:
    height, width = frame_bgr.shape[:2]
    if radius <= 0 or valid_mask.shape != (height, width):
        return None
    x0 = max(0, center_x - radius)
    y0 = max(0, center_y - radius)
    x1 = min(width, center_x + radius + 1)
    y1 = min(height, center_y + radius + 1)
    if x1 - x0 < 3 or y1 - y0 < 3:
        return None
    patch = frame_bgr[y0:y1, x0:x1]
    patch_mask = valid_mask[y0:y1, x0:x1] > 0
    if patch.size == 0 or int(np.count_nonzero(patch_mask)) < 12:
        return None
    return np.median(patch[patch_mask].reshape(-1, 3), axis=0).astype(np.float32)


def _build_external_background_mask(hair_mask: np.ndarray) -> np.ndarray:
    inverse_hair_mask = opencv_bitwise_not(hair_mask)
    label_count, labels = cv2.connectedComponents(inverse_hair_mask, connectivity=8)
    external_background_mask = np.zeros_like(hair_mask, dtype=np.uint8)
    if label_count <= 1:
        return external_background_mask
    border_labels = np.unique(
        np.concatenate(
            [
                labels[0, :],
                labels[-1, :],
                labels[:, 0],
                labels[:, -1],
            ]
        )
    )
    for label_index in border_labels:
        if int(label_index) <= 0:
            continue
        external_background_mask[labels == int(label_index)] = 255
    return external_background_mask


def _build_local_background_field(
    frame_bgr: np.ndarray,
    hair_mask: np.ndarray,
    candidate_mask: np.ndarray,
    *,
    fallback_color: np.ndarray,
    external_background_mask: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray] | None:
    active_cols = np.flatnonzero(np.any(candidate_mask > 0, axis=0))
    if active_cols.size == 0:
        return None

    if external_background_mask is None:
        external_background_mask = _build_external_background_mask(hair_mask)
    if int(np.count_nonzero(external_background_mask)) < 16:
        return None

    hair_x, hair_y, hair_w, hair_h = cv2.boundingRect(hair_mask)
    full_cols = np.arange(int(active_cols[0]), int(active_cols[-1]) + 1, dtype=np.int32)
    sample_y0 = max(0, hair_y - max(2, int(round(hair_h * 0.08))))
    sample_y1 = min(frame_bgr.shape[0], hair_y + hair_h + max(2, int(round(hair_h * 0.08))))
    left_background_mask = np.zeros_like(external_background_mask, dtype=np.uint8)
    right_background_mask = np.zeros_like(external_background_mask, dtype=np.uint8)
    if hair_x > 0:
        left_background_mask[sample_y0:sample_y1, :hair_x] = 255
    if hair_x + hair_w < frame_bgr.shape[1]:
        right_background_mask[sample_y0:sample_y1, hair_x + hair_w :] = 255
    left_background_mask = opencv_bitwise_and(left_background_mask, external_background_mask)
    right_background_mask = opencv_bitwise_and(right_background_mask, external_background_mask)

    left_pixels = frame_bgr[left_background_mask > 0]
    right_pixels = frame_bgr[right_background_mask > 0]
    if left_pixels.size == 0 and right_pixels.size == 0:
        return None
    left_color = (
        np.median(left_pixels.reshape(-1, 3), axis=0).astype(np.float32)
        if left_pixels.size > 0
        else fallback_color.astype(np.float32)
    )
    right_color = (
        np.median(right_pixels.reshape(-1, 3), axis=0).astype(np.float32)
        if right_pixels.size > 0
        else fallback_color.astype(np.float32)
    )
    if full_cols.size == 1:
        center_color = ((left_color + right_color) * 0.5).astype(np.float32)
        return full_cols, center_color[None, :]
    interpolated = np.empty((full_cols.size, 3), dtype=np.float32)
    for channel in range(3):
        interpolated[:, channel] = np.interp(
            full_cols.astype(np.float32),
            np.array([float(full_cols[0]), float(full_cols[-1])], dtype=np.float32),
            np.array([left_color[channel], right_color[channel]], dtype=np.float32),
        )
    return full_cols, np.clip(interpolated, 0.0, 255.0).astype(np.float32)


def _estimate_clothing_color(
    frame_bgr: np.ndarray,
    hair_mask: np.ndarray,
    user_row: dict[str, Any],
    *,
    face_protect_mask: np.ndarray | None = None,
) -> np.ndarray | None:
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

    anchors = user_row.get("anchors")
    lower_left = _anchor_xy(anchors, "lower_left")
    lower_right = _anchor_xy(anchors, "lower_right")
    neck_left = _anchor_xy(anchors, "neck_left")
    neck_right = _anchor_xy(anchors, "neck_right")
    if lower_left is None:
        lower_left = (face_x + face_w * 0.28, face_y + face_h * 0.95)
    if lower_right is None:
        lower_right = (face_x + face_w * 0.72, face_y + face_h * 0.95)
    if neck_left is None:
        neck_left = (lower_left[0], lower_left[1] + face_h * 0.22)
    if neck_right is None:
        neck_right = (lower_right[0], lower_right[1] + face_h * 0.22)

    valid_mask = opencv_bitwise_not(hair_mask)
    if face_protect_mask is not None:
        valid_mask = opencv_bitwise_and(valid_mask, opencv_bitwise_not(face_protect_mask))

    patch_radius = max(4, int(round(face_w * 0.075)))
    neck_center_x = (neck_left[0] + neck_right[0]) * 0.5
    neck_center_y = (neck_left[1] + neck_right[1]) * 0.5
    sample_points = [
        (
            int(round(neck_left[0] - face_w * 0.18)),
            int(round(neck_left[1] + face_h * 0.38)),
        ),
        (
            int(round(neck_center_x)),
            int(round(neck_center_y + face_h * 0.54)),
        ),
        (
            int(round(neck_right[0] + face_w * 0.18)),
            int(round(neck_right[1] + face_h * 0.38)),
        ),
    ]
    samples = [
        sample
        for sample in (
            _sample_patch_median_with_mask(
                frame_bgr,
                valid_mask,
                center_x=sample_x,
                center_y=sample_y,
                radius=patch_radius,
            )
            for sample_x, sample_y in sample_points
        )
        if sample is not None
    ]
    if not samples:
        return None
    return np.median(np.stack(samples, axis=0), axis=0).astype(np.float32)


def _estimate_shoulder_line_y(
    user_row: dict[str, Any],
    shape: tuple[int, int],
) -> np.ndarray | None:
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

    anchors = user_row.get("anchors")
    lower_left = _anchor_xy(anchors, "lower_left")
    lower_right = _anchor_xy(anchors, "lower_right")
    neck_left = _anchor_xy(anchors, "neck_left")
    neck_right = _anchor_xy(anchors, "neck_right")
    if lower_left is None:
        lower_left = (face_x + face_w * 0.28, face_y + face_h * 0.95)
    if lower_right is None:
        lower_right = (face_x + face_w * 0.72, face_y + face_h * 0.95)
    if neck_left is None:
        neck_left = (lower_left[0], lower_left[1] + face_h * 0.22)
    if neck_right is None:
        neck_right = (lower_right[0], lower_right[1] + face_h * 0.22)

    left_shoulder_x = float(neck_left[0] - face_w * 0.18)
    right_shoulder_x = float(neck_right[0] + face_w * 0.18)
    left_shoulder_y = float(neck_left[1] + face_h * 0.38)
    right_shoulder_y = float(neck_right[1] + face_h * 0.38)
    if right_shoulder_x - left_shoulder_x < 1.0:
        return None

    _, frame_width = shape
    x_values = np.arange(frame_width, dtype=np.float32)
    line_y = np.interp(
        x_values,
        np.array([left_shoulder_x, right_shoulder_x], dtype=np.float32),
        np.array([left_shoulder_y, right_shoulder_y], dtype=np.float32),
        left=left_shoulder_y,
        right=right_shoulder_y,
    )
    return line_y.astype(np.float32)


def _build_clothing_envelope_mask(
    user_row: dict[str, Any],
    shape: tuple[int, int],
    *,
    hair_mask: np.ndarray | None = None,
) -> np.ndarray | None:
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

    anchors = user_row.get("anchors")
    lower_left = _anchor_xy(anchors, "lower_left")
    lower_right = _anchor_xy(anchors, "lower_right")
    neck_left = _anchor_xy(anchors, "neck_left")
    neck_right = _anchor_xy(anchors, "neck_right")
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
            np.clip(neck_left[0] - face_w * 0.26, 0.0, frame_w - 1.0),
            np.clip(neck_left[1] + face_h * 0.18, 0.0, frame_h - 1.0),
        ],
        dtype=np.float32,
    )
    right_shoulder = np.array(
        [
            np.clip(neck_right[0] + face_w * 0.26, 0.0, frame_w - 1.0),
            np.clip(neck_right[1] + face_h * 0.18, 0.0, frame_h - 1.0),
        ],
        dtype=np.float32,
    )
    shoulder_vec = right_shoulder - left_shoulder
    shoulder_len = max(1.0, float(np.linalg.norm(shoulder_vec)))
    shoulder_dir = shoulder_vec / shoulder_len
    down_normal = np.array([-shoulder_dir[1], shoulder_dir[0]], dtype=np.float32)
    if down_normal[1] < 0.0:
        down_normal *= -1.0

    neck_center = np.array(
        [
            (neck_left[0] + neck_right[0]) * 0.5,
            (neck_left[1] + neck_right[1]) * 0.5,
        ],
        dtype=np.float32,
    )

    lower_depth = max(face_h * 1.45, shoulder_len * 0.95)
    lateral_expand = max(face_w * 0.52, shoulder_len * 0.34)
    neckline_drop = max(face_h * 0.31, 24.0)
    side_outer_drop = max(face_h * 0.20, 14.0)
    side_contact_outset = max(face_w * 0.06, 4.0)
    curve_power = 1.12

    bottom_left = left_shoulder + down_normal * lower_depth - shoulder_dir * lateral_expand
    bottom_right = right_shoulder + down_normal * lower_depth + shoulder_dir * lateral_expand
    bottom_left[0] = 0.0
    bottom_right[0] = float(frame_w - 1.0)
    neckline = neck_center + down_normal * neckline_drop
    left_neck = np.array(
        [neck_left[0], neck_left[1] + face_h * 0.04],
        dtype=np.float32,
    )
    right_neck = np.array(
        [neck_right[0], neck_right[1] + face_h * 0.04],
        dtype=np.float32,
    )

    def _find_side_contact(side: str) -> np.ndarray:
        fallback = (
            left_shoulder + down_normal * max(face_h * 0.05, 3.0) - shoulder_dir * max(face_w * 0.12, 6.0)
            if side == "left"
            else right_shoulder + down_normal * max(face_h * 0.05, 3.0) + shoulder_dir * max(face_w * 0.12, 6.0)
        )
        if hair_mask is None or hair_mask.shape != shape or int(np.count_nonzero(hair_mask)) < 24:
            return fallback.astype(np.float32)

        center_x = face_x + face_w * 0.5
        neck_point = neck_left if side == "left" else neck_right
        y0 = int(np.clip(round(neck_point[1] + face_h * 0.02), 0, frame_h - 1))
        y1 = int(np.clip(round(neck_point[1] + face_h * 0.42), 0, frame_h - 1))
        target_y = neck_point[1] + face_h * 0.18
        best_point: tuple[float, float] | None = None
        best_score: float | None = None
        for row in range(min(y0, y1), max(y0, y1) + 1):
            row_pixels = np.flatnonzero(hair_mask[row] > 0)
            if row_pixels.size == 0:
                continue
            if side == "left":
                side_pixels = row_pixels[row_pixels < center_x]
                if side_pixels.size == 0:
                    continue
                contact_x = float(np.min(side_pixels)) - side_contact_outset
                horizontal_gap = neck_point[0] - contact_x
            else:
                side_pixels = row_pixels[row_pixels > center_x]
                if side_pixels.size == 0:
                    continue
                contact_x = float(np.max(side_pixels)) + side_contact_outset
                horizontal_gap = contact_x - neck_point[0]
            if horizontal_gap < face_w * 0.10:
                continue
            contact_x = float(np.clip(contact_x, 0.0, frame_w - 1.0))
            score = abs(float(row) - float(target_y)) + horizontal_gap * 0.04
            if best_score is None or score < best_score:
                best_score = score
                best_point = (contact_x, float(row))
        if best_point is None:
            return fallback.astype(np.float32)
        return np.array(best_point, dtype=np.float32)

    left_contact = _find_side_contact("left")
    right_contact = _find_side_contact("right")
    left_outer = np.array([0.0, np.clip(left_contact[1] + side_outer_drop, 0.0, frame_h - 1.0)], dtype=np.float32)
    right_outer = np.array([float(frame_w - 1.0), np.clip(right_contact[1] + side_outer_drop, 0.0, frame_h - 1.0)], dtype=np.float32)

    top_curve_points: list[np.ndarray] = [left_outer, left_contact, left_neck]
    for t_value in np.linspace(0.0, 1.0, 17)[1:-1]:
        base_point = ((1.0 - t_value) * left_neck) + (t_value * right_neck)
        depth = neckline_drop * (np.sin(np.pi * t_value) ** curve_power)
        curve_point = base_point + down_normal * depth
        top_curve_points.append(curve_point.astype(np.float32))
    top_curve_points.extend([right_neck, right_contact, right_outer])

    polygon = np.vstack(
        [
            np.asarray(top_curve_points, dtype=np.float32),
            np.asarray([bottom_right, bottom_left], dtype=np.float32),
        ]
    )
    polygon[:, 0] = np.clip(polygon[:, 0], 0.0, frame_w - 1.0)
    polygon[:, 1] = np.clip(polygon[:, 1], 0.0, frame_h - 1.0)

    mask = np.zeros(shape, dtype=np.uint8)
    cv2.fillPoly(mask, [np.round(polygon).astype(np.int32)], 255)
    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)),
        iterations=1,
    )
    if int(np.count_nonzero(mask)) < 24:
        return None
    return mask


def _build_below_shoulder_mask(
    user_row: dict[str, Any],
    shape: tuple[int, int],
) -> np.ndarray | None:
    line_y = _estimate_shoulder_line_y(user_row, shape)
    if line_y is None:
        return None
    _, _ = shape
    _, y_coords = _coord_grids(shape)
    below_mask = np.where(y_coords >= line_y[None, :], np.uint8(255), np.uint8(0))
    return below_mask


def _build_local_clothing_field(
    frame_bgr: np.ndarray,
    hair_mask: np.ndarray,
    candidate_mask: np.ndarray,
    user_row: dict[str, Any],
    *,
    face_protect_mask: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray] | None:
    active_cols = np.flatnonzero(np.any(candidate_mask > 0, axis=0))
    if active_cols.size == 0:
        return None

    face_bbox = user_row.get("face_bbox")
    if not isinstance(face_bbox, dict):
        return None
    try:
        face_w = float(face_bbox["w"])
        face_h = float(face_bbox["h"])
    except (KeyError, TypeError, ValueError):
        return None
    if face_w <= 1.0 or face_h <= 1.0:
        return None

    line_y = _estimate_shoulder_line_y(user_row, frame_bgr.shape[:2])
    below_shoulder_mask = _build_below_shoulder_mask(user_row, frame_bgr.shape[:2])
    if line_y is None or below_shoulder_mask is None:
        return None

    sample_kernel_w = max(9, int(round(face_w * 0.28)))
    sample_kernel_h = max(11, int(round(face_h * 0.42)))
    if sample_kernel_w % 2 == 0:
        sample_kernel_w += 1
    if sample_kernel_h % 2 == 0:
        sample_kernel_h += 1
    search_mask = opencv_dilate(
        candidate_mask,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (sample_kernel_w, sample_kernel_h)),
        iterations=1,
        min_pixels=0,
    )
    valid_mask = opencv_bitwise_and(search_mask, opencv_bitwise_not(hair_mask))
    valid_mask = opencv_bitwise_and(valid_mask, below_shoulder_mask)
    if face_protect_mask is not None:
        valid_mask = opencv_bitwise_and(valid_mask, opencv_bitwise_not(face_protect_mask))

    if int(np.count_nonzero(valid_mask)) < 24:
        return None

    x, y, width, height = cv2.boundingRect(search_mask)
    if width < 3 or height < 3:
        return None

    full_cols = np.arange(x, x + width, dtype=np.int32)
    frame_roi = frame_bgr[y : y + height, x : x + width]
    valid_roi = valid_mask[y : y + height, x : x + width]
    if frame_roi.size == 0 or int(np.count_nonzero(valid_roi)) < 24:
        return None

    stripe_count = 5 if width >= 10 else 3
    stripe_edges = np.linspace(0, width, num=stripe_count + 1, dtype=np.int32)
    sampled_cols: list[int] = []
    sampled_colors: list[np.ndarray] = []

    for stripe_index in range(stripe_count):
        x0 = int(stripe_edges[stripe_index])
        x1 = int(stripe_edges[stripe_index + 1])
        if x1 - x0 < 2:
            continue
        patch = frame_roi[:, x0:x1]
        patch_mask = valid_roi[:, x0:x1] > 0
        if patch.size == 0 or int(np.count_nonzero(patch_mask)) < 12:
            continue
        sampled_cols.append(x + (x0 + x1 - 1) // 2)
        sampled_colors.append(np.median(patch[patch_mask].reshape(-1, 3), axis=0).astype(np.float32))

    if not sampled_cols:
        return None
    if len(sampled_cols) == 1:
        return np.array(sampled_cols, dtype=np.int32), np.asarray(sampled_colors, dtype=np.float32)

    sampled_cols_array = np.asarray(sampled_cols, dtype=np.int32)
    sampled_colors_array = np.asarray(sampled_colors, dtype=np.float32)
    interpolated = np.empty((full_cols.size, 3), dtype=np.float32)
    for channel in range(3):
        interpolated[:, channel] = np.interp(
            full_cols.astype(np.float32),
            sampled_cols_array.astype(np.float32),
            sampled_colors_array[:, channel],
        )
    return full_cols, np.clip(interpolated, 0.0, 255.0).astype(np.float32)


def _build_local_clothing_field_from_body_mask(
    frame_bgr: np.ndarray,
    hair_mask: np.ndarray,
    body_mask: np.ndarray,
    user_row: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray] | None:
    active_cols = np.flatnonzero(np.any(body_mask > 0, axis=0))
    if active_cols.size == 0:
        return None

    face_bbox = user_row.get("face_bbox")
    if not isinstance(face_bbox, dict):
        return None
    try:
        face_w = float(face_bbox["w"])
        face_h = float(face_bbox["h"])
    except (KeyError, TypeError, ValueError):
        return None
    if face_w <= 1.0 or face_h <= 1.0:
        return None

    line_y = _estimate_shoulder_line_y(user_row, frame_bgr.shape[:2])
    below_shoulder_mask = _build_below_shoulder_mask(user_row, frame_bgr.shape[:2])
    if line_y is None or below_shoulder_mask is None:
        return None

    body_below_mask = opencv_bitwise_and(body_mask, below_shoulder_mask)
    valid_mask = opencv_bitwise_and(body_below_mask, opencv_bitwise_not(hair_mask))
    if int(np.count_nonzero(valid_mask)) < 24:
        return None

    full_cols = np.arange(int(active_cols[0]), int(active_cols[-1]) + 1, dtype=np.int32)
    patch_radius = max(3, int(round(face_w * 0.045)))
    sample_top_offset = max(2.0, face_h * 0.10)
    sample_bottom_offset = max(sample_top_offset + 3.0, face_h * 0.90)
    sampled_cols: list[int] = []
    sampled_colors: list[np.ndarray] = []
    frame_height, frame_width = frame_bgr.shape[:2]

    for col in full_cols.tolist():
        center_x = int(col)
        center_y0 = int(np.clip(np.floor(line_y[center_x] + sample_top_offset), 0, frame_height - 1))
        center_y1 = int(np.clip(np.floor(line_y[center_x] + sample_bottom_offset), center_y0 + 1, frame_height))
        if center_y1 - center_y0 < 3:
            continue
        x0 = max(0, center_x - patch_radius)
        x1 = min(frame_width, center_x + patch_radius + 1)
        patch = frame_bgr[center_y0:center_y1, x0:x1]
        patch_mask = valid_mask[center_y0:center_y1, x0:x1] > 0
        if patch.size == 0 or int(np.count_nonzero(patch_mask)) < 12:
            continue
        sampled_cols.append(center_x)
        sampled_colors.append(np.median(patch[patch_mask].reshape(-1, 3), axis=0).astype(np.float32))

    if not sampled_cols:
        return None
    if len(sampled_cols) == 1:
        return np.array(sampled_cols, dtype=np.int32), np.asarray(sampled_colors, dtype=np.float32)

    sampled_cols_array = np.asarray(sampled_cols, dtype=np.int32)
    sampled_colors_array = np.asarray(sampled_colors, dtype=np.float32)
    interpolated = np.empty((full_cols.size, 3), dtype=np.float32)
    for channel in range(3):
        interpolated[:, channel] = np.interp(
            full_cols.astype(np.float32),
            sampled_cols_array.astype(np.float32),
            sampled_colors_array[:, channel],
        )
    return full_cols, np.clip(interpolated, 0.0, 255.0).astype(np.float32)


def prepare_clothing_cleanup_context(
    frame_bgr: np.ndarray,
    user_row: dict[str, Any],
    *,
    hair_mask: np.ndarray | None,
    body_mask: np.ndarray | None,
) -> dict[str, Any]:
    frame_shape = frame_bgr.shape[:2]
    resolved_body_mask = _as_mask(body_mask, frame_shape)
    resolved_hair_mask = _as_mask(hair_mask, frame_shape)
    below_shoulder_mask = _build_below_shoulder_mask(user_row, frame_shape)
    if resolved_hair_mask is None:
        resolved_hair_mask = np.zeros(frame_shape, dtype=np.uint8)

    geometry_clothing_mask = _build_clothing_envelope_mask(
        user_row,
        frame_shape,
        hair_mask=resolved_hair_mask,
    )
    if geometry_clothing_mask is None and (resolved_body_mask is None or int(np.count_nonzero(resolved_body_mask)) < 24):
        return {}

    if resolved_body_mask is not None and int(np.count_nonzero(resolved_body_mask)) >= 24:
        body_clothing_mask = (
            opencv_bitwise_and(resolved_body_mask, below_shoulder_mask)
            if below_shoulder_mask is not None
            else np.array(resolved_body_mask, copy=True)
        )
        person_body_mask = np.array(resolved_body_mask, copy=True)
    else:
        body_clothing_mask = np.array(geometry_clothing_mask, copy=True)
        # Only use person_body_mask when it comes from an actual body/person segmentation.
        # Geometry fallback is just a cleanup envelope and should not receive extra dilation.
        person_body_mask = None

    if int(np.count_nonzero(body_clothing_mask)) < 24:
        if geometry_clothing_mask is None:
            return {}
        body_clothing_mask = np.array(geometry_clothing_mask, copy=True)
        person_body_mask = None

    if int(np.count_nonzero(resolved_hair_mask)) < 24:
        return {}
    hair_x, hair_y, hair_w, hair_h = cv2.boundingRect(resolved_hair_mask)
    clothing_x, clothing_y, clothing_w, _ = cv2.boundingRect(body_clothing_mask)
    hair_bottom = hair_y + hair_h
    overlap_width = max(0, min(hair_x + hair_w, clothing_x + clothing_w) - max(hair_x, clothing_x))
    if overlap_width < max(6, int(round(clothing_w * 0.12))):
        return {}
    if hair_bottom < clothing_y + max(2, int(round(frame_shape[0] * 0.02))):
        return {}

    payload: dict[str, Any] = {
        "_body_clothing_mask": body_clothing_mask,
    }
    if person_body_mask is not None:
        payload["_person_body_mask"] = person_body_mask
    return payload


def _build_directional_outer_ring_gate(
    user_row: dict[str, Any],
    shape: tuple[int, int],
) -> np.ndarray | None:
    frame_height, frame_width = shape
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

    anchors = user_row.get("anchors")
    left_temple = _anchor_xy(anchors, "left_temple")
    right_temple = _anchor_xy(anchors, "right_temple")
    left_ear_root = _anchor_xy(anchors, "left_ear_root")
    right_ear_root = _anchor_xy(anchors, "right_ear_root")
    forehead_center = _anchor_xy(anchors, "forehead_center")
    crown = _anchor_xy(anchors, "crown")
    lower_left = _anchor_xy(anchors, "lower_left")
    lower_right = _anchor_xy(anchors, "lower_right")

    left_temple_x = left_temple[0] if left_temple is not None else face_x + face_w * 0.18
    right_temple_x = right_temple[0] if right_temple is not None else face_x + face_w * 0.82
    temple_y = (
        (left_temple[1] + right_temple[1]) * 0.5
        if left_temple is not None and right_temple is not None
        else face_y + face_h * 0.16
    )
    forehead_y = forehead_center[1] if forehead_center is not None else face_y
    crown_y = crown[1] if crown is not None else max(0.0, forehead_y - face_h * 0.22)
    jaw_y = (
        (lower_left[1] + lower_right[1]) * 0.5
        if lower_left is not None and lower_right is not None
        else face_y + face_h
    )

    def _side_bottom_y(ear_root: tuple[float, float] | None) -> float:
        if ear_root is None:
            return temple_y + face_h * 0.20
        # stop the side ring above the ear lobe to avoid sideburn/background over-cleanup
        return max(temple_y + max(1.0, face_h * 0.02), ear_root[1] - 5.0)

    left_side_bottom_y = min(jaw_y, _side_bottom_y(left_ear_root))
    right_side_bottom_y = min(jaw_y, _side_bottom_y(right_ear_root))

    x_coords, y_coords = _coord_grids(shape)

    top_gate = (
        (x_coords >= left_temple_x - face_w * 0.52)
        & (x_coords <= right_temple_x + face_w * 0.52)
        & (y_coords <= temple_y + face_h * 0.12)
    )
    left_side_gate = (
        (x_coords <= left_temple_x - face_w * 0.02)
        & (y_coords >= crown_y - face_h * 0.05)
        & (y_coords <= left_side_bottom_y)
    )
    right_side_gate = (
        (x_coords >= right_temple_x + face_w * 0.02)
        & (y_coords >= crown_y - face_h * 0.05)
        & (y_coords <= right_side_bottom_y)
    )
    side_gate = left_side_gate | right_side_gate
    inner_face_gate = (
        (x_coords >= left_temple_x - face_w * 0.02)
        & (x_coords <= right_temple_x + face_w * 0.02)
        & (y_coords >= forehead_y - face_h * 0.04)
        & (y_coords <= jaw_y + face_h * 0.08)
    )
    directional_gate = np.where((top_gate | side_gate) & ~inner_face_gate, 255, 0).astype(np.uint8)
    if int(np.count_nonzero(directional_gate)) < 8:
        return None
    return directional_gate


def _mask_components_touching_seed(
    mask: np.ndarray,
    seed_mask: np.ndarray,
) -> np.ndarray:
    if mask.shape != seed_mask.shape:
        return np.zeros_like(mask, dtype=np.uint8)
    active_mask = np.where(mask > 0, np.uint8(255), np.uint8(0))
    active_seed = np.where(seed_mask > 0, np.uint8(255), np.uint8(0))
    if int(np.count_nonzero(active_mask)) < 8 or int(np.count_nonzero(active_seed)) < 1:
        return np.zeros_like(mask, dtype=np.uint8)

    label_count, labels = cv2.connectedComponents(active_mask, connectivity=8)
    if label_count <= 1:
        return np.zeros_like(mask, dtype=np.uint8)

    selected_labels = np.unique(labels[active_seed > 0])
    if selected_labels.size == 0:
        return np.zeros_like(mask, dtype=np.uint8)

    selected_mask = np.zeros_like(mask, dtype=np.uint8)
    for label_index in selected_labels:
        if int(label_index) <= 0:
            continue
        selected_mask[labels == int(label_index)] = 255
    return selected_mask


def _build_outer_side_fringe_gates(
    user_row: dict[str, Any],
    shape: tuple[int, int],
) -> tuple[np.ndarray | None, np.ndarray | None]:
    frame_height, frame_width = shape
    face_bbox = user_row.get("face_bbox")
    if not isinstance(face_bbox, dict):
        return None, None
    try:
        face_x = float(face_bbox["x"])
        face_y = float(face_bbox["y"])
        face_w = float(face_bbox["w"])
        face_h = float(face_bbox["h"])
    except (KeyError, TypeError, ValueError):
        return None, None
    if face_w <= 1.0 or face_h <= 1.0:
        return None, None

    anchors = user_row.get("anchors")
    left_temple = _anchor_xy(anchors, "left_temple")
    right_temple = _anchor_xy(anchors, "right_temple")
    left_ear_root = _anchor_xy(anchors, "left_ear_root")
    right_ear_root = _anchor_xy(anchors, "right_ear_root")
    forehead_center = _anchor_xy(anchors, "forehead_center")
    crown = _anchor_xy(anchors, "crown")

    left_temple_x = left_temple[0] if left_temple is not None else face_x + face_w * 0.18
    right_temple_x = right_temple[0] if right_temple is not None else face_x + face_w * 0.82
    temple_y = (
        (left_temple[1] + right_temple[1]) * 0.5
        if left_temple is not None and right_temple is not None
        else face_y + face_h * 0.16
    )
    forehead_y = forehead_center[1] if forehead_center is not None else face_y
    crown_y = crown[1] if crown is not None else max(0.0, forehead_y - face_h * 0.22)
    left_ear_y = left_ear_root[1] if left_ear_root is not None else temple_y + face_h * 0.28
    right_ear_y = right_ear_root[1] if right_ear_root is not None else temple_y + face_h * 0.28
    pose = user_row.get("pose")
    try:
        yaw_abs = abs(float((pose or {}).get("yaw_float", 0.0)))
    except (TypeError, ValueError):
        yaw_abs = 0.0
    side_pose_strength = float(np.clip((yaw_abs - 10.0) / 20.0, 0.0, 1.0))
    side_seed_inset = face_w * (0.16 - 0.10 * side_pose_strength)
    side_seed_bottom_pad = face_h * (0.08 - 0.10 * side_pose_strength)
    keep_expand_x = face_w * (0.14 * side_pose_strength)
    keep_expand_bottom = face_h * (0.18 * side_pose_strength)

    x_coords, y_coords = _coord_grids(shape)

    side_seed_gate = (
        (
            (x_coords <= left_temple_x + side_seed_inset)
            & (y_coords >= crown_y - face_h * 0.08)
            & (y_coords <= left_ear_y + side_seed_bottom_pad)
        )
        | (
            (x_coords >= right_temple_x - side_seed_inset)
            & (y_coords >= crown_y - face_h * 0.08)
            & (y_coords <= right_ear_y + side_seed_bottom_pad)
        )
    )
    central_keep_gate = (
        (x_coords >= left_temple_x + face_w * 0.02 - keep_expand_x)
        & (x_coords <= right_temple_x - face_w * 0.02 + keep_expand_x)
        & (y_coords >= crown_y - face_h * 0.24)
        & (y_coords <= temple_y + face_h * 0.24 + keep_expand_bottom)
    )
    if int(np.count_nonzero(side_seed_gate)) < 8:
        return None, None
    return (
        np.where(side_seed_gate, np.uint8(255), np.uint8(0)),
        np.where(central_keep_gate, np.uint8(255), np.uint8(0)),
    )


def _build_outer_side_fringe_cleanup_mask(
    fringe_mask: np.ndarray,
    coverage_mask: np.ndarray,
    face_protect_mask: np.ndarray | None,
    user_row: dict[str, Any],
) -> np.ndarray:
    fringe_residual_mask = opencv_bitwise_and(fringe_mask, opencv_bitwise_not(coverage_mask))
    if face_protect_mask is not None:
        fringe_residual_mask = opencv_bitwise_and(
            fringe_residual_mask,
            opencv_bitwise_not(face_protect_mask),
        )
    if int(np.count_nonzero(fringe_residual_mask)) < 8:
        return np.zeros_like(fringe_mask, dtype=np.uint8)

    side_seed_gate, central_keep_gate = _build_outer_side_fringe_gates(
        user_row,
        fringe_mask.shape,
    )
    if side_seed_gate is None:
        return np.zeros_like(fringe_mask, dtype=np.uint8)

    outer_candidate_mask = np.array(fringe_residual_mask, copy=True)
    if central_keep_gate is not None:
        outer_candidate_mask = opencv_bitwise_and(
            outer_candidate_mask,
            opencv_bitwise_not(central_keep_gate),
        )
    side_seed_mask = opencv_bitwise_and(outer_candidate_mask, side_seed_gate)
    if int(np.count_nonzero(side_seed_mask)) < 8:
        return np.zeros_like(fringe_mask, dtype=np.uint8)
    return _mask_components_touching_seed(outer_candidate_mask, side_seed_mask)


def _build_outer_background_ring_mask(
    cleanup_seed_mask: np.ndarray,
    hair_binary_mask: np.ndarray,
    user_row: dict[str, Any],
    *,
    external_background_mask: np.ndarray | None = None,
) -> np.ndarray:
    if OUTER_BACKGROUND_RING_PX <= 0:
        return np.zeros_like(hair_binary_mask, dtype=np.uint8)
    if int(np.count_nonzero(cleanup_seed_mask)) < 8:
        return np.zeros_like(hair_binary_mask, dtype=np.uint8)

    kernel_size = OUTER_BACKGROUND_RING_PX * 2 + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    dilated_mask = opencv_dilate(cleanup_seed_mask, kernel, iterations=1, min_pixels=0)
    outer_ring_mask = opencv_bitwise_and(dilated_mask, opencv_bitwise_not(cleanup_seed_mask))
    if external_background_mask is None:
        external_background_mask = _build_external_background_mask(hair_binary_mask)
    outer_ring_mask = opencv_bitwise_and(outer_ring_mask, external_background_mask)
    outer_ring_gate = _build_directional_outer_ring_gate(user_row, hair_binary_mask.shape)
    if outer_ring_gate is None:
        return np.zeros_like(hair_binary_mask, dtype=np.uint8)
    outer_ring_mask = opencv_bitwise_and(outer_ring_mask, outer_ring_gate)
    return outer_ring_mask


def _backgroundize_mask(
    output_frame_bgr: np.ndarray,
    base_frame_bgr: np.ndarray,
    hair_binary_mask: np.ndarray,
    cleanup_mask: np.ndarray,
    *,
    background_color: np.ndarray,
    alpha_scale: float = 1.0,
    external_background_mask: np.ndarray | None = None,
    use_local_background_field: bool = True,
    local_color_field: tuple[np.ndarray, np.ndarray] | None = None,
    feather_edges: bool = True,
) -> np.ndarray:
    if int(np.count_nonzero(cleanup_mask)) < 8:
        return output_frame_bgr

    x, y, width, height = cv2.boundingRect(cleanup_mask)
    if width <= 1 or height <= 1:
        return output_frame_bgr

    cleanup_roi = cleanup_mask[y : y + height, x : x + width]
    output_roi = output_frame_bgr[y : y + height, x : x + width].copy()
    base_roi = base_frame_bgr[y : y + height, x : x + width]
    blur_roi = opencv_gaussian_blur(base_roi, (5, 5), sigma_x=0.0, sigma_y=0.0, min_pixels=24_000)

    alpha = cleanup_roi.astype(np.float32) / 255.0
    if feather_edges:
        alpha = opencv_gaussian_blur(
            alpha,
            (0, 0),
            sigma_x=max(0.8, width * 0.012),
            sigma_y=max(0.8, height * 0.018),
            min_pixels=0,
        )
    alpha = np.where(cleanup_roi > 0, alpha, 0.0)
    alpha = np.clip(alpha * float(alpha_scale), 0.0, 1.0)
    if float(alpha.max()) <= 0.01:
        return output_frame_bgr

    background_fill = np.empty_like(output_roi, dtype=np.float32)
    background_fill[:] = background_color
    target_roi = background_fill * 0.97 + blur_roi.astype(np.float32) * 0.03
    local_background_field = local_color_field
    if local_background_field is None and use_local_background_field:
        local_background_field = _build_local_background_field(
            base_frame_bgr,
            hair_binary_mask,
            cleanup_mask,
            fallback_color=background_color,
            external_background_mask=external_background_mask,
        )
    if local_background_field is not None:
        field_cols, field_colors = local_background_field
        field_by_col = np.tile(background_color[None, :], (width, 1))
        local_cols = field_cols - x
        valid_local_cols = (
            (local_cols >= 0)
            & (local_cols < width)
        )
        if bool(np.any(valid_local_cols)):
            field_by_col[local_cols[valid_local_cols]] = field_colors[valid_local_cols]
        target_roi = field_by_col[None, :, :] * 0.97 + blur_roi.astype(np.float32) * 0.03

    output_roi_float = output_roi.astype(np.float32)
    output_roi_float = output_roi_float * (1.0 - alpha[..., None]) + target_roi * alpha[..., None]

    result = output_frame_bgr.copy()
    result[y : y + height, x : x + width] = np.clip(output_roi_float, 0.0, 255.0).astype(np.uint8)
    return result


def apply_overlay_postprocess(
    output_frame_bgr: np.ndarray,
    base_frame_bgr: np.ndarray,
    user_row: dict[str, Any],
    *,
    renderer_name: str,
    coverage_mask: np.ndarray | None = None,
) -> np.ndarray:
    _ = renderer_name
    if output_frame_bgr.shape != base_frame_bgr.shape or output_frame_bgr.ndim != 3 or output_frame_bgr.shape[2] != 3:
        return output_frame_bgr

    frame_shape = output_frame_bgr.shape[:2]
    hair_binary_mask = _as_mask(user_row.get("_hair_binary_mask"), frame_shape)
    fringe_mask = _as_mask(user_row.get("_hair_fringe_mask"), frame_shape)
    face_protect_mask = _as_mask(user_row.get("_hair_face_protect_mask"), frame_shape)
    body_clothing_mask = _as_mask(user_row.get("_body_clothing_mask"), frame_shape)
    person_body_mask = _as_mask(user_row.get("_person_body_mask"), frame_shape)
    background_color = _as_color(user_row.get("_hair_background_color"))
    precomputed_shirt_color = _as_color(user_row.get("_hair_clothing_color"))
    precomputed_field_cols = user_row.get("_hair_clothing_field_cols")
    precomputed_field_colors = user_row.get("_hair_clothing_field_colors")
    if hair_binary_mask is None or background_color is None:
        return output_frame_bgr
    external_background_mask = _build_external_background_mask(hair_binary_mask)

    candidate_mask = np.array(hair_binary_mask, copy=True)
    if fringe_mask is not None:
        candidate_mask = opencv_bitwise_and(candidate_mask, opencv_bitwise_not(fringe_mask))
    if face_protect_mask is not None:
        candidate_mask = opencv_bitwise_and(candidate_mask, opencv_bitwise_not(face_protect_mask))

    coverage = _as_mask(coverage_mask, frame_shape)
    # Never backgroundize pixels unless the renderer provided an explicit
    # coverage mask. Output-vs-base diff is too weak for semi-transparent hair
    # assets and can punch holes inside the applied asset.
    if coverage is None:
        return output_frame_bgr

    residual_mask = (
        opencv_bitwise_and(candidate_mask, opencv_bitwise_not(coverage))
        if int(np.count_nonzero(candidate_mask)) >= 8
        else np.zeros_like(hair_binary_mask, dtype=np.uint8)
    )
    fringe_central_keep_gate: np.ndarray | None = None
    fringe_outer_cleanup_mask = np.zeros_like(hair_binary_mask, dtype=np.uint8)
    if fringe_mask is not None:
        _, fringe_central_keep_gate = _build_outer_side_fringe_gates(
            user_row,
            frame_shape,
        )
        fringe_outer_cleanup_mask = _build_outer_side_fringe_cleanup_mask(
            fringe_mask,
            coverage,
            face_protect_mask,
            user_row,
        )
    cleanup_seed_mask = opencv_bitwise_or(residual_mask, fringe_outer_cleanup_mask)
    outer_ring_mask = _build_outer_background_ring_mask(
        cleanup_seed_mask,
        hair_binary_mask,
        user_row,
        external_background_mask=external_background_mask,
    )
    if fringe_central_keep_gate is not None:
        outer_ring_mask = opencv_bitwise_and(
            outer_ring_mask,
            opencv_bitwise_not(fringe_central_keep_gate),
        )
    cleanup_mask = opencv_bitwise_or(cleanup_seed_mask, outer_ring_mask)
    if int(np.count_nonzero(cleanup_mask)) < 8:
        return output_frame_bgr

    local_clothing_field: tuple[np.ndarray, np.ndarray] | None = None
    if (
        isinstance(precomputed_field_cols, np.ndarray)
        and precomputed_field_cols.ndim == 1
        and isinstance(precomputed_field_colors, np.ndarray)
        and precomputed_field_colors.ndim == 2
        and precomputed_field_colors.shape[1] == 3
        and precomputed_field_colors.shape[0] == precomputed_field_cols.shape[0]
    ):
        local_clothing_field = (
            np.asarray(precomputed_field_cols, dtype=np.int32),
            np.asarray(precomputed_field_colors, dtype=np.float32),
        )

    shirt_color = precomputed_shirt_color
    below_shoulder_mask = body_clothing_mask
    if shirt_color is None:
        shirt_color = _estimate_clothing_color(
            base_frame_bgr,
            hair_binary_mask,
            user_row,
            face_protect_mask=face_protect_mask,
        )
    if below_shoulder_mask is None and shirt_color is not None:
        below_shoulder_mask = _build_below_shoulder_mask(user_row, frame_shape)
    if shirt_color is None or below_shoulder_mask is None:
        return _backgroundize_mask(
            output_frame_bgr,
            base_frame_bgr,
            hair_binary_mask,
            cleanup_mask,
            background_color=background_color,
            alpha_scale=1.0,
            external_background_mask=external_background_mask,
        )

    clothing_seed_mask = opencv_bitwise_and(cleanup_mask, below_shoulder_mask)
    if person_body_mask is not None:
        body_overlap_mask = opencv_bitwise_and(cleanup_mask, person_body_mask)
        if int(np.count_nonzero(body_overlap_mask)) >= 8:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            clothing_seed_mask = opencv_bitwise_or(
                clothing_seed_mask,
                opencv_dilate(body_overlap_mask, kernel, iterations=1, min_pixels=0),
            )
            clothing_seed_mask = opencv_bitwise_and(clothing_seed_mask, cleanup_mask)

    clothing_target_mask = clothing_seed_mask
    if int(np.count_nonzero(clothing_seed_mask)) >= 8:
        clothing_expand_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
        clothing_target_mask = opencv_dilate(
            clothing_seed_mask,
            clothing_expand_kernel,
            iterations=1,
            min_pixels=0,
        )
        clothing_target_mask = opencv_bitwise_and(clothing_target_mask, cleanup_mask)

    lower_cleanup_mask = clothing_target_mask
    upper_cleanup_mask = opencv_bitwise_and(cleanup_mask, opencv_bitwise_not(clothing_target_mask))

    result = output_frame_bgr
    if int(np.count_nonzero(upper_cleanup_mask)) >= 8:
        result = _backgroundize_mask(
            result,
            base_frame_bgr,
            hair_binary_mask,
            upper_cleanup_mask,
            background_color=background_color,
            alpha_scale=1.0,
            external_background_mask=external_background_mask,
        )
    if int(np.count_nonzero(lower_cleanup_mask)) >= 8:
        if local_clothing_field is None:
            local_clothing_field = _build_local_clothing_field(
                base_frame_bgr,
                hair_binary_mask,
                lower_cleanup_mask,
                user_row,
                face_protect_mask=face_protect_mask,
            )
        result = _backgroundize_mask(
            result,
            base_frame_bgr,
            hair_binary_mask,
            lower_cleanup_mask,
            background_color=shirt_color,
            alpha_scale=1.0,
            external_background_mask=None,
            use_local_background_field=False,
            local_color_field=local_clothing_field,
            feather_edges=False,
        )
    return result
