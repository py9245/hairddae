from __future__ import annotations

from typing import Any

import cv2
import numpy as np

try:
    from .gpu_tensor_ops import alpha_blend, gaussian_blur_tensor, image_to_tensor, mask_to_tensor, tensor_to_image
except ImportError:  # pragma: no cover
    from gpu_tensor_ops import alpha_blend, gaussian_blur_tensor, image_to_tensor, mask_to_tensor, tensor_to_image


def _as_mask(mask: object, shape: tuple[int, int]) -> np.ndarray | None:
    if not isinstance(mask, np.ndarray) or mask.shape != shape:
        return None
    return np.where(mask > 0, np.uint8(255), np.uint8(0))


def _as_color(color: object) -> np.ndarray | None:
    if color is None:
        return None
    values = np.asarray(color, dtype=np.float32).reshape(-1)
    if values.size < 3 or not bool(np.all(np.isfinite(values[:3]))):
        return None
    return np.clip(values[:3], 0.0, 255.0).astype(np.float32)


class GpuOverlayPostprocess:
    def apply(
        self,
        output_frame_bgr: np.ndarray,
        base_frame_bgr: np.ndarray,
        user_row: dict[str, Any],
        *,
        coverage_mask: np.ndarray | None = None,
    ) -> np.ndarray:
        if output_frame_bgr.shape != base_frame_bgr.shape:
            return output_frame_bgr
        frame_shape = output_frame_bgr.shape[:2]
        hair_binary_mask = _as_mask(user_row.get("_hair_binary_mask"), frame_shape)
        fringe_mask = _as_mask(user_row.get("_hair_fringe_mask"), frame_shape)
        background_color = _as_color(user_row.get("_hair_background_color"))
        coverage = _as_mask(coverage_mask, frame_shape)
        if hair_binary_mask is None or background_color is None or coverage is None:
            return output_frame_bgr

        candidate_mask = np.array(hair_binary_mask, copy=True)
        if fringe_mask is not None:
            candidate_mask = cv2.bitwise_and(candidate_mask, cv2.bitwise_not(fringe_mask))
        residual_mask = cv2.bitwise_and(candidate_mask, cv2.bitwise_not(coverage))
        if int(np.count_nonzero(residual_mask)) < 8:
            return output_frame_bgr

        x, y, width, height = cv2.boundingRect(residual_mask)
        if width <= 1 or height <= 1:
            return output_frame_bgr

        residual_roi = residual_mask[y : y + height, x : x + width]
        output_roi = output_frame_bgr[y : y + height, x : x + width]
        base_roi = base_frame_bgr[y : y + height, x : x + width]
        output_tensor = image_to_tensor(output_roi)
        base_tensor = image_to_tensor(base_roi)
        alpha_tensor = gaussian_blur_tensor(
            mask_to_tensor(residual_roi),
            sigma_x=max(0.8, width * 0.012),
            sigma_y=max(0.8, height * 0.018),
        ).clamp(0.0, 1.0)
        background_fill = output_tensor.new_tensor(background_color.reshape(1, 3, 1, 1) / 255.0)
        blurred_base = gaussian_blur_tensor(base_tensor, sigma_x=1.25, sigma_y=1.25)
        target_tensor = background_fill * 0.97 + blurred_base * 0.03
        composed = alpha_blend(output_tensor, target_tensor, alpha_tensor)
        result = output_frame_bgr.copy()
        result[y : y + height, x : x + width] = tensor_to_image(composed, dtype=np.uint8)
        return result
