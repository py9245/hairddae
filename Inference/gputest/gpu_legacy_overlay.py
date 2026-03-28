from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np

from hairddae_tools import run_hair_overlay_poc as rp

try:
    from .gpu_asset_cache import GpuLegacyAssetCache
    from .gpu_tensor_ops import (
        alpha_blend,
        apply_masked_gain,
        gaussian_blur_tensor,
        image_to_tensor,
        tensor_to_image,
        tensor_to_mask,
        warp_affine_tensor,
    )
except ImportError:  # pragma: no cover
    from gpu_asset_cache import GpuLegacyAssetCache
    from gpu_tensor_ops import (
        alpha_blend,
        apply_masked_gain,
        gaussian_blur_tensor,
        image_to_tensor,
        tensor_to_image,
        tensor_to_mask,
        warp_affine_tensor,
    )


class GpuLegacyOverlayEngine:
    def __init__(self, *, asset_cache: GpuLegacyAssetCache | None = None) -> None:
        self.asset_cache = asset_cache or GpuLegacyAssetCache()

    def _build_layer(
        self,
        user_row: dict[str, Any],
        user_image_shape: tuple[int, int, int],
        asset_row: dict[str, Any],
        asset_root: Path,
        *,
        user_mask_bundle: dict[str, Any] | None = None,
        debug_payload: dict[str, object] | None = None,
    ) -> dict[str, Any] | None:
        started_at = time.perf_counter()
        asset_load_started_at = time.perf_counter()
        asset = self.asset_cache.get(asset_root, asset_row)
        asset_load_ms = round((time.perf_counter() - asset_load_started_at) * 1000.0, 3)

        height, width = user_image_shape[:2]
        setup_started_at = time.perf_counter()
        matrix = rp.estimate_transform(asset.anchors, user_row["anchors"])
        head_size_scale, head_scale_pivot = rp.compute_conservative_head_size_scale(
            user_row,
            user_mask_bundle,
            (height, width),
        )
        matrix = rp._scaled_affine_about_pivot(matrix, head_size_scale, head_scale_pivot)
        src_x0, src_y0, src_x1, src_y1 = asset.crop_box
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
        dst_x0, dst_y0, dst_x1, dst_y1 = roi
        roi_width = dst_x1 - dst_x0
        roi_height = dst_y1 - dst_y0
        roi_matrix = rp.roi_affine_from_crop(matrix, src_x0, src_y0, dst_x0, dst_y0)
        roi_setup_ms = round((time.perf_counter() - setup_started_at) * 1000.0, 3)

        warp_started_at = time.perf_counter()
        warped_rgb = warp_affine_tensor(asset.rgb, roi_matrix, dst_width=roi_width, dst_height=roi_height, mode="bilinear")
        warped_alpha = warp_affine_tensor(asset.alpha, roi_matrix, dst_width=roi_width, dst_height=roi_height, mode="bilinear")
        warped_hair = warp_affine_tensor(asset.hair, roi_matrix, dst_width=roi_width, dst_height=roi_height, mode="nearest")
        warped_protect = warp_affine_tensor(
            asset.protect_face,
            roi_matrix,
            dst_width=roi_width,
            dst_height=roi_height,
            mode="nearest",
        )
        warp_total_ms = round((time.perf_counter() - warp_started_at) * 1000.0, 3)

        rgb_gain_started_at = time.perf_counter()
        rgb_gain = rp.resolve_hair_tone_gain(user_row, asset.hair_luma)
        warped_rgb = apply_masked_gain(warped_rgb, warped_hair, rgb_gain)
        rgb_gain_ms = round((time.perf_counter() - rgb_gain_started_at) * 1000.0, 3)

        effective_alpha_started_at = time.perf_counter()
        alpha_min = warped_alpha.minimum(warped_hair)
        effective_alpha = gaussian_blur_tensor(
            alpha_min,
            sigma_x=1.45,
            sigma_y=1.45,
        )
        effective_alpha = effective_alpha.clamp(0.0, 1.0)
        effective_alpha_ms = round((time.perf_counter() - effective_alpha_started_at) * 1000.0, 3)

        suppression_started_at = time.perf_counter()
        if float(warped_protect.max().item()) > 0.0:
            protect_layer = gaussian_blur_tensor(warped_protect, sigma_x=2.8, sigma_y=2.8).clamp(0.0, 1.0)
            effective_alpha = (effective_alpha * (1.0 - protect_layer * 0.10)).clamp(0.84, 1.0) * (effective_alpha > 0.0)
        skin_suppression_ms = round((time.perf_counter() - suppression_started_at) * 1000.0, 3)

        coverage_tensor = ((warped_alpha >= (24.0 / 255.0)) | (warped_hair >= (24.0 / 255.0))).float()
        if debug_payload is not None:
            debug_payload.update(
                {
                    "asset_load_ms": asset_load_ms,
                    "roi_setup_ms": roi_setup_ms,
                    "warp_total_ms": warp_total_ms,
                    "rgb_gain_ms": rgb_gain_ms,
                    "effective_alpha_ms": effective_alpha_ms,
                    "skin_suppression_ms": skin_suppression_ms,
                    "legacy_layer_total_ms": round((time.perf_counter() - started_at) * 1000.0, 3),
                }
            )
        return {
            "roi": roi,
            "rgb": warped_rgb,
            "alpha": effective_alpha,
            "coverage": coverage_tensor,
        }

    def compose_single(
        self,
        user_row: dict[str, Any],
        base_frame_bgr: np.ndarray,
        asset_row: dict[str, Any],
        asset_root: Path,
        *,
        user_mask_bundle: dict[str, Any] | None = None,
        debug_payload: dict[str, object] | None = None,
    ) -> tuple[np.ndarray, np.ndarray | None]:
        layer_detail_ms: dict[str, object] = {}
        layer = self._build_layer(
            user_row,
            base_frame_bgr.shape,
            asset_row,
            asset_root,
            user_mask_bundle=user_mask_bundle,
            debug_payload=layer_detail_ms,
        )
        if layer is None:
            return base_frame_bgr.copy(), None

        x0, y0, x1, y1 = layer["roi"]
        base_roi_tensor = image_to_tensor(base_frame_bgr[y0:y1, x0:x1])
        composite_started_at = time.perf_counter()
        composed_roi = alpha_blend(base_roi_tensor, layer["rgb"], layer["alpha"])
        composite_ms = round((time.perf_counter() - composite_started_at) * 1000.0, 3)
        output = base_frame_bgr.copy()
        output[y0:y1, x0:x1] = tensor_to_image(composed_roi, dtype=np.uint8)
        coverage_roi = tensor_to_mask(layer["coverage"], dtype=np.uint8)
        coverage_mask = np.zeros(base_frame_bgr.shape[:2], dtype=np.uint8)
        coverage_mask[y0:y1, x0:x1] = coverage_roi
        if debug_payload is not None:
            debug_payload.update(
                {
                    "build_layer_ms": round(float(layer_detail_ms.get("legacy_layer_total_ms") or 0.0), 3),
                    "composite_ms": composite_ms,
                    "legacy_layer_detail_ms": layer_detail_ms,
                }
            )
        return output, coverage_mask

    def compose_weighted(
        self,
        user_row: dict[str, Any],
        base_frame_bgr: np.ndarray,
        weighted_assets: list[tuple[dict[str, Any], float]],
        asset_root: Path,
        *,
        user_mask_bundle: dict[str, Any] | None = None,
        debug_payload: dict[str, object] | None = None,
    ) -> tuple[np.ndarray, np.ndarray | None]:
        active_assets = [(asset_row, float(weight)) for asset_row, weight in weighted_assets if float(weight) > 0.0]
        if not active_assets:
            return base_frame_bgr.copy(), None
        if len(active_assets) == 1 and active_assets[0][1] >= 0.999:
            return self.compose_single(
                user_row,
                base_frame_bgr,
                active_assets[0][0],
                asset_root,
                user_mask_bundle=user_mask_bundle,
                debug_payload=debug_payload,
            )

        started_at = time.perf_counter()
        base_tensor = image_to_tensor(base_frame_bgr)
        accumulated_coverage: np.ndarray | None = None
        total_weight = max(1e-6, sum(weight for _, weight in active_assets))
        delta_tensor = base_tensor.new_zeros(base_tensor.shape)
        for asset_row, weight in active_assets:
            single_debug: dict[str, object] = {}
            overlay_frame, coverage_mask = self.compose_single(
                user_row,
                base_frame_bgr,
                asset_row,
                asset_root,
                user_mask_bundle=user_mask_bundle,
                debug_payload=single_debug,
            )
            overlay_tensor = image_to_tensor(overlay_frame)
            delta_tensor = delta_tensor + (overlay_tensor - base_tensor) * (weight / total_weight)
            if isinstance(coverage_mask, np.ndarray):
                accumulated_coverage = coverage_mask if accumulated_coverage is None else np.maximum(accumulated_coverage, coverage_mask)
        output = tensor_to_image((base_tensor + delta_tensor).clamp(0.0, 1.0), dtype=np.uint8)
        if debug_payload is not None:
            debug_payload.update(
                {
                    "blend_path": "gpu_multi_asset_delta",
                    "asset_count": len(active_assets),
                    "overlay_blend_total_ms": round((time.perf_counter() - started_at) * 1000.0, 3),
                }
            )
        return output, accumulated_coverage
