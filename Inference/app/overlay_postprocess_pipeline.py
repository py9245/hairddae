from __future__ import annotations

from typing import Any

import cv2
import numpy as np


def _mask_from_payload(
    value: object,
    frame_shape: tuple[int, int],
) -> np.ndarray | None:
    if not isinstance(value, np.ndarray) or value.ndim != 2:
        return None
    if value.shape != frame_shape:
        return None
    return np.where(value >= 96, np.uint8(255), np.uint8(0))


def _color_from_payload(value: object) -> np.ndarray | None:
    if value is None:
        return None
    color = np.asarray(value, dtype=np.float32).reshape(-1)
    if color.size < 3:
        return None
    return color[:3].astype(np.float32)


def apply_overlay_postprocess(
    output_frame_bgr: np.ndarray,
    base_frame_bgr: np.ndarray,
    user_row: dict[str, Any],
    *,
    renderer_name: str,
    coverage_mask: np.ndarray | None = None,
) -> np.ndarray:
    if renderer_name != "bundle_render":
        return output_frame_bgr
    if not isinstance(coverage_mask, np.ndarray) or coverage_mask.shape != output_frame_bgr.shape[:2]:
        return output_frame_bgr

    hair_binary_mask = _mask_from_payload(
        user_row.get("_hair_binary_mask"),
        output_frame_bgr.shape[:2],
    )
    upper_region_mask = _mask_from_payload(
        user_row.get("_hair_upper_region_mask"),
        output_frame_bgr.shape[:2],
    )
    face_protect_mask = _mask_from_payload(
        user_row.get("_hair_face_protect_mask"),
        output_frame_bgr.shape[:2],
    )
    background_color = _color_from_payload(user_row.get("_hair_background_color"))
    if hair_binary_mask is None or upper_region_mask is None or background_color is None:
        return output_frame_bgr
    if int(np.count_nonzero(hair_binary_mask)) == 0:
        return output_frame_bgr
    if int(np.count_nonzero(upper_region_mask)) == 0:
        return output_frame_bgr

    coverage_u8 = np.asarray(coverage_mask, dtype=np.uint8)
    strict_upper_coverage = np.where(coverage_u8 >= 40, np.uint8(255), np.uint8(0))
    upper_protrusion_mask = cv2.bitwise_and(
        hair_binary_mask,
        upper_region_mask,
    )
    upper_protrusion_mask = cv2.bitwise_and(
        upper_protrusion_mask,
        cv2.bitwise_not(strict_upper_coverage),
    )
    if face_protect_mask is not None and int(np.count_nonzero(face_protect_mask)) > 0:
        protect_inverse = cv2.bitwise_not(face_protect_mask)
        upper_protrusion_mask = cv2.bitwise_and(upper_protrusion_mask, protect_inverse)
    if int(np.count_nonzero(upper_protrusion_mask)) == 0:
        return output_frame_bgr

    result = output_frame_bgr.astype(np.float32)
    background_fill = np.empty_like(result, dtype=np.float32)
    background_fill[:] = background_color
    target = background_fill * 0.98 + base_frame_bgr.astype(np.float32) * 0.02
    alpha = np.where(upper_protrusion_mask[..., None] > 0, np.float32(0.995), np.float32(0.0))
    result = result * (1.0 - alpha) + target * alpha
    return np.clip(result, 0.0, 255.0).astype(np.uint8)
