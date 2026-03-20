from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
import json
import logging
import cv2
import numpy as np
from PIL import Image
from statistics import median
import time
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.auth import TicketValidationError, validate_connect_ticket
from app.bald import BaldPreprocessor
from app.catalog import AssetBundle, AssetCatalog
from app.config import Settings
from app.face_tracking import ServerFaceTracker
from app.hairddae_runtime_manager import HairddaeRuntimeManager
from app.models import FeatureMessageModel
from app.server_render import compose_bundle_frame

try:
    from aiortc import (
        RTCConfiguration,
        RTCIceGatherer,
        RTCIceServer,
        RTCPeerConnection,
        RTCSessionDescription,
        VideoStreamTrack,
    )
    from aiortc.mediastreams import MediaStreamError
    from av import VideoFrame
except ImportError:  # pragma: no cover - runtime guarded
    RTCConfiguration = None
    RTCIceGatherer = None
    RTCIceServer = None
    RTCPeerConnection = None
    RTCSessionDescription = None
    VideoStreamTrack = object
    MediaStreamError = RuntimeError
    VideoFrame = None


logger = logging.getLogger("uvicorn.error")
RENDER_FRAME_DELAY_MS = 60.0
MAX_BUFFERED_VIDEO_FRAMES = 8
SERVER_TRACK_MAX_BUFFERED_VIDEO_FRAMES = 2
SERVER_RENDER_READY_MIN_PROCESSED = 1
SERVER_RENDER_READY_MIN_STABLE_ASSET = 1
PROCESSED_BUNDLE_HISTORY_SIZE = 48
FRAME_BUNDLE_MAX_LAG_MS = 280.0
FRAME_BUNDLE_MAX_LEAD_MS = 180.0
RENDER_MATCH_LOG_INTERVAL_MS = 1000.0
PERF_LOG_INTERVAL_MS = 1500.0


async def _wait_for_ice_gathering_complete(peer_connection: Any, timeout_seconds: float = 8.0) -> None:
    if getattr(peer_connection, "iceGatheringState", None) == "complete":
        return

    loop = asyncio.get_running_loop()
    future: asyncio.Future[None] = loop.create_future()

    @peer_connection.on("icegatheringstatechange")
    async def _on_icegatheringstatechange() -> None:
        if peer_connection.iceGatheringState != "complete" or future.done():
            return
        future.set_result(None)

    try:
        await asyncio.wait_for(future, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.warning("rtc ice gathering timed out before completion")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _build_fallback_bundle(feature: FeatureMessageModel) -> AssetBundle:
    return AssetBundle(
        asset_id="fallback-blur-only",
        pose_key=(
            f"yaw{feature.pose.yaw_1deg:+03d}_"
            f"pitch{feature.pose.pitch_1deg:+03d}_"
            f"roll{feature.pose.roll_1deg:+03d}"
        ),
        yaw_1deg=feature.pose.yaw_1deg,
        pitch_1deg=feature.pose.pitch_1deg,
        roll_1deg=feature.pose.roll_1deg,
        hair_rgba_path=None,
        hair_rgba_url=None,
        hair_mask_url=None,
        anchors_url=None,
        metadata_url=None,
        hair_bbox=None,
        face_mask_url=None,
        protect_face_mask_url=None,
        render_task=None,
        revision="fallback:blur-only",
        score=0.0,
    )


class RtcOfferRequest(BaseModel):
    sdp: str
    type: str
    connect_ticket: str


@dataclass
class RtcSessionState:
    latest_feature: FeatureMessageModel | None = None
    last_selected_bundle: AssetBundle | None = None
    last_switch_at_ms: int = 0
    last_processed_seq: int = 0
    dropped_pending_count: int = 0
    processed_count: int = 0
    stable_asset_count: int = 0
    last_asset_id: str | None = None
    render_ready: bool = False
    processed_bundle_history: deque["ProcessedBundle"] = field(default_factory=deque)
    pose_window: deque[tuple[float, float, float]] = field(default_factory=deque)
    data_channel: Any | None = None
    server_processed_seq: int = 0
    bald_cache_frame_bgr: np.ndarray | None = None
    bald_cache_user_row: dict[str, Any] | None = None
    bald_cache_reuse_count: int = 0
    current_process_max_dimension: int | None = None
    slow_frame_streak: int = 0
    fast_frame_streak: int = 0
    last_perf_log_at_ms: float = 0.0
    recent_pipeline_latency_ms: float = 0.0


@dataclass
class BufferedVideoFrame:
    frame: Any
    received_at_ms: float


@dataclass
class ProcessedBundle:
    bundle: AssetBundle
    processed_seq: int
    feature_ts_ms: int
    received_at_ms: float
    feature_width: int
    feature_height: int


def _build_selection_feature(
    state: RtcSessionState,
    feature: FeatureMessageModel,
) -> FeatureMessageModel:
    state.pose_window.append(
        (
            float(feature.pose.yaw_float),
            float(feature.pose.pitch_float),
            float(feature.pose.roll_float),
        )
    )
    while len(state.pose_window) > 7:
        state.pose_window.popleft()

    if len(state.pose_window) < 3:
        return feature

    smoothed_yaw = float(median(item[0] for item in state.pose_window))
    smoothed_pitch = float(median(item[1] for item in state.pose_window))
    smoothed_roll = float(median(item[2] for item in state.pose_window))
    return feature.model_copy(
        update={
            "pose": feature.pose.model_copy(
                update={
                    "yaw_float": smoothed_yaw,
                    "pitch_float": smoothed_pitch,
                    "roll_float": smoothed_roll,
                    "yaw_1deg": int(round(smoothed_yaw)),
                    "pitch_1deg": int(round(smoothed_pitch)),
                    "roll_1deg": int(round(smoothed_roll)),
                }
            )
        }
    )


class RtcRenderTrack(VideoStreamTrack):  # type: ignore[misc]
    kind = "video"

    def __init__(self, source_track: Any, state: RtcSessionState) -> None:
        super().__init__()
        self._source_track = source_track
        self._state = state
        self._buffer: deque[BufferedVideoFrame] = deque()
        self._frame_available = asyncio.Event()
        self._source_ended = False
        self._last_match_log_at_ms = 0.0
        self._reader_task = asyncio.create_task(self._reader_loop())

    async def _reader_loop(self) -> None:
        try:
            while True:
                frame = await self._source_track.recv()
                self._buffer.append(
                    BufferedVideoFrame(frame=frame, received_at_ms=time.monotonic() * 1000)
                )
                while len(self._buffer) > MAX_BUFFERED_VIDEO_FRAMES:
                    self._buffer.popleft()
                self._frame_available.set()
        except Exception:
            self._source_ended = True
            self._frame_available.set()

    async def _next_buffered_frame(self) -> BufferedVideoFrame:
        while True:
            if self._buffer:
                oldest = self._buffer[0]
                age_ms = time.monotonic() * 1000 - oldest.received_at_ms
                if age_ms >= RENDER_FRAME_DELAY_MS or self._source_ended:
                    return self._buffer.popleft()

                await asyncio.sleep(max(0.001, (RENDER_FRAME_DELAY_MS - age_ms) / 1000))
                continue

            if self._source_ended:
                raise MediaStreamError

            await asyncio.sleep(0.005)

    def _match_bundle_for_frame(self, frame_received_at_ms: float) -> ProcessedBundle | None:
        if not self._state.render_ready:
            return None

        best_match: ProcessedBundle | None = None
        best_abs_delta_ms: float | None = None
        for candidate in reversed(self._state.processed_bundle_history):
            delta_ms = candidate.received_at_ms - frame_received_at_ms
            if delta_ms < -FRAME_BUNDLE_MAX_LAG_MS:
                break
            if delta_ms > FRAME_BUNDLE_MAX_LEAD_MS:
                continue

            abs_delta_ms = abs(delta_ms)
            if best_match is None or best_abs_delta_ms is None or abs_delta_ms < best_abs_delta_ms:
                best_match = candidate
                best_abs_delta_ms = abs_delta_ms

        return best_match

    def _log_render_match(
        self,
        frame_received_at_ms: float,
        match: ProcessedBundle | None,
        frame_width: int,
        frame_height: int,
    ) -> None:
        now_ms = time.monotonic() * 1000
        if now_ms - self._last_match_log_at_ms < RENDER_MATCH_LOG_INTERVAL_MS:
            return

        self._last_match_log_at_ms = now_ms
        if match is None:
            logger.info(
                "rtc render match: frame=%.1f match=none frame_size=%sx%s history=%s render_ready=%s",
                frame_received_at_ms,
                frame_width,
                frame_height,
                len(self._state.processed_bundle_history),
                self._state.render_ready,
            )
            return

        logger.info(
            (
                "rtc render match: frame=%.1f seq=%s asset=%s delta_ms=%.1f "
                "frame_size=%sx%s feature_size=%sx%s history=%s"
            ),
            frame_received_at_ms,
            match.processed_seq,
            match.bundle.asset_id,
            match.received_at_ms - frame_received_at_ms,
            frame_width,
            frame_height,
            match.feature_width,
            match.feature_height,
            len(self._state.processed_bundle_history),
        )

    async def recv(self) -> Any:
        buffered_frame = await self._next_buffered_frame()
        frame = buffered_frame.frame
        frame_width = int(getattr(frame, "width", 0) or 0)
        frame_height = int(getattr(frame, "height", 0) or 0)
        match = self._match_bundle_for_frame(buffered_frame.received_at_ms)
        self._log_render_match(
            buffered_frame.received_at_ms,
            match,
            frame_width,
            frame_height,
        )
        if match is None:
            return frame

        image = frame.to_image()
        rendered = compose_bundle_frame(
            image,
            match.bundle,
            reference_width=match.feature_width,
            reference_height=match.feature_height,
        )
        next_frame = VideoFrame.from_image(rendered.convert("RGB"))
        next_frame.pts = frame.pts
        next_frame.time_base = frame.time_base
        return next_frame


class RtcServerTrackedRenderTrack(VideoStreamTrack):  # type: ignore[misc]
    kind = "video"

    def __init__(
        self,
        source_track: Any,
        state: RtcSessionState,
        *,
        claims: Any,
        settings: Settings,
        catalog: AssetCatalog,
        hair_runtime_manager: HairddaeRuntimeManager,
        face_tracker: ServerFaceTracker,
        bald_processor: BaldPreprocessor | None,
    ) -> None:
        super().__init__()
        self._source_track = source_track
        self._state = state
        self._claims = claims
        self._settings = settings
        self._catalog = catalog
        self._hair_runtime_manager = hair_runtime_manager
        self._face_tracker = face_tracker
        self._bald_processor = bald_processor
        self._buffer: deque[BufferedVideoFrame] = deque()
        self._frame_available = asyncio.Event()
        self._source_ended = False
        self._reader_task = asyncio.create_task(self._reader_loop())

    @staticmethod
    def _bbox_iou(lhs_bbox: dict[str, Any] | None, rhs_bbox: dict[str, Any] | None) -> float:
        if not lhs_bbox or not rhs_bbox:
            return 0.0
        lhs_x0 = float(lhs_bbox.get("x", 0.0))
        lhs_y0 = float(lhs_bbox.get("y", 0.0))
        lhs_x1 = lhs_x0 + float(lhs_bbox.get("w", 0.0))
        lhs_y1 = lhs_y0 + float(lhs_bbox.get("h", 0.0))
        rhs_x0 = float(rhs_bbox.get("x", 0.0))
        rhs_y0 = float(rhs_bbox.get("y", 0.0))
        rhs_x1 = rhs_x0 + float(rhs_bbox.get("w", 0.0))
        rhs_y1 = rhs_y0 + float(rhs_bbox.get("h", 0.0))
        inter_x0 = max(lhs_x0, rhs_x0)
        inter_y0 = max(lhs_y0, rhs_y0)
        inter_x1 = min(lhs_x1, rhs_x1)
        inter_y1 = min(lhs_y1, rhs_y1)
        inter_w = max(0.0, inter_x1 - inter_x0)
        inter_h = max(0.0, inter_y1 - inter_y0)
        inter_area = inter_w * inter_h
        lhs_area = max(0.0, lhs_x1 - lhs_x0) * max(0.0, lhs_y1 - lhs_y0)
        rhs_area = max(0.0, rhs_x1 - rhs_x0) * max(0.0, rhs_y1 - rhs_y0)
        denominator = lhs_area + rhs_area - inter_area
        if denominator <= 0.0:
            return 0.0
        return inter_area / denominator

    @staticmethod
    def _pose_delta(lhs_row: dict[str, Any] | None, rhs_row: dict[str, Any] | None) -> float:
        if not lhs_row or not rhs_row:
            return 999.0
        lhs_pose = lhs_row.get("pose", {})
        rhs_pose = rhs_row.get("pose", {})
        return max(
            abs(float(lhs_pose.get("yaw_float", lhs_pose.get("yaw_1deg", 0.0))) - float(rhs_pose.get("yaw_float", rhs_pose.get("yaw_1deg", 0.0)))),
            abs(float(lhs_pose.get("pitch_float", lhs_pose.get("pitch_1deg", 0.0))) - float(rhs_pose.get("pitch_float", rhs_pose.get("pitch_1deg", 0.0)))),
            abs(float(lhs_pose.get("roll_float", lhs_pose.get("roll_1deg", 0.0))) - float(rhs_pose.get("roll_float", rhs_pose.get("roll_1deg", 0.0)))),
        )

    def _can_reuse_bald_cache(
        self,
        user_row: dict[str, Any] | None,
        frame_shape: tuple[int, ...],
    ) -> bool:
        cached_frame = self._state.bald_cache_frame_bgr
        cached_user_row = self._state.bald_cache_user_row
        if cached_frame is None or cached_user_row is None or user_row is None:
            return False
        if max(int(user_row.get("candidate_face_count") or 1), int(cached_user_row.get("candidate_face_count") or 1)) > 1:
            return False
        if cached_frame.shape != frame_shape:
            return False
        if self._state.bald_cache_reuse_count >= self._settings.rtc_bald_cache_max_reuse_frames:
            return False
        if self._bbox_iou(cached_user_row.get("face_bbox"), user_row.get("face_bbox")) < self._settings.rtc_bald_cache_bbox_iou_threshold:
            return False
        if self._pose_delta(cached_user_row, user_row) > self._settings.rtc_bald_cache_pose_delta_threshold_deg:
            return False
        return True

    def _prefer_latency_runtime(self) -> bool:
        configured_max_dimension = max(0, int(getattr(self._settings, "rtc_process_max_dimension", 0) or 0))
        effective_max_dimension = self._effective_process_max_dimension()
        if configured_max_dimension > 0 and effective_max_dimension < configured_max_dimension:
            return True
        target_latency_ms = max(1, int(getattr(self._settings, "rtc_target_frame_latency_ms", 0) or 1))
        return self._state.recent_pipeline_latency_ms > (target_latency_ms * 1.12)

    def _effective_process_max_dimension(self) -> int:
        configured = max(0, int(getattr(self._settings, "rtc_process_max_dimension", 0) or 0))
        current = self._state.current_process_max_dimension
        if current is None or current <= 0:
            return configured
        if configured <= 0:
            return current
        return min(configured, current)

    def _update_adaptive_resolution(self, pipeline_latency_ms: float) -> None:
        max_dimension = max(0, int(getattr(self._settings, "rtc_process_max_dimension", 0) or 0))
        min_dimension = max(0, int(getattr(self._settings, "rtc_process_min_dimension", 0) or 0))
        step_dimension = max(1, int(getattr(self._settings, "rtc_process_step_dimension", 0) or 1))
        target_latency_ms = max(1, int(getattr(self._settings, "rtc_target_frame_latency_ms", 0) or 1))
        if max_dimension <= 0 or min_dimension <= 0 or min_dimension >= max_dimension:
            return

        current_dimension = self._state.current_process_max_dimension or max_dimension
        slow_threshold = target_latency_ms * 1.45
        fast_threshold = target_latency_ms * 0.78

        if pipeline_latency_ms > slow_threshold and current_dimension > min_dimension:
            self._state.slow_frame_streak += 1
            self._state.fast_frame_streak = 0
            if self._state.slow_frame_streak >= 2:
                next_dimension = max(min_dimension, current_dimension - step_dimension)
                self._state.current_process_max_dimension = next_dimension
                self._state.slow_frame_streak = 0
                logger.info(
                    "rtc adaptive resolution: latency_ms=%.1f process_max_dimension=%s->%s",
                    pipeline_latency_ms,
                    current_dimension,
                    next_dimension,
                )
            return

        if pipeline_latency_ms < fast_threshold and current_dimension < max_dimension:
            self._state.fast_frame_streak += 1
            self._state.slow_frame_streak = 0
            if self._state.fast_frame_streak >= 6:
                next_dimension = min(max_dimension, current_dimension + step_dimension)
                self._state.current_process_max_dimension = next_dimension
                self._state.fast_frame_streak = 0
                logger.info(
                    "rtc adaptive resolution: latency_ms=%.1f process_max_dimension=%s->%s",
                    pipeline_latency_ms,
                    current_dimension,
                    next_dimension,
                )
            return

        self._state.slow_frame_streak = 0
        self._state.fast_frame_streak = 0

    def _prepare_frame_for_hair_runtime(
        self,
        frame_bgr: np.ndarray,
        seq: int,
    ) -> tuple[np.ndarray, dict[str, Any] | None, str, dict[str, float]]:
        tracking_started_at = time.perf_counter()
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        reference_face_bbox = self._hair_runtime_manager.reference_face_bbox(
            self._claims.dataset_code,
            self._claims.apply_session_id,
        )
        tracking_result = self._face_tracker.extract_tracking_result_from_rgb(
            frame_rgb,
            claims=self._claims,
            settings=self._settings,
            seq=seq,
            ts_ms=_now_ms(),
            reference_face_bbox=reference_face_bbox,
        )
        tracking_latency_ms = round((time.perf_counter() - tracking_started_at) * 1000.0, 3)
        if tracking_result is None:
            return (
                frame_bgr,
                {"ok": False, "reason": "no_face_or_pose"},
                "no_face",
                {
                    "tracking_latency_ms": tracking_latency_ms,
                    "bald_latency_ms": 0.0,
                },
            )
        if self._bald_processor is None:
            return (
                frame_bgr,
                tracking_result.user_row,
                "disabled",
                {
                    "tracking_latency_ms": tracking_latency_ms,
                    "bald_latency_ms": 0.0,
                },
            )

        if self._can_reuse_bald_cache(tracking_result.user_row, frame_bgr.shape):
            self._state.bald_cache_reuse_count += 1
            cached_frame = self._state.bald_cache_frame_bgr
            if cached_frame is not None:
                return (
                    cached_frame.copy(),
                    tracking_result.user_row,
                    "cached",
                    {
                        "tracking_latency_ms": tracking_latency_ms,
                        "bald_latency_ms": 0.0,
                    },
                )

        try:
            bald_started_at = time.perf_counter()
            bald_rgb = self._bald_processor.apply(frame_rgb, tracking_result.landmarks_px)
            bald_latency_ms = round((time.perf_counter() - bald_started_at) * 1000.0, 3)
        except Exception as exc:
            logger.warning("rtc bald preprocessing failed: %s", exc)
            return (
                frame_bgr,
                tracking_result.user_row,
                "error",
                {
                    "tracking_latency_ms": tracking_latency_ms,
                    "bald_latency_ms": 0.0,
                },
            )

        if not isinstance(bald_rgb, np.ndarray) or bald_rgb.shape != frame_rgb.shape:
            return (
                frame_bgr,
                tracking_result.user_row,
                "invalid_output",
                {
                    "tracking_latency_ms": tracking_latency_ms,
                    "bald_latency_ms": bald_latency_ms,
                },
            )

        prepared_frame_bgr = cv2.cvtColor(bald_rgb, cv2.COLOR_RGB2BGR)
        cached_pose = tracking_result.user_row.get("pose", {})
        cached_face_bbox = tracking_result.user_row.get("face_bbox", {})
        self._state.bald_cache_frame_bgr = prepared_frame_bgr.copy()
        self._state.bald_cache_user_row = {
            "pose": {
                "yaw_float": float(cached_pose.get("yaw_float", cached_pose.get("yaw_1deg", 0.0))),
                "pitch_float": float(cached_pose.get("pitch_float", cached_pose.get("pitch_1deg", 0.0))),
                "roll_float": float(cached_pose.get("roll_float", cached_pose.get("roll_1deg", 0.0))),
                "yaw_1deg": int(cached_pose.get("yaw_1deg", round(float(cached_pose.get("yaw_float", 0.0))))),
                "pitch_1deg": int(cached_pose.get("pitch_1deg", round(float(cached_pose.get("pitch_float", 0.0))))),
                "roll_1deg": int(cached_pose.get("roll_1deg", round(float(cached_pose.get("roll_float", 0.0))))),
            },
            "face_bbox": {
                "x": float(cached_face_bbox.get("x", 0.0)),
                "y": float(cached_face_bbox.get("y", 0.0)),
                "w": float(cached_face_bbox.get("w", 0.0)),
                "h": float(cached_face_bbox.get("h", 0.0)),
            },
            "candidate_face_count": int(tracking_result.user_row.get("candidate_face_count") or 1),
        }
        self._state.bald_cache_reuse_count = 0

        return (
            prepared_frame_bgr,
            tracking_result.user_row,
            "applied",
            {
                "tracking_latency_ms": tracking_latency_ms,
                "bald_latency_ms": bald_latency_ms,
            },
        )

    def _resize_frame_for_processing(
        self,
        frame_bgr: np.ndarray,
    ) -> tuple[np.ndarray, tuple[int, int]]:
        frame_height, frame_width = frame_bgr.shape[:2]
        max_dimension = self._effective_process_max_dimension()
        if max_dimension <= 0 or max(frame_width, frame_height) <= max_dimension:
            return frame_bgr, (frame_width, frame_height)

        scale = float(max_dimension) / float(max(frame_width, frame_height))
        resized_width = max(1, int(round(frame_width * scale)))
        resized_height = max(1, int(round(frame_height * scale)))
        resized = cv2.resize(frame_bgr, (resized_width, resized_height), interpolation=cv2.INTER_AREA)
        return resized, (frame_width, frame_height)

    def _process_runtime_frame(
        self,
        frame_bgr: np.ndarray,
        seq: int,
        prefer_latency: bool,
    ) -> tuple[dict[str, Any], str, dict[str, float]]:
        prepared_frame_bgr, tracked_user_row, bald_status, prepare_metrics = self._prepare_frame_for_hair_runtime(frame_bgr, seq)
        runtime_result = self._hair_runtime_manager.process_frame(
            dataset_code=self._claims.dataset_code,
            frame_bgr=frame_bgr,
            render_frame_bgr=prepared_frame_bgr,
            tracked_user_row=tracked_user_row,
            prefer_latency=prefer_latency,
            session_id=self._claims.apply_session_id,
        )
        return runtime_result, bald_status, prepare_metrics

    async def _reader_loop(self) -> None:
        try:
            while True:
                frame = await self._source_track.recv()
                self._buffer.append(
                    BufferedVideoFrame(frame=frame, received_at_ms=time.monotonic() * 1000)
                )
                while len(self._buffer) > SERVER_TRACK_MAX_BUFFERED_VIDEO_FRAMES:
                    self._buffer.popleft()
                self._frame_available.set()
        except Exception:
            self._source_ended = True
            self._frame_available.set()

    async def _next_latest_frame(self) -> Any:
        while True:
            if self._buffer:
                latest = self._buffer.pop()
                self._buffer.clear()
                return latest.frame

            if self._source_ended:
                raise MediaStreamError

            self._frame_available.clear()
            await self._frame_available.wait()

    def stop(self) -> None:
        if not self._reader_task.done():
            self._reader_task.cancel()
        super().stop()

    def _emit_channel_payload(self, payload: dict[str, object]) -> None:
        channel = self._state.data_channel
        if channel is None or getattr(channel, "readyState", None) != "open":
            return
        channel.send(json.dumps(payload))

    async def recv(self) -> Any:
        frame_started_at = time.perf_counter()
        frame = await self._next_latest_frame()
        next_seq = self._state.server_processed_seq + 1
        frame_bgr = frame.to_ndarray(format="bgr24")
        self._state.server_processed_seq = next_seq
        resize_in_started_at = time.perf_counter()
        processing_frame_bgr, original_size = self._resize_frame_for_processing(frame_bgr)
        resize_in_latency_ms = round((time.perf_counter() - resize_in_started_at) * 1000.0, 3)
        prepare_metrics = {
            "tracking_latency_ms": 0.0,
            "bald_latency_ms": 0.0,
        }

        selected: AssetBundle | None = None
        changed = False
        try:
            runtime_started_at = time.perf_counter()
            prefer_latency = self._prefer_latency_runtime()
            runtime_result, bald_status, prepare_metrics = await asyncio.to_thread(
                self._process_runtime_frame,
                processing_frame_bgr,
                next_seq,
                prefer_latency,
            )
            runtime_latency_ms = round((time.perf_counter() - runtime_started_at) * 1000.0, 3)
        except Exception as exc:
            logger.warning("rtc hairddae runtime failed: %s", exc)
            return frame

        selected_asset_id = str(runtime_result.get("selected_asset_id") or "")
        if selected_asset_id:
            try:
                selected = self._catalog.bundle_for_runtime_selection(
                    dataset_code=self._claims.dataset_code,
                    asset_id=selected_asset_id,
                    score=(
                        None
                        if runtime_result.get("score") is None
                        else float(runtime_result["score"])
                    ),
                )
            except Exception as exc:
                logger.warning("rtc asset bundle build failed: %s", exc)
                selected = None

        if selected is not None:
            changed = self._state.last_asset_id != selected.asset_id
            self._state.last_selected_bundle = selected
            self._state.last_processed_seq = next_seq
            self._state.processed_count += 1
            if self._state.last_asset_id == selected.asset_id:
                self._state.stable_asset_count += 1
            else:
                self._state.last_asset_id = selected.asset_id
                self._state.stable_asset_count = 1
            if (
                not self._state.render_ready
                and self._state.processed_count >= SERVER_RENDER_READY_MIN_PROCESSED
                and self._state.stable_asset_count >= SERVER_RENDER_READY_MIN_STABLE_ASSET
            ):
                self._state.render_ready = True

            user_pose = runtime_result.get("user_row", {}).get("pose", {})
            raw_user_pose = runtime_result.get("raw_user_row", {}).get("pose", {})
            logger.info(
                (
                    "rtc hairddae feature: seq=%s changed=%s asset=%s "
                    "raw_pose=(%s,%s,%s) smooth_pose=(%s,%s,%s) mode=%s parsing=%s bald=%s profile=%s"
                ),
                next_seq,
                changed,
                selected.asset_id,
                raw_user_pose.get("yaw_1deg"),
                raw_user_pose.get("pitch_1deg"),
                raw_user_pose.get("roll_1deg"),
                user_pose.get("yaw_1deg"),
                user_pose.get("pitch_1deg"),
                user_pose.get("roll_1deg"),
                runtime_result.get("selection_mode"),
                runtime_result.get("user_parsing_status"),
                bald_status,
                "latency" if prefer_latency else "balanced",
            )
            self._emit_channel_payload(
                {
                    "type": "processed",
                    "apply_session_id": self._claims.apply_session_id,
                    "accepted_seq": next_seq,
                    "processed_seq": next_seq,
                    "changed": changed,
                    "queue_depth": 0,
                    "dropped_pending_count": 0,
                    "overloaded": False,
                    "asset": selected.to_message(),
                }
            )

        rendered_bgr = runtime_result.get("output_frame_bgr")
        resize_out_started_at = time.perf_counter()
        if not isinstance(rendered_bgr, np.ndarray):
            total_pipeline_latency_ms = round((time.perf_counter() - frame_started_at) * 1000.0, 3)
            self._state.recent_pipeline_latency_ms = total_pipeline_latency_ms
            self._update_adaptive_resolution(total_pipeline_latency_ms)
            now_ms = time.monotonic() * 1000.0
            if now_ms - self._state.last_perf_log_at_ms >= PERF_LOG_INTERVAL_MS:
                self._state.last_perf_log_at_ms = now_ms
                logger.info(
                    (
                        "rtc perf: seq=%s total=%.1f resize_in=%.1f tracking=%.1f "
                        "bald=%.1f hair_total=%.1f hair_feature=%.1f hair_overlay=%.1f "
                        "hair_parse=%.1f resize_out=%.1f process_size=%sx%s original_size=%sx%s "
                        "process_max_dimension=%s bald=%s asset=%s profile=%s output=passthrough"
                    ),
                    next_seq,
                    total_pipeline_latency_ms,
                    resize_in_latency_ms,
                    float(prepare_metrics.get("tracking_latency_ms", 0.0)),
                    float(prepare_metrics.get("bald_latency_ms", 0.0)),
                    runtime_latency_ms,
                    float(runtime_result.get("feature_latency_ms", 0.0) or 0.0),
                    float(runtime_result.get("overlay_latency_ms", 0.0) or 0.0),
                    float(runtime_result.get("user_parsing_latency_ms", 0.0) or 0.0),
                    0.0,
                    processing_frame_bgr.shape[1],
                    processing_frame_bgr.shape[0],
                    original_size[0],
                    original_size[1],
                    self._effective_process_max_dimension(),
                    bald_status,
                    runtime_result.get("selected_asset_id"),
                    "latency" if prefer_latency else "balanced",
                )
            return frame
        resize_out_latency_ms = round((time.perf_counter() - resize_out_started_at) * 1000.0, 3)
        total_pipeline_latency_ms = round((time.perf_counter() - frame_started_at) * 1000.0, 3)
        self._state.recent_pipeline_latency_ms = total_pipeline_latency_ms
        self._update_adaptive_resolution(total_pipeline_latency_ms)

        now_ms = time.monotonic() * 1000.0
        if now_ms - self._state.last_perf_log_at_ms >= PERF_LOG_INTERVAL_MS:
            self._state.last_perf_log_at_ms = now_ms
            logger.info(
                (
                    "rtc perf: seq=%s total=%.1f resize_in=%.1f tracking=%.1f "
                    "bald=%.1f hair_total=%.1f hair_feature=%.1f hair_overlay=%.1f "
                    "hair_parse=%.1f resize_out=%.1f process_size=%sx%s original_size=%sx%s "
                    "process_max_dimension=%s bald=%s asset=%s profile=%s"
                ),
                next_seq,
                total_pipeline_latency_ms,
                resize_in_latency_ms,
                float(prepare_metrics.get("tracking_latency_ms", 0.0)),
                float(prepare_metrics.get("bald_latency_ms", 0.0)),
                runtime_latency_ms,
                float(runtime_result.get("feature_latency_ms", 0.0) or 0.0),
                float(runtime_result.get("overlay_latency_ms", 0.0) or 0.0),
                float(runtime_result.get("user_parsing_latency_ms", 0.0) or 0.0),
                resize_out_latency_ms,
                processing_frame_bgr.shape[1],
                processing_frame_bgr.shape[0],
                original_size[0],
                original_size[1],
                self._effective_process_max_dimension(),
                bald_status,
                runtime_result.get("selected_asset_id"),
                "latency" if prefer_latency else "balanced",
            )

        next_frame = VideoFrame.from_ndarray(rendered_bgr, format="bgr24")
        next_frame.pts = frame.pts
        next_frame.time_base = frame.time_base
        return next_frame


def _normalize_ice_urls(raw_urls: Any) -> list[str]:
    if isinstance(raw_urls, str) and raw_urls:
        return [raw_urls]
    if isinstance(raw_urls, list):
        return [item for item in raw_urls if isinstance(item, str) and item]
    return []


def _ice_server_urls_for_log(ice_servers: tuple[dict[str, object], ...]) -> list[list[str]]:
    return [urls for payload in ice_servers if (urls := _normalize_ice_urls(payload.get("urls")))]


def _sdp_candidate_lines(description: Any) -> list[str]:
    sdp = getattr(description, "sdp", None)
    if not isinstance(sdp, str):
        return []
    return [line for line in sdp.splitlines() if line.startswith("a=candidate:")]


def _create_peer_connection(settings: Settings) -> Any:
    if RTCPeerConnection is None:
        return None
    if RTCConfiguration is None or RTCIceServer is None:
        return RTCPeerConnection()

    configured_ice_servers = (
        settings.rtc_internal_ice_servers
        if settings.rtc_internal_ice_servers
        else settings.rtc_ice_servers
    )
    logger.info("rtc configured ice servers: %s", _ice_server_urls_for_log(configured_ice_servers))

    ice_servers = []
    for payload in configured_ice_servers:
        urls = _normalize_ice_urls(payload.get("urls"))
        if not urls:
            continue

        username = payload.get("username")
        credential = payload.get("credential")
        ice_servers.append(
            RTCIceServer(
                urls=urls,
                username=username if isinstance(username, str) and username else None,
                credential=credential if isinstance(credential, str) and credential else None,
            )
        )

    if not ice_servers and RTCIceGatherer is not None:
        try:
            default_servers = RTCIceGatherer.getDefaultIceServers()
        except Exception:  # pragma: no cover - aiortc runtime variation
            default_servers = []
        if default_servers:
            logger.info(
                "rtc using aiortc default ice servers: %s",
                [
                    getattr(server, "urls", None)
                    for server in default_servers
                ],
            )
            ice_servers.extend(default_servers)

    if not ice_servers:
        return RTCPeerConnection()
    return RTCPeerConnection(configuration=RTCConfiguration(iceServers=ice_servers))


def _maybe_switch_asset(
    state: RtcSessionState,
    candidate: AssetBundle,
    settings: Settings,
    catalog: AssetCatalog,
    dataset_code: str,
    feature: FeatureMessageModel,
) -> tuple[bool, AssetBundle]:
    now_ms = _now_ms()
    if state.last_selected_bundle is None:
        state.last_selected_bundle = candidate
        state.last_switch_at_ms = now_ms
        return True, candidate

    if candidate.asset_id == state.last_selected_bundle.asset_id:
        state.last_selected_bundle = candidate
        return False, candidate

    current = catalog.bundle_for_asset(
        dataset_code=dataset_code,
        asset_id=state.last_selected_bundle.asset_id,
        feature=feature,
    )
    within_hold = now_ms - state.last_switch_at_ms < settings.min_hold_ms
    improved_enough = candidate.score + settings.hysteresis_margin < current.score
    if not within_hold and improved_enough:
        state.last_selected_bundle = candidate
        state.last_switch_at_ms = now_ms
        return True, candidate

    state.last_selected_bundle = current
    return False, current


def attach_rtc_routes(app: FastAPI) -> None:
    app.state.rtc_peer_connections = getattr(app.state, "rtc_peer_connections", set())

    @app.post("/rtc/offer")
    @app.post("/v2/rtc/offer")
    async def rtc_offer(payload: RtcOfferRequest) -> dict[str, str]:
        if RTCPeerConnection is None or RTCSessionDescription is None or VideoFrame is None:
            raise HTTPException(status_code=503, detail="RTC runtime is unavailable")

        settings: Settings = app.state.settings
        try:
            claims = await validate_connect_ticket(
                payload.connect_ticket,
                settings,
                app.state.replay_store,
            )
        except TicketValidationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

        logger.info("rtc offer accepted: apply_session_id=%s hair_id=%s", claims.apply_session_id, claims.hair_id)

        peer_connection = _create_peer_connection(settings)
        if peer_connection is None:
            raise HTTPException(status_code=503, detail="RTC runtime is unavailable")
        app.state.rtc_peer_connections.add(peer_connection)
        session_state = RtcSessionState()

        @peer_connection.on("connectionstatechange")
        async def _on_connectionstatechange() -> None:
            logger.info("rtc connection state changed: %s", peer_connection.connectionState)
            if peer_connection.connectionState not in {"failed", "disconnected", "closed"}:
                return
            await peer_connection.close()
            app.state.rtc_peer_connections.discard(peer_connection)

        @peer_connection.on("iceconnectionstatechange")
        async def _on_iceconnectionstatechange() -> None:
            logger.info("rtc ice connection state changed: %s", peer_connection.iceConnectionState)

        @peer_connection.on("icegatheringstatechange")
        async def _on_icegatheringstatechange() -> None:
            logger.info("rtc ice gathering state changed: %s", peer_connection.iceGatheringState)

        @peer_connection.on("datachannel")
        def _on_datachannel(channel: Any) -> None:
            logger.info("rtc data channel opened: label=%s", getattr(channel, "label", "unknown"))
            session_state.data_channel = channel
            channel.send(
                json.dumps(
                    {
                        "type": "connected",
                        "apply_session_id": claims.apply_session_id,
                        "node_id": settings.node_id,
                        "feature_schema_version": settings.feature_schema_version,
                        "transform_version": settings.transform_version,
                    }
                )
            )

            @channel.on("message")
            def _on_message(message: str | bytes) -> None:
                try:
                    raw_message = message.decode("utf-8") if isinstance(message, bytes) else message
                    parsed_message = json.loads(raw_message)
                    if parsed_message.get("type") != "heartbeat":
                        return
                    channel.send(
                        json.dumps(
                            {
                                "type": "heartbeat_ack",
                                "apply_session_id": claims.apply_session_id,
                                "ts_ms": _now_ms(),
                            }
                        )
                    )
                except Exception as exc:  # pragma: no cover - browser interoperability
                    logger.warning("rtc feature processing failed: %s", exc)
                    channel.send(
                        json.dumps(
                            {
                                "type": "error",
                                "code": 400,
                                "message": str(exc),
                            }
                        )
                    )

        @peer_connection.on("track")
        def _on_track(track: Any) -> None:
            if track.kind != "video":
                return
            logger.info("rtc video track received")
            peer_connection.addTrack(
                RtcServerTrackedRenderTrack(
                    track,
                    session_state,
                    claims=claims,
                    settings=settings,
                    catalog=app.state.catalog,
                    hair_runtime_manager=app.state.hair_runtime_manager,
                    face_tracker=app.state.face_tracker,
                    bald_processor=getattr(app.state, "bald_processor", None),
                )
            )

        await peer_connection.setRemoteDescription(
            RTCSessionDescription(sdp=payload.sdp, type=payload.type)
        )
        logger.info(
            "rtc remote candidates: %s",
            _sdp_candidate_lines(peer_connection.remoteDescription),
        )
        answer = await peer_connection.createAnswer()
        await peer_connection.setLocalDescription(answer)
        await _wait_for_ice_gathering_complete(peer_connection)

        local_description = peer_connection.localDescription
        if local_description is None:
            raise HTTPException(status_code=500, detail="failed to create RTC answer")

        logger.info(
            "rtc local candidates: %s",
            _sdp_candidate_lines(local_description),
        )

        return {
            "sdp": local_description.sdp,
            "type": local_description.type,
        }
