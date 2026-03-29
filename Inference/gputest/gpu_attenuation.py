from __future__ import annotations

import time
from typing import Any

import cv2
import numpy as np

from app.hair_attenuation import HairAttenuator

try:
    from .gpu_tensor_ops import alpha_blend, gaussian_blur_tensor, image_to_tensor, mask_to_tensor, tensor_to_image
except ImportError:  # pragma: no cover
    from gpu_tensor_ops import alpha_blend, gaussian_blur_tensor, image_to_tensor, mask_to_tensor, tensor_to_image


class GpuNativeHairAttenuator(HairAttenuator):
    def apply_with_metadata(
        self,
        frame_bgr: np.ndarray,
        landmarks_px: np.ndarray | None,
        *,
        user_row: dict[str, Any] | None = None,
        hair_confidence_mask: np.ndarray | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        if frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
            return frame_bgr, {}

        started_at = time.perf_counter()
        detail_ms: dict[str, float] = {}
        confidence_mask = None
        mask_kind = "landmark"

        mask_prepare_started_at = time.perf_counter()
        if hair_confidence_mask is not None:
            confidence_mask = self._normalize_confidence_mask(
                hair_confidence_mask,
                frame_bgr.shape[1],
                frame_bgr.shape[0],
            )
            if confidence_mask is not None:
                confidence_mask = np.clip(confidence_mask, 0.0, 1.0)
                mask_kind = "segmentation_gpu_native"
        detail_ms["mask_prepare_ms"] = round((time.perf_counter() - mask_prepare_started_at) * 1000.0, 3)

        segmentation_alpha_threshold = max(0.08, self.profile.segmentation_confidence_threshold * 0.42)
        mask_build_started_at = time.perf_counter()
        if confidence_mask is not None:
            binary_mask = np.where(confidence_mask >= segmentation_alpha_threshold, np.uint8(255), np.uint8(0))
        else:
            if landmarks_px is None:
                return frame_bgr, {}
            binary_mask = self._build_binary_mask(frame_bgr.shape, landmarks_px, user_row=user_row)
            if binary_mask is None:
                return frame_bgr, {}
        detail_ms["mask_build_ms"] = round((time.perf_counter() - mask_build_started_at) * 1000.0, 3)

        x, y, width, height = cv2.boundingRect(binary_mask)
        if width <= 1 or height <= 1:
            return frame_bgr, {}

        roi_setup_started_at = time.perf_counter()
        roi = frame_bgr[y : y + height, x : x + width]
        mask_roi = binary_mask[y : y + height, x : x + width]
        roi_tensor = image_to_tensor(roi)
        mask_tensor = mask_to_tensor(mask_roi)
        detail_ms["roi_setup_ms"] = round((time.perf_counter() - roi_setup_started_at) * 1000.0, 3)

        alpha_started_at = time.perf_counter()
        if confidence_mask is not None:
            confidence_roi = confidence_mask[y : y + height, x : x + width]
            confidence_tensor = mask_to_tensor(confidence_roi)
            confidence_tensor = gaussian_blur_tensor(
                confidence_tensor,
                sigma_x=max(1.2, width * 0.026),
                sigma_y=max(1.2, height * 0.026),
            )
            alpha_tensor = (
                (confidence_tensor - segmentation_alpha_threshold)
                / max(1e-6, 1.0 - segmentation_alpha_threshold)
            ).clamp(0.0, 1.0) * float(self.profile.strength)
            alpha_tensor = alpha_tensor * (mask_tensor >= (96.0 / 255.0)).float()
        else:
            alpha_tensor = gaussian_blur_tensor(
                mask_tensor,
                sigma_x=max(2.0, width * 0.08),
                sigma_y=max(2.0, height * 0.10),
            ).clamp(0.0, 1.0) * float(self.profile.strength)
        detail_ms["confidence_alpha_ms"] = round((time.perf_counter() - alpha_started_at) * 1000.0, 3)

        zone_started_at = time.perf_counter()
        hair_mask_full = np.array(binary_mask, copy=True)
        fringe_mask_full = (
            self._build_forehead_fringe_mask(frame_bgr.shape, landmarks_px, user_row=user_row)
            if landmarks_px is not None
            else None
        )
        if fringe_mask_full is None:
            fringe_mask_full = np.zeros(frame_bgr.shape[:2], dtype=np.uint8)
        fringe_mask_full = cv2.bitwise_and(hair_mask_full, fringe_mask_full)
        outer_bulk_mask_full = cv2.bitwise_and(hair_mask_full, cv2.bitwise_not(fringe_mask_full))
        fringe_roi = fringe_mask_full[y : y + height, x : x + width]
        outer_bulk_roi = outer_bulk_mask_full[y : y + height, x : x + width]
        fringe_tensor = mask_to_tensor(fringe_roi)
        outer_bulk_tensor = mask_to_tensor(outer_bulk_roi)
        detail_ms["zone_mask_ms"] = round((time.perf_counter() - zone_started_at) * 1000.0, 3)

        blur_started_at = time.perf_counter()
        blur_sigma = max(1.0, max(width, height) * max(0.02, self.profile.blur_kernel_scale * 0.45))
        blurred_tensor = gaussian_blur_tensor(roi_tensor, sigma_x=blur_sigma, sigma_y=blur_sigma)
        weakened_tensor = blurred_tensor
        detail_ms["base_blur_ms"] = round((time.perf_counter() - blur_started_at) * 1000.0, 3)

        color_started_at = time.perf_counter()
        scalp_color = None
        skin_color = self._estimate_skin_color(frame_bgr, landmarks_px)
        boundary_skin_color = self._estimate_lower_boundary_skin_color(
            frame_bgr,
            hair_mask_full,
            landmarks_px,
            reference_skin_color=skin_color,
        )
        scalp_source_color = self._blend_scalp_reference_color(skin_color, boundary_skin_color)
        if scalp_source_color is not None:
            scalp_color = self._resolve_scalp_color(scalp_source_color)
        background_color = (
            self._estimate_background_color(frame_bgr, outer_bulk_mask_full)
            if not self.profile.disable_outer_bulk_suppression and int(np.count_nonzero(outer_bulk_mask_full)) > 0
            else None
        )
        if scalp_color is not None and not self.profile.disable_fringe_suppression and int(np.count_nonzero(fringe_roi)) > 0:
            scalp_fill = roi_tensor.new_tensor(scalp_color.reshape(1, 3, 1, 1) / 255.0)
            weakened_tensor = weakened_tensor * (1.0 - fringe_tensor) + scalp_fill * fringe_tensor
            alpha_tensor = alpha_tensor.maximum(fringe_tensor)
        detail_ms["color_estimation_ms"] = round((time.perf_counter() - color_started_at) * 1000.0, 3)

        suppression_started_at = time.perf_counter()
        if background_color is not None and not self.profile.disable_outer_bulk_suppression and int(np.count_nonzero(outer_bulk_roi)) > 0:
            background_fill = roi_tensor.new_tensor(background_color.reshape(1, 3, 1, 1) / 255.0)
            weakened_tensor = weakened_tensor * (1.0 - outer_bulk_tensor) + (
                background_fill * 0.82 + blurred_tensor * 0.18
            ) * outer_bulk_tensor
            alpha_tensor = alpha_tensor.maximum(outer_bulk_tensor * max(float(self.profile.strength), 0.95))
        detail_ms["suppression_apply_ms"] = round((time.perf_counter() - suppression_started_at) * 1000.0, 3)

        blend_started_at = time.perf_counter()
        blended_tensor = alpha_blend(roi_tensor, weakened_tensor, alpha_tensor.clamp(0.0, 1.0))
        output = frame_bgr.copy()
        output[y : y + height, x : x + width] = tensor_to_image(blended_tensor, dtype=np.uint8)
        detail_ms["roi_blend_ms"] = round((time.perf_counter() - blend_started_at) * 1000.0, 3)
        detail_ms["lower_hairline_blend_ms"] = 0.0
        detail_ms["eye_restore_ms"] = 0.0
        detail_ms["total_ms"] = round((time.perf_counter() - started_at) * 1000.0, 3)

        metadata: dict[str, Any] = {
            "mask_kind": mask_kind,
            "hair_binary_mask": hair_mask_full,
            "fringe_mask": fringe_mask_full,
            "outer_bulk_mask": outer_bulk_mask_full,
            "attenuation_detail_ms": detail_ms,
        }
        if background_color is not None:
            metadata["background_color"] = np.asarray(background_color, dtype=np.float32)
        if scalp_color is not None:
            metadata["scalp_color"] = np.asarray(scalp_color, dtype=np.float32)
        return output, metadata
