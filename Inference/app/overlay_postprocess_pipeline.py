from __future__ import annotations

import os
from typing import Any

import cv2
import numpy as np

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
) -> tuple[np.ndarray, np.ndarray] | None:
    active_cols = np.flatnonzero(np.any(candidate_mask > 0, axis=0))
    if active_cols.size == 0:
        return None

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
        return max(temple_y + max(1.0, face_h * 0.02), ear_root[1] - 10.0)

    left_side_bottom_y = min(jaw_y, _side_bottom_y(left_ear_root))
    right_side_bottom_y = min(jaw_y, _side_bottom_y(right_ear_root))

    x_coords = np.broadcast_to(
        np.arange(frame_width, dtype=np.float32)[None, :],
        (frame_height, frame_width),
    )
    y_coords = np.broadcast_to(
        np.arange(frame_height, dtype=np.float32)[:, None],
        (frame_height, frame_width),
    )

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


def _build_outer_background_ring_mask(
    cleanup_seed_mask: np.ndarray,
    hair_binary_mask: np.ndarray,
    user_row: dict[str, Any],
) -> np.ndarray:
    if OUTER_BACKGROUND_RING_PX <= 0:
        return np.zeros_like(hair_binary_mask, dtype=np.uint8)
    if int(np.count_nonzero(cleanup_seed_mask)) < 8:
        return np.zeros_like(hair_binary_mask, dtype=np.uint8)

    kernel_size = OUTER_BACKGROUND_RING_PX * 2 + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    dilated_mask = opencv_dilate(cleanup_seed_mask, kernel, iterations=1, min_pixels=0)
    outer_ring_mask = opencv_bitwise_and(dilated_mask, opencv_bitwise_not(cleanup_seed_mask))
    outer_ring_mask = opencv_bitwise_and(
        outer_ring_mask,
        _build_external_background_mask(hair_binary_mask),
    )
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
    local_background_field = _build_local_background_field(
        base_frame_bgr,
        hair_binary_mask,
        cleanup_mask,
        fallback_color=background_color,
    )
    target_roi = background_fill * 0.97 + blur_roi.astype(np.float32) * 0.03
    if local_background_field is not None:
        field_cols, field_colors = local_background_field
        field_by_col = np.tile(background_color[None, :], (output_frame_bgr.shape[1], 1))
        field_by_col[field_cols] = field_colors
        target_roi = field_by_col[x : x + width][None, :, :] * 0.97 + blur_roi.astype(np.float32) * 0.03

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
    background_color = _as_color(user_row.get("_hair_background_color"))
    if hair_binary_mask is None or background_color is None:
        return output_frame_bgr

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

    if int(np.count_nonzero(candidate_mask)) < 8:
        return output_frame_bgr

    residual_mask = opencv_bitwise_and(candidate_mask, opencv_bitwise_not(coverage))
    outer_ring_mask = _build_outer_background_ring_mask(
        residual_mask,
        hair_binary_mask,
        user_row,
    )
    cleanup_mask = opencv_bitwise_or(residual_mask, outer_ring_mask)
    if int(np.count_nonzero(cleanup_mask)) < 8:
        return output_frame_bgr

    # Feather residual cleanup and the outer n-ring together so there is no
    # seam between the original residual region and the 5px extension.
    return _backgroundize_mask(
        output_frame_bgr,
        base_frame_bgr,
        hair_binary_mask,
        cleanup_mask,
        background_color=background_color,
        alpha_scale=1.0,
    )
