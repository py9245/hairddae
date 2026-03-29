from __future__ import annotations

from concurrent.futures import Executor
from dataclasses import dataclass
import logging
import time
from typing import Any

import cv2
import numpy as np

from cv2_cuda_utils import opencv_cvt_color
from app.models import FeatureMessageModel

logger = logging.getLogger("uvicorn.error")


def _now_ms() -> int:
    return int(time.time() * 1000)


@dataclass(frozen=True)
class FramePreparationMetrics:
    tracking_latency_ms: float
    hair_segmentation_latency_ms: float
    hair_attenuation_latency_ms: float
    hair_attenuation_detail_ms: dict[str, float] | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "tracking_latency_ms": self.tracking_latency_ms,
            "hair_segmentation_latency_ms": self.hair_segmentation_latency_ms,
            "hair_attenuation_latency_ms": self.hair_attenuation_latency_ms,
        }
        if self.hair_attenuation_detail_ms:
            payload["hair_attenuation_detail_ms"] = dict(self.hair_attenuation_detail_ms)
        return payload


@dataclass(frozen=True)
class TrackingCacheSnapshot:
    user_row: dict[str, Any] | None
    landmarks_px: np.ndarray | None
    feature: FeatureMessageModel | None


@dataclass(frozen=True)
class PreparedRuntimeFrame:
    prepared_frame_bgr: np.ndarray
    tracked_user_row: dict[str, Any] | None
    attenuation_status: str
    metrics: FramePreparationMetrics
    tracking_feature: FeatureMessageModel | None
    tracking_snapshot: TrackingCacheSnapshot


def prepare_runtime_frame(
    frame_bgr: np.ndarray,
    *,
    seq: int,
    face_tracker: Any,
    hair_segmenter: Any | None,
    hair_attenuator: Any | None,
    hair_runtime_manager: Any,
    claims: Any,
    settings: Any,
    active_dataset_code: str,
    active_hair_id: int,
    prepare_executor: Executor,
    previous_tracking_snapshot: TrackingCacheSnapshot,
) -> PreparedRuntimeFrame:
    frame_rgb = opencv_cvt_color(frame_bgr, cv2.COLOR_BGR2RGB, min_pixels=200_000)
    reference_face_bbox = hair_runtime_manager.reference_face_bbox(
        active_dataset_code,
        claims.apply_session_id,
    )

    def _run_tracking() -> tuple[Any | None, float]:
        started_at = time.perf_counter()
        result = face_tracker.extract_tracking_result_from_rgb(
            frame_rgb,
            claims=claims,
            settings=settings,
            seq=seq,
            ts_ms=_now_ms(),
            hair_id_override=active_hair_id,
            reference_face_bbox=reference_face_bbox,
        )
        return result, round((time.perf_counter() - started_at) * 1000.0, 3)

    def _run_segmentation() -> tuple[np.ndarray | None, float]:
        if hair_segmenter is None:
            return None, 0.0
        started_at = time.perf_counter()
        try:
            result = hair_segmenter.segment_hair_confidence_from_rgb(
                frame_rgb,
                timestamp_ms=_now_ms(),
            )
        except Exception:
            result = None
        return result, round((time.perf_counter() - started_at) * 1000.0, 3)

    tracking_future = prepare_executor.submit(_run_tracking)
    segmentation_future = prepare_executor.submit(_run_segmentation)
    tracking_result, tracking_latency_ms = tracking_future.result()
    hair_confidence_mask, hair_segmentation_latency_ms = segmentation_future.result()

    next_tracking_snapshot = previous_tracking_snapshot
    fill_landmarks_px: np.ndarray | None = None
    fill_user_row: dict[str, Any] | None = None
    if tracking_result is not None:
        next_tracking_snapshot = TrackingCacheSnapshot(
            user_row=dict(tracking_result.user_row),
            landmarks_px=np.array(tracking_result.landmarks_px, copy=True),
            feature=tracking_result.feature,
        )
        fill_landmarks_px = tracking_result.landmarks_px
        fill_user_row = tracking_result.user_row
    else:
        if previous_tracking_snapshot.landmarks_px is not None:
            fill_landmarks_px = np.array(previous_tracking_snapshot.landmarks_px, copy=True)
        if previous_tracking_snapshot.user_row is not None:
            fill_user_row = dict(previous_tracking_snapshot.user_row)

    if fill_user_row is not None:
        fill_user_row = dict(fill_user_row)
        fill_user_row["_apply_session_id"] = str(claims.apply_session_id)

    metrics = FramePreparationMetrics(
        tracking_latency_ms=tracking_latency_ms,
        hair_segmentation_latency_ms=hair_segmentation_latency_ms,
        hair_attenuation_latency_ms=0.0,
    )

    if hair_attenuator is None:
        if tracking_result is None:
            return PreparedRuntimeFrame(
                prepared_frame_bgr=frame_bgr,
                tracked_user_row={"ok": False, "reason": "no_face_or_pose"},
                attenuation_status="no_face",
                metrics=metrics,
                tracking_feature=None,
                tracking_snapshot=next_tracking_snapshot,
            )
        return PreparedRuntimeFrame(
            prepared_frame_bgr=frame_bgr,
            tracked_user_row=tracking_result.user_row,
            attenuation_status="disabled",
            metrics=metrics,
            tracking_feature=tracking_result.feature,
            tracking_snapshot=next_tracking_snapshot,
        )

    try:
        attenuation_started_at = time.perf_counter()
        prepared_frame_bgr, hair_tone_metadata = hair_attenuator.apply_with_metadata(
            frame_bgr,
            fill_landmarks_px,
            user_row=fill_user_row,
            hair_confidence_mask=hair_confidence_mask,
        )
        metrics = FramePreparationMetrics(
            tracking_latency_ms=tracking_latency_ms,
            hair_segmentation_latency_ms=hair_segmentation_latency_ms,
            hair_attenuation_latency_ms=round(
                (time.perf_counter() - attenuation_started_at) * 1000.0,
                3,
            ),
            hair_attenuation_detail_ms=(
                dict(hair_tone_metadata.get("attenuation_detail_ms") or {})
                if isinstance(hair_tone_metadata, dict)
                else None
            ),
        )
    except Exception:
        logger.exception("hair attenuation failed during frame preparation: seq=%s", seq)
        return PreparedRuntimeFrame(
            prepared_frame_bgr=frame_bgr,
            tracked_user_row=(
                {"ok": False, "reason": "no_face_or_pose"}
                if tracking_result is None
                else tracking_result.user_row
            ),
            attenuation_status="error",
            metrics=metrics,
            tracking_feature=None if tracking_result is None else tracking_result.feature,
            tracking_snapshot=next_tracking_snapshot,
        )

    if not isinstance(prepared_frame_bgr, np.ndarray) or prepared_frame_bgr.shape != frame_bgr.shape:
        return PreparedRuntimeFrame(
            prepared_frame_bgr=frame_bgr,
            tracked_user_row=(
                {"ok": False, "reason": "no_face_or_pose"}
                if tracking_result is None
                else tracking_result.user_row
            ),
            attenuation_status="invalid_output",
            metrics=metrics,
            tracking_feature=None if tracking_result is None else tracking_result.feature,
            tracking_snapshot=next_tracking_snapshot,
        )

    if tracking_result is None:
        tracked_user_row: dict[str, Any] = {
            "ok": False,
            "reason": "no_face_or_pose",
            "image_size": {
                "width": int(frame_bgr.shape[1]),
                "height": int(frame_bgr.shape[0]),
            },
        }
    else:
        tracked_user_row = dict(tracking_result.user_row)

    if hair_tone_metadata:
        tone_payload = {
            key: hair_tone_metadata[key]
            for key in ("mean_luma", "coverage")
            if key in hair_tone_metadata
        }
        if tone_payload:
            tracked_user_row["_hair_tone"] = tone_payload
        outer_bulk_mask = hair_tone_metadata.get("outer_bulk_mask")
        if isinstance(outer_bulk_mask, np.ndarray) and outer_bulk_mask.shape == frame_bgr.shape[:2]:
            tracked_user_row["_hair_outer_bulk_mask"] = outer_bulk_mask
        hair_binary_mask = hair_tone_metadata.get("hair_binary_mask")
        if isinstance(hair_binary_mask, np.ndarray) and hair_binary_mask.shape == frame_bgr.shape[:2]:
            tracked_user_row["_hair_binary_mask"] = hair_binary_mask
        fringe_mask = hair_tone_metadata.get("fringe_mask")
        if isinstance(fringe_mask, np.ndarray) and fringe_mask.shape == frame_bgr.shape[:2]:
            tracked_user_row["_hair_fringe_mask"] = fringe_mask
        upper_region_mask = hair_tone_metadata.get("upper_region_mask")
        if isinstance(upper_region_mask, np.ndarray) and upper_region_mask.shape == frame_bgr.shape[:2]:
            tracked_user_row["_hair_upper_region_mask"] = upper_region_mask
        background_color = hair_tone_metadata.get("background_color")
        if background_color is not None:
            tracked_user_row["_hair_background_color"] = np.asarray(background_color, dtype=np.float32)
        scalp_color = hair_tone_metadata.get("scalp_color")
        if scalp_color is not None:
            tracked_user_row["_hair_scalp_color"] = np.asarray(scalp_color, dtype=np.float32)

    if hair_confidence_mask is not None and tracking_result is None:
        attenuation_status = "segmented_only"
    elif hair_confidence_mask is not None:
        attenuation_status = "segmented"
    elif tracking_result is None:
        attenuation_status = "no_face"
    else:
        attenuation_status = "landmark_mask"

    return PreparedRuntimeFrame(
        prepared_frame_bgr=prepared_frame_bgr,
        tracked_user_row=tracked_user_row,
        attenuation_status=attenuation_status,
        metrics=metrics,
        tracking_feature=None if tracking_result is None else tracking_result.feature,
        tracking_snapshot=next_tracking_snapshot,
    )
