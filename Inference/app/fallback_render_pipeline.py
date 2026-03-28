from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

import cv2
import numpy as np
from PIL import Image

from app.catalog import AssetBundle
from app.models import FeatureMessageModel
from app.server_render import compose_bundle_frame
from cv2_cuda_utils import opencv_cvt_color


@dataclass(frozen=True)
class BundleFallbackRenderResult:
    rendered_bgr: np.ndarray | None
    bundle: AssetBundle | None
    latency_ms: float


def render_bundle_fallback_frame(
    frame_bgr: np.ndarray,
    original_frame_bgr: np.ndarray | None,
    feature: FeatureMessageModel,
    *,
    catalog: Any,
    dataset_code: str,
    representative_asset_id: str | None,
) -> BundleFallbackRenderResult:
    started_at = time.perf_counter()
    try:
        bundle = catalog.recommend(
            dataset_code,
            feature,
            representative_asset_id=representative_asset_id,
        )
    except Exception:
        return BundleFallbackRenderResult(rendered_bgr=None, bundle=None, latency_ms=0.0)

    try:
        frame_image = Image.fromarray(opencv_cvt_color(frame_bgr, cv2.COLOR_BGR2RGB))
        original_frame_image = None
        if isinstance(original_frame_bgr, np.ndarray) and original_frame_bgr.shape == frame_bgr.shape:
            original_frame_image = Image.fromarray(opencv_cvt_color(original_frame_bgr, cv2.COLOR_BGR2RGB))
        rendered_image = compose_bundle_frame(
            frame_image,
            bundle,
            original_frame_image=original_frame_image,
        )
        rendered_bgr = opencv_cvt_color(np.asarray(rendered_image), cv2.COLOR_RGB2BGR)
    except Exception:
        return BundleFallbackRenderResult(rendered_bgr=None, bundle=None, latency_ms=0.0)

    return BundleFallbackRenderResult(
        rendered_bgr=rendered_bgr,
        bundle=bundle,
        latency_ms=round((time.perf_counter() - started_at) * 1000.0, 3),
    )
