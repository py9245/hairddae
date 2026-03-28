from __future__ import annotations

import importlib
import time
from typing import Any

import cv2
import numpy as np

import forced_gpu_cv2 as fg

ha = importlib.import_module("app.hair_attenuation")
rp = importlib.import_module("hairddae_tools.run_hair_overlay_poc")


_ORIGINAL_APPLY_WITH_METADATA = ha.HairAttenuator.apply_with_metadata
_ORIGINAL_BUILD_LEGACY_OVERLAY_LAYER = rp.build_legacy_overlay_layer


def experimental_apply_with_metadata(
    self: Any,
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
    mask_started_at = time.perf_counter()
    confidence_mask = None
    mask_kind = "landmark"
    if hair_confidence_mask is not None:
        confidence_mask = self._normalize_confidence_mask(
            hair_confidence_mask,
            frame_bgr.shape[1],
            frame_bgr.shape[0],
        )
        if confidence_mask is not None:
            confidence_mask = np.clip(confidence_mask, 0.0, 1.0)
            mask_kind = "segmentation_fast"
    detail_ms["mask_prepare_ms"] = round((time.perf_counter() - mask_started_at) * 1000.0, 3)

    build_mask_started_at = time.perf_counter()
    if confidence_mask is not None:
        binary_mask = np.where(
            confidence_mask >= max(0.10, self.profile.segmentation_confidence_threshold * 0.55),
            np.uint8(255),
            np.uint8(0),
        )
    else:
        if landmarks_px is None:
            return frame_bgr, {}
        binary_mask = self._build_binary_mask(frame_bgr.shape, landmarks_px, user_row=user_row)
        if binary_mask is None:
            return frame_bgr, {}
    detail_ms["mask_build_ms"] = round((time.perf_counter() - build_mask_started_at) * 1000.0, 3)

    x, y, width, height = cv2.boundingRect(binary_mask)
    if width <= 1 or height <= 1:
        return frame_bgr, {}

    roi_started_at = time.perf_counter()
    output = frame_bgr.copy()
    roi = output[y : y + height, x : x + width]
    mask_roi = binary_mask[y : y + height, x : x + width]
    detail_ms["roi_setup_ms"] = round((time.perf_counter() - roi_started_at) * 1000.0, 3)

    blur_started_at = time.perf_counter()
    blur_sigma = max(1.2, max(width, height) * max(0.02, self.profile.blur_kernel_scale * 0.45))
    blurred_roi = fg.opencv_gaussian_blur(
        roi,
        (0, 0),
        sigma_x=blur_sigma,
        sigma_y=blur_sigma,
    )
    detail_ms["base_blur_ms"] = round((time.perf_counter() - blur_started_at) * 1000.0, 3)

    color_started_at = time.perf_counter()
    fringe_mask_full = (
        self._build_forehead_fringe_mask(frame_bgr.shape, landmarks_px, user_row=user_row)
        if landmarks_px is not None
        else np.zeros(frame_bgr.shape[:2], dtype=np.uint8)
    )
    fringe_mask_full = fg.opencv_bitwise_and(binary_mask, fringe_mask_full)
    fringe_roi = fringe_mask_full[y : y + height, x : x + width]
    scalp_color = self._estimate_skin_color(frame_bgr, landmarks_px)
    if scalp_color is None:
        scalp_color = self._estimate_skin_color_fallback(frame_bgr)
    if scalp_color is None:
        scalp_color = np.array([214.0, 204.0, 196.0], dtype=np.float32)
    weakened_roi = blurred_roi.astype(np.float32)
    if int(np.count_nonzero(fringe_roi)) > 0:
        weakened_roi[fringe_roi > 0] = scalp_color.astype(np.float32)
    detail_ms["color_estimation_ms"] = round((time.perf_counter() - color_started_at) * 1000.0, 3)

    alpha_started_at = time.perf_counter()
    if confidence_mask is not None:
        alpha_roi = confidence_mask[y : y + height, x : x + width].astype(np.float32) * float(self.profile.strength)
    else:
        alpha_roi = (mask_roi.astype(np.float32) / 255.0) * float(self.profile.strength)
    alpha_roi = fg.opencv_gaussian_blur(
        alpha_roi,
        (0, 0),
        sigma_x=max(1.0, min(width, height) * 0.012),
        sigma_y=max(1.0, min(width, height) * 0.015),
    )
    alpha_roi = np.where(mask_roi > 0, alpha_roi, 0.0)
    alpha_roi = np.clip(alpha_roi[..., None], 0.0, 1.0)
    detail_ms["confidence_alpha_ms"] = round((time.perf_counter() - alpha_started_at) * 1000.0, 3)

    blend_started_at = time.perf_counter()
    blended = roi.astype(np.float32) * (1.0 - alpha_roi) + weakened_roi * alpha_roi
    output[y : y + height, x : x + width] = np.clip(blended, 0.0, 255.0).astype(np.uint8)
    detail_ms["roi_blend_ms"] = round((time.perf_counter() - blend_started_at) * 1000.0, 3)
    detail_ms["lower_hairline_blend_ms"] = 0.0
    detail_ms["eye_restore_ms"] = 0.0
    detail_ms["total_ms"] = round((time.perf_counter() - started_at) * 1000.0, 3)

    metadata = {
        "mask_kind": mask_kind,
        "hair_binary_mask": binary_mask,
        "fringe_mask": fringe_mask_full,
        "outer_bulk_mask": np.zeros_like(binary_mask, dtype=np.uint8),
        "scalp_color": np.asarray(scalp_color, dtype=np.float32),
        "attenuation_detail_ms": detail_ms,
    }
    return output, metadata


def experimental_build_legacy_overlay_layer(
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
    matrix = rp.estimate_transform(asset_anchors, user_row["anchors"])
    head_size_scale, head_scale_pivot = rp.compute_conservative_head_size_scale(
        user_row,
        user_mask_bundle,
        (height, width),
    )
    matrix = rp._scaled_affine_about_pivot(matrix, head_size_scale, head_scale_pivot)
    src_corners = np.array(
        [[src_x0, src_y0], [src_x1, src_y0], [src_x1, src_y1], [src_x0, src_y1]],
        dtype=np.float32,
    )
    dst_corners = rp.transform_points(matrix, src_corners)
    dst_margin = rp.render_roi_margin(src_x1 - src_x0, src_y1 - src_y0)
    roi = rp.clamp_roi(
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
    if bool(asset_bundle.get("packed_crop_only")):
        src_rgb = asset_image
        src_alpha = asset_alpha
        src_hair = asset_hair
        src_protect_face = asset_bundle["protect_face_mask"]
    else:
        src_rgb = asset_image[src_y0:src_y1, src_x0:src_x1]
        src_alpha = asset_alpha[src_y0:src_y1, src_x0:src_x1]
        src_hair = asset_hair[src_y0:src_y1, src_x0:src_x1]
        src_protect_face = asset_bundle["protect_face_mask"][src_y0:src_y1, src_x0:src_x1]

    roi_matrix = rp.roi_affine_from_crop(matrix, src_x0, src_y0, dst_x0, dst_y0)
    gpu_src_rgb = fg.opencv_cuda_upload(src_rgb)
    gpu_src_alpha = fg.opencv_cuda_upload(src_alpha)
    gpu_src_hair = fg.opencv_cuda_upload(src_hair)
    gpu_src_protect = fg.opencv_cuda_upload(src_protect_face)

    warp_started_at = time.perf_counter()
    warped_rgb_gpu = fg.opencv_warp_affine_uploaded(
        gpu_src_rgb,
        roi_matrix,
        (roi_width, roi_height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
    )
    warped_alpha_gpu = fg.opencv_warp_affine_uploaded(
        gpu_src_alpha,
        roi_matrix,
        (roi_width, roi_height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
    )
    warped_hair_gpu = fg.opencv_warp_affine_uploaded(
        gpu_src_hair,
        roi_matrix,
        (roi_width, roi_height),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
    )
    warped_protect_gpu = fg.opencv_warp_affine_uploaded(
        gpu_src_protect,
        roi_matrix,
        (roi_width, roi_height),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
    )
    warped_rgb = fg.opencv_cuda_download(warped_rgb_gpu) if warped_rgb_gpu is not None else fg.opencv_warp_affine(src_rgb, roi_matrix, (roi_width, roi_height), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    warped_alpha = fg.opencv_cuda_download(warped_alpha_gpu) if warped_alpha_gpu is not None else fg.opencv_warp_affine(src_alpha, roi_matrix, (roi_width, roi_height), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    warped_hair = fg.opencv_cuda_download(warped_hair_gpu) if warped_hair_gpu is not None else fg.opencv_warp_affine(src_hair, roi_matrix, (roi_width, roi_height), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT)
    warped_protect = fg.opencv_cuda_download(warped_protect_gpu) if warped_protect_gpu is not None else fg.opencv_warp_affine(src_protect_face, roi_matrix, (roi_width, roi_height), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT)
    warp_total_ms = round((time.perf_counter() - warp_started_at) * 1000.0, 3)

    rgb_gain_started_at = time.perf_counter()
    rgb_gain = rp.resolve_hair_tone_gain(user_row, asset_bundle.get("hair_luma"))
    warped_rgb = rp.apply_masked_rgb_gain(warped_rgb, warped_hair, rgb_gain)
    rgb_gain_ms = round((time.perf_counter() - rgb_gain_started_at) * 1000.0, 3)

    alpha_started_at = time.perf_counter()
    hard_coverage = np.where(np.maximum(warped_alpha, warped_hair) >= 32, np.uint8(255), np.uint8(0))
    effective_alpha = np.minimum(warped_alpha, warped_hair).astype(np.float32) / 255.0
    effective_alpha = fg.opencv_gaussian_blur(effective_alpha, (0, 0), sigma_x=1.1, sigma_y=1.1)
    effective_alpha = np.clip(effective_alpha, 0.0, 1.0)
    alpha_ms = round((time.perf_counter() - alpha_started_at) * 1000.0, 3)

    suppression_started_at = time.perf_counter()
    if warped_protect is not None and int(np.count_nonzero(warped_protect)) > 0:
        protect_layer = fg.opencv_gaussian_blur((warped_protect > 0).astype(np.float32), (0, 0), sigma_x=2.8, sigma_y=2.8)
        effective_alpha *= np.clip(1.0 - (protect_layer * 0.10), 0.84, 1.0)
        effective_alpha = np.clip(effective_alpha, 0.0, 1.0)
    suppression_ms = round((time.perf_counter() - suppression_started_at) * 1000.0, 3)

    if debug_payload is not None:
        debug_payload.update(
            {
                "roi_setup_ms": roi_setup_ms,
                "warp_total_ms": warp_total_ms,
                "rgb_gain_ms": rgb_gain_ms,
                "effective_alpha_ms": alpha_ms,
                "skin_suppression_ms": suppression_ms,
                "legacy_layer_total_ms": round((time.perf_counter() - started_at) * 1000.0, 3),
            }
        )
    return {
        "roi": roi,
        "rgb": np.clip(warped_rgb, 0.0, 255.0).astype(np.uint8),
        "alpha": effective_alpha,
        "coverage": hard_coverage,
        "render_kind": "legacy_experimental_gpu",
    }


def patch_experimental_pipeline() -> None:
    ha.HairAttenuator.apply_with_metadata = experimental_apply_with_metadata
    rp.build_legacy_overlay_layer = experimental_build_legacy_overlay_layer


def restore_experimental_pipeline() -> None:
    ha.HairAttenuator.apply_with_metadata = _ORIGINAL_APPLY_WITH_METADATA
    rp.build_legacy_overlay_layer = _ORIGINAL_BUILD_LEGACY_OVERLAY_LAYER
