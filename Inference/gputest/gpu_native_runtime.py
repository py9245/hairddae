from __future__ import annotations

import os
import time
from pathlib import Path
from threading import Lock
from typing import Any

import numpy as np

from app.config import Settings
from app.hairddae_runtime import HairOverlayRuntime, normalize_renderer_name
from app.hairddae_runtime_manager import HairddaeRuntimeManager
from cv2_cuda_utils import opencv_add_weighted

try:
    from .gpu_legacy_overlay import GpuLegacyOverlayEngine
    from .gpu_postprocess import GpuOverlayPostprocess
except ImportError:  # pragma: no cover
    from gpu_legacy_overlay import GpuLegacyOverlayEngine
    from gpu_postprocess import GpuOverlayPostprocess


class GpuNativeLegacyRuntime(HairOverlayRuntime):
    def __init__(
        self,
        asset_root: str | Path | None = None,
        model_path: str | Path | None = None,
        jpeg_quality: int = 88,
        renderer_name: str = "legacy",
    ) -> None:
        super().__init__(asset_root=asset_root, model_path=model_path, jpeg_quality=jpeg_quality, renderer_name=renderer_name)
        self._gpu_overlay_engine = GpuLegacyOverlayEngine()
        self._gpu_postprocess = GpuOverlayPostprocess()

    def _compose_output_frame(
        self,
        user_row: dict[str, Any],
        frame_bgr: np.ndarray,
        blend_assets: list[tuple[dict[str, Any], float]],
        renderer_name: str,
        user_mask_bundle: dict[str, Any] | None,
        *,
        prefer_latency: bool,
        source_frame_bgr: np.ndarray | None = None,
    ) -> tuple[np.ndarray, float, str | None, str, np.ndarray | None]:
        _ = prefer_latency
        started_at = time.perf_counter()
        resolved_renderer = normalize_renderer_name(renderer_name)
        effective_renderer_name = "legacy" if resolved_renderer == "legacy" else resolved_renderer
        if self._transition is None:
            overlay_detail_ms: dict[str, object] = {}
            output_frame, coverage_mask = self._gpu_overlay_engine.compose_weighted(
                user_row,
                frame_bgr,
                blend_assets,
                self.asset_root,
                user_mask_bundle=user_mask_bundle,
                debug_payload=overlay_detail_ms,
            )
            overlay_blend_ms = round((time.perf_counter() - started_at) * 1000.0, 3)
            self._merge_selection_trace_fields(
                compose_detail_ms={
                    "compose_mode": "overlay",
                    "resolve_compose_mode_ms": 0.0,
                    "resolve_compose_renderer_ms": 0.0,
                    "overlay_blend_ms": overlay_blend_ms,
                    "overlay_blend_detail_ms": overlay_detail_ms,
                    "transition_blend_ms": 0.0,
                }
            )
            return output_frame, 1.0, None, effective_renderer_name, coverage_mask

        target_debug: dict[str, object] = {}
        target_frame, target_coverage = self._gpu_overlay_engine.compose_weighted(
            user_row,
            frame_bgr,
            blend_assets,
            self.asset_root,
            user_mask_bundle=user_mask_bundle,
            debug_payload=target_debug,
        )
        from_assets = self._transition["from_blend_assets"]
        from_asset_id = str(self._transition["from_asset_id"])
        from_debug: dict[str, object] = {}
        from_frame, from_coverage = self._gpu_overlay_engine.compose_weighted(
            user_row,
            frame_bgr,
            from_assets,
            self.asset_root,
            user_mask_bundle=user_mask_bundle,
            debug_payload=from_debug,
        )
        self._transition["step"] += 1
        transition_progress = min(1.0, self._transition["step"] / float(self._transition["steps"]))
        blend_started_at = time.perf_counter()
        blended_frame = opencv_add_weighted(from_frame, 1.0 - transition_progress, target_frame, transition_progress, 0.0)
        transition_blend_ms = round((time.perf_counter() - blend_started_at) * 1000.0, 3)
        blended_coverage = target_coverage
        if isinstance(target_coverage, np.ndarray) and isinstance(from_coverage, np.ndarray) and target_coverage.shape == from_coverage.shape:
            blended_coverage = np.maximum(target_coverage, from_coverage)
        if transition_progress >= 1.0:
            self._transition = None
        self._merge_selection_trace_fields(
            compose_detail_ms={
                "compose_mode": "overlay_transition",
                "resolve_compose_mode_ms": 0.0,
                "resolve_compose_renderer_ms": 0.0,
                "overlay_transition_frames_ms": round(float(target_debug.get("overlay_blend_total_ms") or 0.0), 3),
                "transition_blend_ms": transition_blend_ms,
                "overlay_transition_detail_ms": {"target": target_debug, "from": from_debug},
            }
        )
        return blended_frame, transition_progress, from_asset_id, effective_renderer_name, blended_coverage

    def _apply_overlay_postprocess(
        self,
        output_frame_bgr: np.ndarray,
        base_frame_bgr: np.ndarray,
        user_row: dict[str, Any],
        *,
        renderer_name: str,
        coverage_mask: np.ndarray | None = None,
    ) -> np.ndarray:
        _ = renderer_name
        return self._gpu_postprocess.apply(output_frame_bgr, base_frame_bgr, user_row, coverage_mask=coverage_mask)


class GpuNativeRuntimeManager(HairddaeRuntimeManager):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = Lock()
        self._runtime_cache: dict[str, GpuNativeLegacyRuntime] = {}

    def _runtime_for_dataset(self, dataset_code: str) -> GpuNativeLegacyRuntime:
        with self._lock:
            runtime = self._runtime_cache.get(dataset_code)
            if runtime is not None:
                return runtime
            self._configure_runtime_env()
            asset_root = self._settings.static_root / dataset_code
            os.environ["INFERENCE_RTC_BUNDLE_RENDER_ENABLED"] = "0"
            os.environ["INFERENCE_RTC_RENDERER_NAME"] = "legacy"
            os.environ["INFERENCE_RTC_LATENCY_RENDERER_NAME"] = "legacy"
            os.environ["INFERENCE_RTC_LIGHTWEIGHT_RENDERER_NAME"] = "legacy"
            runtime = GpuNativeLegacyRuntime(
                asset_root=asset_root,
                model_path=self._settings.face_landmarker_model_path,
                jpeg_quality=self._settings.http_test_jpeg_quality,
                renderer_name="legacy",
            )
            self._runtime_cache[dataset_code] = runtime
            return runtime
