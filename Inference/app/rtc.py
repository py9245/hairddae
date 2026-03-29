from __future__ import annotations

import asyncio
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
import fractions
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
from app.catalog import AssetBundle, AssetCatalog
from app.config import DEFAULT_RTC_FPS, Settings
from app.face_tracking import ServerFaceTracker
from app.fallback_render_pipeline import render_bundle_fallback_frame
from app.frame_prepare_pipeline import TrackingCacheSnapshot, prepare_runtime_frame
from app.hair_attenuation import HairAttenuator
from app.hairddae_runtime_manager import HairddaeRuntimeManager
from app.models import FeatureMessageModel
from app.server_render import compose_bundle_frame
from cv2_cuda_utils import opencv_flip, opencv_resize

try:
    from aiortc import (
        RTCConfiguration,
        RTCIceGatherer,
        RTCIceServer,
        RTCPeerConnection,
        RTCSessionDescription,
        VideoStreamTrack,
    )
    from aiortc.mediastreams import MediaStreamError, VIDEO_CLOCK_RATE, VIDEO_TIME_BASE
    from av import VideoFrame
except ImportError:  # pragma: no cover - runtime guarded
    RTCConfiguration = None
    RTCIceGatherer = None
    RTCIceServer = None
    RTCPeerConnection = None
    RTCSessionDescription = None
    VideoStreamTrack = object
    MediaStreamError = RuntimeError
    VIDEO_CLOCK_RATE = 90000
    VIDEO_TIME_BASE = fractions.Fraction(1, 90000)
    VideoFrame = None


logger = logging.getLogger("uvicorn.error")
RENDER_FRAME_DELAY_MS = 1000.0 / float(DEFAULT_RTC_FPS)
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


@dataclass(frozen=True)
class HairControlTarget:
    hair_id: int
    dataset_code: str
    representative_asset_id: str | None = None


class ControlMessageError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


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
    current_process_max_dimension: int | None = None
    slow_frame_streak: int = 0
    fast_frame_streak: int = 0
    last_perf_log_at_ms: float = 0.0
    recent_pipeline_latency_ms: float = 0.0
    active_hair_id: int | None = None
    active_dataset_code: str | None = None
    active_representative_asset_id: str | None = None
    hello_received: bool = False
    stage_width: int | None = None
    stage_height: int | None = None
    stage_fps: float | None = None
    mirrored: bool = False
    stage_mismatch_reported: bool = False
    last_stats_sent_at_ms: float = 0.0
    last_tracking_user_row: dict[str, Any] | None = None
    last_tracking_landmarks_px: np.ndarray | None = None
    last_tracking_feature: FeatureMessageModel | None = None
    control_message_count: int = 0
    control_error_count: int = 0
    control_message_total_bytes: int = 0
    last_control_message_type: str | None = None
    last_control_message_bytes: int = 0
    last_control_message_client_ts_ms: int | None = None
    last_control_message_server_ts_ms: int | None = None
    last_control_message_latency_ms: float = 0.0
    last_control_error_code: str | None = None
    last_control_response_count: int = 0
    data_channel_send_count: int = 0
    last_channel_payload_type: str | None = None
    last_channel_send_latency_ms: float = 0.0
    last_channel_buffered_amount: int = 0


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


def _control_error_payload(code: str, message: str) -> dict[str, object]:
    return {
        "type": "error",
        "code": code,
        "message": message,
    }


def _raw_message_size_bytes(raw_message: str | bytes) -> int:
    if isinstance(raw_message, bytes):
        return len(raw_message)
    return len(raw_message.encode("utf-8", errors="ignore"))


def _extract_control_message_debug(raw_message: str | bytes) -> tuple[str | None, int | None]:
    try:
        decoded = raw_message.decode("utf-8") if isinstance(raw_message, bytes) else raw_message
        parsed = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, None
    if not isinstance(parsed, dict):
        return None, None
    message_type = _optional_str(parsed.get("type"))
    client_ts_ms = None
    ts_value = parsed.get("ts_ms")
    if ts_value is not None:
        try:
            client_ts_ms = int(ts_value)
        except (TypeError, ValueError):
            client_ts_ms = None
    return message_type, client_ts_ms


def _channel_observability_payload(channel: Any | None) -> dict[str, object]:
    if channel is None:
        return {
            "data_channel_ready_state": "missing",
            "data_channel_buffered_amount": 0,
            "data_channel_label": "",
        }
    payload: dict[str, object] = {
        "data_channel_ready_state": str(getattr(channel, "readyState", "") or ""),
        "data_channel_buffered_amount": int(getattr(channel, "bufferedAmount", 0) or 0),
        "data_channel_label": str(getattr(channel, "label", "") or ""),
    }
    low_threshold = getattr(channel, "bufferedAmountLowThreshold", None)
    if low_threshold is not None:
        payload["data_channel_buffered_amount_low_threshold"] = int(low_threshold)
    return payload


def _augment_control_payload(
    payload: dict[str, object],
    *,
    message_type: str | None,
    message_bytes: int,
    server_received_ts_ms: int,
    processing_ms: float,
    response_index: int,
    response_count: int,
    channel: Any | None,
    client_ts_ms: int | None = None,
) -> dict[str, object]:
    enriched = dict(payload)
    enriched["control_message_type"] = message_type or ""
    enriched["control_message_bytes"] = int(message_bytes)
    enriched["control_processing_ms"] = round(float(processing_ms), 3)
    enriched["control_response_index"] = int(response_index)
    enriched["control_response_count"] = int(response_count)
    enriched["server_received_ts_ms"] = int(server_received_ts_ms)
    enriched["server_sent_ts_ms"] = _now_ms()
    if client_ts_ms is not None and enriched.get("client_ts_ms") is None:
        enriched["client_ts_ms"] = int(client_ts_ms)
    enriched.update(_channel_observability_payload(channel))
    return enriched


def _send_channel_json(
    channel: Any | None,
    state: RtcSessionState | None,
    payload: dict[str, object],
) -> bool:
    if channel is None or getattr(channel, "readyState", None) != "open":
        return False
    send_started_at = time.perf_counter()
    serialized = json.dumps(payload)
    channel.send(serialized)
    if state is not None:
        state.data_channel_send_count += 1
        state.last_channel_payload_type = str(payload.get("type") or "")
        state.last_channel_send_latency_ms = round((time.perf_counter() - send_started_at) * 1000.0, 3)
        state.last_channel_buffered_amount = int(getattr(channel, "bufferedAmount", 0) or 0)
    return True


def _optional_str(value: object) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def _positive_int(value: object, field_name: str) -> int:
    try:
        resolved = int(value)
    except (TypeError, ValueError) as exc:
        raise ControlMessageError("INVALID_CONTROL_MESSAGE", f"{field_name} must be an integer") from exc
    if resolved <= 0:
        raise ControlMessageError("INVALID_CONTROL_MESSAGE", f"{field_name} must be positive")
    return resolved


def _positive_float(value: object, field_name: str) -> float:
    try:
        resolved = float(value)
    except (TypeError, ValueError) as exc:
        raise ControlMessageError("INVALID_CONTROL_MESSAGE", f"{field_name} must be numeric") from exc
    if resolved <= 0:
        raise ControlMessageError("INVALID_CONTROL_MESSAGE", f"{field_name} must be positive")
    return resolved


def _bool_value(value: object, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ControlMessageError("INVALID_CONTROL_MESSAGE", f"{field_name} must be a boolean")


def _non_negative_int(value: object, field_name: str) -> int:
    try:
        resolved = int(value)
    except (TypeError, ValueError) as exc:
        raise ControlMessageError("INVALID_CONTROL_MESSAGE", f"{field_name} must be an integer") from exc
    if resolved < 0:
        raise ControlMessageError("INVALID_CONTROL_MESSAGE", f"{field_name} must be non-negative")
    return resolved


def _active_hair_target(state: RtcSessionState, claims: Any) -> HairControlTarget:
    return HairControlTarget(
        hair_id=int(claims.hair_id if state.active_hair_id is None else state.active_hair_id),
        dataset_code=str(claims.dataset_code if state.active_dataset_code is None else state.active_dataset_code),
        representative_asset_id=(
            claims.representative_asset_id
            if state.active_representative_asset_id is None
            else state.active_representative_asset_id
        ),
    )


def _mapped_hair_target(settings: Settings, hair_id: int) -> HairControlTarget | None:
    for payload in settings.rtc_hair_control_map:
        try:
            mapped_hair_id = int(payload.get("hair_id"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if mapped_hair_id != hair_id:
            continue

        dataset_code = _optional_str(payload.get("dataset_code"))
        if dataset_code is None:
            continue
        return HairControlTarget(
            hair_id=mapped_hair_id,
            dataset_code=dataset_code,
            representative_asset_id=_optional_str(payload.get("representative_asset_id")),
        )
    return None


def _resolve_hair_target(
    payload: dict[str, object],
    *,
    state: RtcSessionState,
    settings: Settings,
    claims: Any,
    catalog: AssetCatalog,
) -> HairControlTarget:
    hair_id = _positive_int(payload.get("hair_id"), "hair_id")
    dataset_code = _optional_str(payload.get("dataset_code"))
    representative_asset_id = _optional_str(payload.get("representative_asset_id"))
    current_target = _active_hair_target(state, claims)

    if dataset_code is None:
        if current_target.hair_id == hair_id:
            dataset_code = current_target.dataset_code
            if representative_asset_id is None:
                representative_asset_id = current_target.representative_asset_id
        else:
            mapped_target = _mapped_hair_target(settings, hair_id)
            if mapped_target is not None:
                dataset_code = mapped_target.dataset_code
                if representative_asset_id is None:
                    representative_asset_id = mapped_target.representative_asset_id

    if dataset_code is None:
        raise ControlMessageError(
            "HAIR_MAPPING_NOT_FOUND",
            f"unable to resolve dataset_code for hair_id {hair_id}",
        )

    try:
        catalog.ensure_control_target(dataset_code, representative_asset_id)
    except ValueError as exc:
        message = str(exc)
        if "dataset_code" in message:
            raise ControlMessageError("DATASET_NOT_FOUND", message) from exc
        if "representative_asset_id" in message:
            raise ControlMessageError("ASSET_NOT_FOUND", message) from exc
        raise ControlMessageError("INVALID_CONTROL_MESSAGE", message) from exc

    return HairControlTarget(
        hair_id=hair_id,
        dataset_code=dataset_code,
        representative_asset_id=representative_asset_id,
    )


def _reset_runtime_control_state(state: RtcSessionState) -> None:
    state.latest_feature = None
    state.last_selected_bundle = None
    state.last_switch_at_ms = 0
    state.last_processed_seq = 0
    state.processed_count = 0
    state.stable_asset_count = 0
    state.last_asset_id = None
    state.render_ready = False
    state.processed_bundle_history.clear()
    state.pose_window.clear()


def _apply_hair_target(
    state: RtcSessionState,
    target: HairControlTarget,
    *,
    hair_runtime_manager: HairddaeRuntimeManager,
    session_id: str,
) -> bool:
    previous_dataset_code = state.active_dataset_code
    changed = (
        state.active_hair_id != target.hair_id
        or state.active_dataset_code != target.dataset_code
        or state.active_representative_asset_id != target.representative_asset_id
    )
    state.active_hair_id = target.hair_id
    state.active_dataset_code = target.dataset_code
    state.active_representative_asset_id = target.representative_asset_id
    if changed:
        _reset_runtime_control_state(state)
        if previous_dataset_code not in (None, "", target.dataset_code):
            hair_runtime_manager.reset_session(previous_dataset_code, session_id)
        hair_runtime_manager.reset_session(target.dataset_code, session_id)
    return changed


def _hair_applied_payload(
    *,
    target: HairControlTarget,
    source: str,
    changed: bool,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "type": "hair_applied",
        "hair_id": target.hair_id,
        "dataset_code": target.dataset_code,
        "changed": changed,
        "source": source,
        "server_ts_ms": _now_ms(),
    }
    if target.representative_asset_id:
        payload["representative_asset_id"] = target.representative_asset_id
    return payload


def _process_control_message(
    raw_message: str | bytes,
    *,
    state: RtcSessionState,
    settings: Settings,
    claims: Any,
    catalog: AssetCatalog,
    hair_runtime_manager: HairddaeRuntimeManager,
) -> list[dict[str, object]]:
    try:
        decoded = raw_message.decode("utf-8") if isinstance(raw_message, bytes) else raw_message
        parsed = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ControlMessageError("INVALID_CONTROL_MESSAGE", "message must be valid JSON") from exc

    if not isinstance(parsed, dict):
        raise ControlMessageError("INVALID_CONTROL_MESSAGE", "message must be a JSON object")

    message_type = _optional_str(parsed.get("type"))
    if message_type is None:
        raise ControlMessageError("INVALID_CONTROL_MESSAGE", "message.type is required")

    if message_type == "heartbeat":
        ts_ms = (
            _non_negative_int(parsed.get("ts_ms"), "ts_ms")
            if parsed.get("ts_ms") is not None
            else _now_ms()
        )
        return [
            {
                "type": "heartbeat_ack",
                "apply_session_id": claims.apply_session_id,
                "ts_ms": ts_ms,
                "server_ts_ms": _now_ms(),
            }
        ]

    if message_type == "hello":
        session_version = _positive_int(parsed.get("session_version", 1), "session_version")
        if session_version != 1:
            raise ControlMessageError("UNSUPPORTED_SESSION_VERSION", f"unsupported session_version {session_version}")

        state.stage_width = _positive_int(parsed.get("stage_width"), "stage_width")
        state.stage_height = _positive_int(parsed.get("stage_height"), "stage_height")
        state.stage_fps = _positive_float(parsed.get("fps"), "fps")
        state.mirrored = (
            settings.rtc_mirrored_input
            if parsed.get("mirrored") is None
            else _bool_value(parsed.get("mirrored"), "mirrored")
        )
        state.hello_received = True

        if parsed.get("hair_id") is None:
            return []

        target = _resolve_hair_target(
            parsed,
            state=state,
            settings=settings,
            claims=claims,
            catalog=catalog,
        )
        changed = _apply_hair_target(
            state,
            target,
            hair_runtime_manager=hair_runtime_manager,
            session_id=claims.apply_session_id,
        )
        return [
            _hair_applied_payload(
                target=target,
                source="hello",
                changed=changed,
            )
        ]

    if message_type == "select_hair":
        if settings.rtc_require_hello and not state.hello_received:
            raise ControlMessageError("HELLO_REQUIRED", "hello must be received before select_hair")
        target = _resolve_hair_target(
            parsed,
            state=state,
            settings=settings,
            claims=claims,
            catalog=catalog,
        )
        changed = _apply_hair_target(
            state,
            target,
            hair_runtime_manager=hair_runtime_manager,
            session_id=claims.apply_session_id,
        )
        return [
            _hair_applied_payload(
                target=target,
                source="select_hair",
                changed=changed,
            )
        ]

    raise ControlMessageError(
        "UNSUPPORTED_CONTROL_MESSAGE",
        f"unsupported control message type {message_type}",
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
        hair_segmenter: Any | None,
        hair_attenuator: HairAttenuator | None,
    ) -> None:
        super().__init__()
        self._source_track = source_track
        self._state = state
        self._claims = claims
        self._settings = settings
        self._catalog = catalog
        self._hair_runtime_manager = hair_runtime_manager
        self._face_tracker = face_tracker
        self._hair_segmenter = hair_segmenter
        self._hair_attenuator = hair_attenuator
        self._buffer: deque[BufferedVideoFrame] = deque()
        self._frame_available = asyncio.Event()
        self._source_ended = False
        self._last_output_sent_at_ms = 0.0
        self._output_timestamp: int | None = None
        self._last_input_pts: int | None = None
        self._last_output_pts_sent: int | None = None
        self._input_pts_duplicate_count = 0
        self._input_pts_rewind_count = 0
        self._output_pts_duplicate_count = 0
        self._output_pts_rewind_count = 0
        self._tracking_snapshot = TrackingCacheSnapshot(
            user_row=None,
            landmarks_px=None,
            feature=None,
        )
        self._prepare_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="rtc-prepare")
        self._reader_task = asyncio.create_task(self._reader_loop())

    def _active_target(self) -> HairControlTarget:
        return _active_hair_target(self._state, self._claims)

    def _active_dataset_code(self) -> str:
        return self._active_target().dataset_code

    def _active_hair_id(self) -> int:
        return self._active_target().hair_id

    def _active_representative_asset_id(self) -> str | None:
        return self._active_target().representative_asset_id

    def _mirrored_input(self) -> bool:
        if self._state.hello_received:
            return bool(self._state.mirrored)
        return bool(self._settings.rtc_mirrored_input)

    def _mirrored_output(self) -> bool:
        return bool(self._settings.rtc_output_mirrored)

    def _output_interval_ms(self) -> float:
        configured_fps = max(1, int(getattr(self._settings, "rtc_output_fps", DEFAULT_RTC_FPS) or DEFAULT_RTC_FPS))
        return 1000.0 / float(configured_fps)

    def _target_output_size(self, original_size: tuple[int, int]) -> tuple[int, int]:
        configured_width = max(0, int(getattr(self._settings, "rtc_output_width", 0) or 0))
        configured_height = max(0, int(getattr(self._settings, "rtc_output_height", 0) or 0))
        if configured_width <= 0 or configured_height <= 0:
            return original_size
        return configured_width, configured_height

    def _next_output_timestamp(self) -> tuple[int, fractions.Fraction]:
        configured_fps = max(1, int(getattr(self._settings, "rtc_output_fps", DEFAULT_RTC_FPS) or DEFAULT_RTC_FPS))
        increment = max(1, int(round(VIDEO_CLOCK_RATE / float(configured_fps))))
        if self._output_timestamp is None:
            self._output_timestamp = 0
        else:
            self._output_timestamp += increment
        return self._output_timestamp, VIDEO_TIME_BASE

    @staticmethod
    def _time_base_to_str(time_base: Any) -> str | None:
        if time_base is None:
            return None
        try:
            numerator = getattr(time_base, "numerator", None)
            denominator = getattr(time_base, "denominator", None)
            if numerator is not None and denominator is not None:
                return f"{numerator}/{denominator}"
            return str(time_base)
        except Exception:
            return None

    @staticmethod
    def _pts_to_ms(pts: int | None, time_base: Any) -> float | None:
        if pts is None or time_base is None:
            return None
        try:
            return round(float(pts) * float(time_base) * 1000.0, 3)
        except Exception:
            return None

    def _record_input_pts(self, pts: int | None) -> None:
        if pts is None:
            return
        if self._last_input_pts is not None:
            if pts == self._last_input_pts:
                self._input_pts_duplicate_count += 1
            elif pts < self._last_input_pts:
                self._input_pts_rewind_count += 1
        self._last_input_pts = pts

    def _record_output_pts(self, pts: int | None) -> None:
        if pts is None:
            return
        if self._last_output_pts_sent is not None:
            if pts == self._last_output_pts_sent:
                self._output_pts_duplicate_count += 1
            elif pts < self._last_output_pts_sent:
                self._output_pts_rewind_count += 1
        self._last_output_pts_sent = pts

    async def _wait_for_next_output_slot(self) -> None:
        interval_ms = self._output_interval_ms()
        if self._last_output_sent_at_ms <= 0.0 or interval_ms <= 0.0:
            return
        now_ms = time.monotonic() * 1000.0
        wait_ms = self._last_output_sent_at_ms + interval_ms - now_ms
        if wait_ms > 0.0:
            await asyncio.sleep(wait_ms / 1000.0)

    def _maybe_emit_stage_mismatch_error(self, frame_width: int, frame_height: int) -> None:
        if self._state.stage_mismatch_reported or not self._state.hello_received:
            return
        if self._state.stage_width is None or self._state.stage_height is None:
            return
        if self._state.stage_width == frame_width and self._state.stage_height == frame_height:
            return
        self._state.stage_mismatch_reported = True
        self._emit_channel_payload(
            _control_error_payload(
                "STAGE_MISMATCH",
                (
                    f"hello stage {self._state.stage_width}x{self._state.stage_height} "
                    f"does not match incoming track {frame_width}x{frame_height}"
                ),
            )
        )

    def _maybe_emit_stats(
        self,
        *,
        queue_depth: int,
        decode_latency_ms: float,
        tracking_latency_ms: float,
        hair_segmentation_latency_ms: float,
        hair_attenuation_latency_ms: float,
        infer_latency_ms: float,
        render_latency_ms: float,
        encode_latency_ms: float,
        user_parsing_latency_ms: float,
        total_pipeline_latency_ms: float,
        selected_asset_id: str | None,
    ) -> None:
        interval_ms = int(getattr(self._settings, "rtc_stats_interval_ms", 0) or 0)
        if interval_ms <= 0:
            return

        now_ms = time.monotonic() * 1000.0
        if now_ms - self._state.last_stats_sent_at_ms < interval_ms:
            return
        self._state.last_stats_sent_at_ms = now_ms

        payload: dict[str, object] = {
            "type": "stats",
            "queue_depth": max(0, int(queue_depth)),
            "dropped_pending_count": int(self._state.dropped_pending_count),
            "decode_ms": round(float(decode_latency_ms), 3),
            "tracking_ms": round(float(tracking_latency_ms), 3),
            "hair_segmentation_ms": round(float(hair_segmentation_latency_ms), 3),
            "hair_attenuation_ms": round(float(hair_attenuation_latency_ms), 3),
            "infer_ms": round(float(infer_latency_ms), 3),
            "render_ms": round(float(render_latency_ms), 3),
            "user_parsing_ms": round(float(user_parsing_latency_ms), 3),
            "encode_ms": round(float(encode_latency_ms), 3),
            "e2e_estimate_ms": round(float(total_pipeline_latency_ms), 3),
            "hair_id": self._active_hair_id(),
            "dataset_code": self._active_dataset_code(),
            "mirrored": self._mirrored_input(),
            "output_mirrored": self._mirrored_output(),
            "selected_asset_id": selected_asset_id or "",
            "server_ts_ms": _now_ms(),
        }
        if self._state.stage_width is not None and self._state.stage_height is not None:
            payload["stage_width"] = int(self._state.stage_width)
            payload["stage_height"] = int(self._state.stage_height)
        if self._state.stage_fps is not None:
            payload["stage_fps"] = round(float(self._state.stage_fps), 3)

        self._emit_channel_payload(payload)

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
        slow_ratio = max(
            1.0,
            float(getattr(self._settings, "rtc_adaptive_slow_threshold_ratio", 1.45) or 1.45),
        )
        fast_ratio = min(
            0.99,
            max(0.1, float(getattr(self._settings, "rtc_adaptive_fast_threshold_ratio", 0.78) or 0.78)),
        )
        slow_threshold = target_latency_ms * slow_ratio
        fast_threshold = target_latency_ms * fast_ratio

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
    ) -> tuple[np.ndarray, dict[str, Any] | None, str, dict[str, float], FeatureMessageModel | None]:
        prepared = prepare_runtime_frame(
            frame_bgr,
            seq=seq,
            face_tracker=self._face_tracker,
            hair_segmenter=self._hair_segmenter,
            hair_attenuator=self._hair_attenuator,
            hair_runtime_manager=self._hair_runtime_manager,
            claims=self._claims,
            settings=self._settings,
            active_dataset_code=self._active_dataset_code(),
            active_hair_id=self._active_hair_id(),
            prepare_executor=self._prepare_executor,
            previous_tracking_snapshot=self._tracking_snapshot,
        )
        self._tracking_snapshot = prepared.tracking_snapshot
        self._state.last_tracking_user_row = (
            None
            if prepared.tracking_snapshot.user_row is None
            else dict(prepared.tracking_snapshot.user_row)
        )
        self._state.last_tracking_landmarks_px = (
            None
            if prepared.tracking_snapshot.landmarks_px is None
            else np.array(prepared.tracking_snapshot.landmarks_px, copy=True)
        )
        self._state.last_tracking_feature = prepared.tracking_snapshot.feature
        return (
            prepared.prepared_frame_bgr,
            prepared.tracked_user_row,
            prepared.attenuation_status,
            prepared.metrics.as_dict(),
            prepared.tracking_feature,
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
        resized = opencv_resize(frame_bgr, (resized_width, resized_height), interpolation=cv2.INTER_AREA)
        return resized, (frame_width, frame_height)

    def _process_runtime_frame(
        self,
        frame_bgr: np.ndarray,
        seq: int,
        prefer_latency: bool,
    ) -> tuple[dict[str, Any], str, dict[str, float], FeatureMessageModel | None]:
        prepared_frame_bgr, tracked_user_row, attenuation_status, prepare_metrics, tracking_feature = self._prepare_frame_for_hair_runtime(frame_bgr, seq)
        if bool(getattr(self._settings, "rtc_disable_hair_overlay", False)):
            prepared_only_result: dict[str, Any] = {
                "output_frame_bgr": prepared_frame_bgr,
                "selected_asset_id": "",
                "selected_pose_key": "",
                "score": None,
                "status": "ok",
                "selection_mode": "prepared_only",
                "renderer_name": "disabled",
                "feature_latency_ms": 0.0,
                "primary_overlay_latency_ms": 0.0,
                "overlay_latency_ms": 0.0,
                "fallback_latency_ms": 0.0,
                "user_parsing_latency_ms": 0.0,
                "user_parsing_status": "skipped",
                "overlay_detail_ms": {"overlay_disabled": True},
                "compose_detail_ms": {"compose_mode": "prepared_only"},
                "bundle_detail_ms": {},
                "selection_trace": {"overlay_detail_ms": {"overlay_disabled": True}},
                "fallback_allowed": False,
                "user_row": tracked_user_row or {},
                "raw_user_row": tracked_user_row or {},
            }
            return prepared_only_result, attenuation_status, prepare_metrics, tracking_feature
        runtime_result = self._hair_runtime_manager.process_frame(
            dataset_code=self._active_dataset_code(),
            frame_bgr=frame_bgr,
            render_frame_bgr=prepared_frame_bgr,
            source_frame_bgr=prepared_frame_bgr,
            tracked_user_row=tracked_user_row,
            prefer_latency=prefer_latency,
            session_id=self._claims.apply_session_id,
            representative_asset_id=self._active_representative_asset_id(),
            encode_output=False,
        )
        return runtime_result, attenuation_status, prepare_metrics, tracking_feature

    def _render_bundle_fallback_frame(
        self,
        frame_bgr: np.ndarray,
        original_frame_bgr: np.ndarray | None,
        feature: FeatureMessageModel,
    ) -> tuple[np.ndarray | None, AssetBundle | None, float]:
        result = render_bundle_fallback_frame(
            frame_bgr,
            original_frame_bgr,
            feature,
            catalog=self._catalog,
            dataset_code=self._active_dataset_code(),
            representative_asset_id=self._active_representative_asset_id(),
        )
        return result.rendered_bgr, result.bundle, result.latency_ms

    async def _reader_loop(self) -> None:
        try:
            while True:
                frame = await self._source_track.recv()
                self._buffer.append(
                    BufferedVideoFrame(frame=frame, received_at_ms=time.monotonic() * 1000)
                )
                while len(self._buffer) > max(1, int(self._settings.rtc_max_pending_frames)):
                    self._buffer.popleft()
                    self._state.dropped_pending_count += 1
                self._frame_available.set()
        except Exception:
            self._source_ended = True
            self._frame_available.set()

    async def _next_latest_frame(self) -> BufferedVideoFrame:
        while True:
            if self._buffer:
                latest = self._buffer.pop()
                dropped_pending = len(self._buffer)
                if dropped_pending > 0:
                    self._state.dropped_pending_count += dropped_pending
                self._buffer.clear()
                return latest

            if self._source_ended:
                raise MediaStreamError

            self._frame_available.clear()
            await self._frame_available.wait()

    def stop(self) -> None:
        if not self._reader_task.done():
            self._reader_task.cancel()
        self._prepare_executor.shutdown(wait=False, cancel_futures=True)
        super().stop()

    def _emit_channel_payload(self, payload: dict[str, object]) -> None:
        _send_channel_json(self._state.data_channel, self._state, payload)

    async def recv(self) -> Any:
        await self._wait_for_next_output_slot()
        frame_started_at = time.perf_counter()
        buffered_frame = await self._next_latest_frame()
        frame = buffered_frame.frame
        input_pts = getattr(frame, "pts", None)
        input_time_base = getattr(frame, "time_base", None)
        self._record_input_pts(input_pts)
        input_time_base_str = self._time_base_to_str(input_time_base)
        input_pts_ms = self._pts_to_ms(input_pts, input_time_base)
        next_seq = self._state.server_processed_seq + 1
        frame_age_ms = round(max(0.0, time.monotonic() * 1000.0 - buffered_frame.received_at_ms), 3)
        decode_started_at = time.perf_counter()
        frame_bgr = frame.to_ndarray(format="bgr24")
        processing_source_bgr = opencv_flip(frame_bgr, 1) if self._mirrored_input() else frame_bgr
        decode_latency_ms = round((time.perf_counter() - decode_started_at) * 1000.0, 3)
        self._maybe_emit_stage_mismatch_error(frame_bgr.shape[1], frame_bgr.shape[0])
        self._state.server_processed_seq = next_seq
        resize_in_started_at = time.perf_counter()
        processing_frame_bgr, original_size = self._resize_frame_for_processing(processing_source_bgr)
        resize_in_latency_ms = round((time.perf_counter() - resize_in_started_at) * 1000.0, 3)
        prepare_metrics = {
            "tracking_latency_ms": 0.0,
            "hair_attenuation_latency_ms": 0.0,
        }
        queue_depth = len(self._buffer)

        selected: AssetBundle | None = None
        changed = False
        try:
            runtime_started_at = time.perf_counter()
            prefer_latency = self._prefer_latency_runtime()
            runtime_result, attenuation_status, prepare_metrics, tracking_feature = await asyncio.to_thread(
                self._process_runtime_frame,
                processing_frame_bgr,
                next_seq,
                prefer_latency,
            )
            runtime_latency_ms = round((time.perf_counter() - runtime_started_at) * 1000.0, 3)
        except Exception as exc:
            logger.warning("rtc hairddae runtime failed: %s", exc)
            pts, time_base = self._next_output_timestamp()
            self._record_output_pts(pts)
            frame.pts = pts
            frame.time_base = time_base
            self._last_output_sent_at_ms = time.monotonic() * 1000.0
            return frame

        fallback_allowed = bool(runtime_result.get("fallback_allowed", True))
        if (
            fallback_allowed
            and
            tracking_feature is not None
            and (
                str(runtime_result.get("status") or "") == "overlay_error"
                or not str(runtime_result.get("selected_asset_id") or "")
            )
        ):
            fallback_source_bgr = runtime_result.get("output_frame_bgr")
            if not isinstance(fallback_source_bgr, np.ndarray):
                fallback_source_bgr = processing_frame_bgr
            fallback_rendered_bgr, fallback_bundle, fallback_latency_ms = await asyncio.to_thread(
                self._render_bundle_fallback_frame,
                fallback_source_bgr,
                processing_frame_bgr,
                tracking_feature,
            )
            if fallback_rendered_bgr is not None and fallback_bundle is not None:
                runtime_result["output_frame_bgr"] = fallback_rendered_bgr
                runtime_result["selected_asset_id"] = fallback_bundle.asset_id
                runtime_result["selected_pose_key"] = fallback_bundle.pose_key
                runtime_result["score"] = fallback_bundle.score
                runtime_result["status"] = "degraded_ok"
                runtime_result["selection_mode"] = "bundle_render_fallback"
                primary_overlay_latency_ms = round(
                    float(
                        runtime_result.get(
                            "primary_overlay_latency_ms",
                            runtime_result.get("overlay_latency_ms", 0.0),
                        )
                        or 0.0
                    ),
                    3,
                )
                runtime_result["primary_overlay_latency_ms"] = primary_overlay_latency_ms
                runtime_result["fallback_latency_ms"] = round(float(fallback_latency_ms), 3)
                runtime_result["overlay_latency_ms"] = round(
                    primary_overlay_latency_ms + fallback_latency_ms,
                    3,
                )
                overlay_detail_ms = runtime_result.get("overlay_detail_ms")
                if isinstance(overlay_detail_ms, dict):
                    merged_overlay_detail_ms = dict(overlay_detail_ms)
                    merged_overlay_detail_ms["fallback_ms"] = round(float(fallback_latency_ms), 3)
                    merged_overlay_detail_ms["overlay_total_after_fallback_ms"] = float(
                        runtime_result["overlay_latency_ms"]
                    )
                    runtime_result["overlay_detail_ms"] = merged_overlay_detail_ms
                    selection_trace = runtime_result.get("selection_trace")
                    if isinstance(selection_trace, dict):
                        merged_selection_trace = dict(selection_trace)
                        merged_selection_trace["overlay_detail_ms"] = merged_overlay_detail_ms
                        runtime_result["selection_trace"] = merged_selection_trace
                logger.info(
                    "rtc bundle render fallback applied: asset=%s latency_ms=%.1f",
                    fallback_bundle.asset_id,
                    fallback_latency_ms,
                )
                selected = fallback_bundle

        selected_asset_id = str(runtime_result.get("selected_asset_id") or "")
        if selected is None and selected_asset_id:
            try:
                selected = self._catalog.bundle_for_runtime_selection(
                    dataset_code=self._active_dataset_code(),
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
                    "raw_pose=(%s,%s,%s) smooth_pose=(%s,%s,%s) mode=%s renderer=%s parsing=%s attenuation=%s profile=%s"
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
                runtime_result.get("renderer_name"),
                runtime_result.get("user_parsing_status"),
                attenuation_status,
                "latency" if prefer_latency else "balanced",
            )
            if self._settings.rtc_send_processed_events:
                self._emit_channel_payload(
                    {
                        "type": "processed",
                        "apply_session_id": self._claims.apply_session_id,
                        "accepted_seq": next_seq,
                        "processed_seq": next_seq,
                        "changed": changed,
                        "queue_depth": queue_depth,
                        "dropped_pending_count": self._state.dropped_pending_count,
                        "overloaded": False,
                        "hair_id": self._active_hair_id(),
                        "dataset_code": self._active_dataset_code(),
                        "asset": selected.to_message(),
                    }
                )

        rendered_bgr = runtime_result.get("output_frame_bgr")
        resize_out_started_at = time.perf_counter()
        if not isinstance(rendered_bgr, np.ndarray):
            total_pipeline_latency_ms = round((time.perf_counter() - frame_started_at) * 1000.0, 3)
            self._state.recent_pipeline_latency_ms = total_pipeline_latency_ms
            self._update_adaptive_resolution(total_pipeline_latency_ms)
            fallback_pts, fallback_time_base = self._next_output_timestamp()
            self._record_output_pts(fallback_pts)
            now_ms = time.monotonic() * 1000.0
            if now_ms - self._state.last_perf_log_at_ms >= PERF_LOG_INTERVAL_MS:
                self._state.last_perf_log_at_ms = now_ms
                logger.info(
                    (
                        "rtc perf: seq=%s total=%.1f resize_in=%.1f tracking=%.1f "
                        "segmentation=%.1f attenuation=%.1f hair_total=%.1f hair_feature=%.1f hair_overlay=%.1f "
                        "hair_parse=%.1f resize_out=%.1f frame_age=%.1f queue_depth=%s process_size=%sx%s original_size=%sx%s "
                        "process_max_dimension=%s attenuation=%s asset=%s renderer=%s selection_mode=%s status=%s profile=%s output=passthrough"
                    ),
                    next_seq,
                    total_pipeline_latency_ms,
                    resize_in_latency_ms,
                    float(prepare_metrics.get("tracking_latency_ms", 0.0)),
                    float(prepare_metrics.get("hair_segmentation_latency_ms", 0.0)),
                    float(prepare_metrics.get("hair_attenuation_latency_ms", 0.0)),
                    runtime_latency_ms,
                    float(runtime_result.get("feature_latency_ms", 0.0) or 0.0),
                    float(runtime_result.get("overlay_latency_ms", 0.0) or 0.0),
                    float(runtime_result.get("user_parsing_latency_ms", 0.0) or 0.0),
                    0.0,
                    frame_age_ms,
                    queue_depth,
                    processing_frame_bgr.shape[1],
                    processing_frame_bgr.shape[0],
                    original_size[0],
                    original_size[1],
                    self._effective_process_max_dimension(),
                    attenuation_status,
                    runtime_result.get("selected_asset_id"),
                    runtime_result.get("renderer_name"),
                    runtime_result.get("selection_mode"),
                    runtime_result.get("status"),
                    "latency" if prefer_latency else "balanced",
                )
                logger.info(
                    (
                        "rtc perf detail: seq=%s frame_age=%.1f queue_depth=%s dropped_total=%s "
                        "control_last=%s control_ms=%.2f control_err=%s control_count=%s "
                        "channel_state=%s buffered_amount=%s send_count=%s last_send=%.3f "
                        "feature_ms=%.1f primary_overlay_ms=%.1f fallback_ms=%.1f overlay_ms=%.1f user_parse_ms=%.1f "
                        "input_pts=%s input_tb=%s input_ms=%s input_dup=%s input_rewind=%s "
                        "output_pts=%s output_tb=%s output_ms=%s output_dup=%s output_rewind=%s"
                    ),
                    next_seq,
                    frame_age_ms,
                    queue_depth,
                    self._state.dropped_pending_count,
                    self._state.last_control_message_type,
                    self._state.last_control_message_latency_ms,
                    self._state.last_control_error_code,
                    self._state.control_message_count,
                    getattr(self._state.data_channel, "readyState", None),
                    getattr(self._state.data_channel, "bufferedAmount", 0) if self._state.data_channel is not None else 0,
                    self._state.data_channel_send_count,
                    self._state.last_channel_send_latency_ms,
                    float(runtime_result.get("feature_latency_ms", 0.0) or 0.0),
                    float(runtime_result.get("primary_overlay_latency_ms", 0.0) or 0.0),
                    float(runtime_result.get("fallback_latency_ms", 0.0) or 0.0),
                    float(runtime_result.get("overlay_latency_ms", 0.0) or 0.0),
                    float(runtime_result.get("user_parsing_latency_ms", 0.0) or 0.0),
                    input_pts,
                    input_time_base_str,
                    input_pts_ms,
                    self._input_pts_duplicate_count,
                    self._input_pts_rewind_count,
                    fallback_pts,
                    self._time_base_to_str(fallback_time_base),
                    self._pts_to_ms(fallback_pts, fallback_time_base),
                    self._output_pts_duplicate_count,
                    self._output_pts_rewind_count,
                )
                attenuation_detail_ms = prepare_metrics.get("hair_attenuation_detail_ms")
                if attenuation_detail_ms:
                    logger.info(
                        "rtc attenuation detail: seq=%s status=%s detail=%s",
                        next_seq,
                        attenuation_status,
                        attenuation_detail_ms,
                    )
            if (
                float(runtime_result.get("overlay_latency_ms", 0.0) or 0.0) >= 80.0
                or str(runtime_result.get("status") or "ok") != "ok"
            ):
                logger.info(
                    "rtc overlay detail: seq=%s asset=%s status=%s selection_mode=%s overlay_detail=%s compose_detail=%s bundle_detail=%s",
                    next_seq,
                    runtime_result.get("selected_asset_id"),
                    runtime_result.get("status"),
                    runtime_result.get("selection_mode"),
                    runtime_result.get("overlay_detail_ms") or {},
                    runtime_result.get("compose_detail_ms") or {},
                    runtime_result.get("bundle_detail_ms") or {},
                )
            self._maybe_emit_stats(
                queue_depth=queue_depth,
                decode_latency_ms=decode_latency_ms,
                tracking_latency_ms=float(prepare_metrics.get("tracking_latency_ms", 0.0)),
                hair_segmentation_latency_ms=float(prepare_metrics.get("hair_segmentation_latency_ms", 0.0)),
                hair_attenuation_latency_ms=float(prepare_metrics.get("hair_attenuation_latency_ms", 0.0)),
                infer_latency_ms=runtime_latency_ms,
                render_latency_ms=float(runtime_result.get("overlay_latency_ms", 0.0) or 0.0),
                encode_latency_ms=0.0,
                user_parsing_latency_ms=float(runtime_result.get("user_parsing_latency_ms", 0.0) or 0.0),
                total_pipeline_latency_ms=total_pipeline_latency_ms,
                selected_asset_id=selected_asset_id or None,
            )
            frame.pts = fallback_pts
            frame.time_base = fallback_time_base
            self._last_output_sent_at_ms = time.monotonic() * 1000.0
            return frame
        target_output_size = self._target_output_size(original_size)
        if rendered_bgr.shape[1] != target_output_size[0] or rendered_bgr.shape[0] != target_output_size[1]:
            rendered_bgr = opencv_resize(
                rendered_bgr,
                (target_output_size[0], target_output_size[1]),
                interpolation=cv2.INTER_LINEAR,
            )
        resize_out_latency_ms = round((time.perf_counter() - resize_out_started_at) * 1000.0, 3)
        if self._mirrored_output():
            rendered_bgr = opencv_flip(rendered_bgr, 1)
        total_pipeline_latency_ms = round((time.perf_counter() - frame_started_at) * 1000.0, 3)
        self._state.recent_pipeline_latency_ms = total_pipeline_latency_ms
        self._update_adaptive_resolution(total_pipeline_latency_ms)
        output_pts, output_time_base = self._next_output_timestamp()
        self._record_output_pts(output_pts)

        now_ms = time.monotonic() * 1000.0
        if now_ms - self._state.last_perf_log_at_ms >= PERF_LOG_INTERVAL_MS:
            self._state.last_perf_log_at_ms = now_ms
            logger.info(
                (
                    "rtc perf: seq=%s total=%.1f resize_in=%.1f tracking=%.1f "
                    "segmentation=%.1f attenuation=%.1f hair_total=%.1f hair_feature=%.1f hair_overlay=%.1f "
                    "hair_parse=%.1f resize_out=%.1f frame_age=%.1f queue_depth=%s process_size=%sx%s original_size=%sx%s "
                    "process_max_dimension=%s attenuation=%s asset=%s renderer=%s selection_mode=%s status=%s profile=%s"
                ),
                next_seq,
                total_pipeline_latency_ms,
                resize_in_latency_ms,
                float(prepare_metrics.get("tracking_latency_ms", 0.0)),
                float(prepare_metrics.get("hair_segmentation_latency_ms", 0.0)),
                float(prepare_metrics.get("hair_attenuation_latency_ms", 0.0)),
                runtime_latency_ms,
                float(runtime_result.get("feature_latency_ms", 0.0) or 0.0),
                float(runtime_result.get("overlay_latency_ms", 0.0) or 0.0),
                float(runtime_result.get("user_parsing_latency_ms", 0.0) or 0.0),
                resize_out_latency_ms,
                frame_age_ms,
                queue_depth,
                processing_frame_bgr.shape[1],
                processing_frame_bgr.shape[0],
                original_size[0],
                original_size[1],
                self._effective_process_max_dimension(),
                attenuation_status,
                runtime_result.get("selected_asset_id"),
                runtime_result.get("renderer_name"),
                runtime_result.get("selection_mode"),
                runtime_result.get("status"),
                "latency" if prefer_latency else "balanced",
            )
            logger.info(
                (
                    "rtc perf detail: seq=%s frame_age=%.1f queue_depth=%s dropped_total=%s "
                    "control_last=%s control_ms=%.2f control_err=%s control_count=%s "
                    "channel_state=%s buffered_amount=%s send_count=%s last_send=%.3f "
                    "feature_ms=%.1f primary_overlay_ms=%.1f fallback_ms=%.1f overlay_ms=%.1f user_parse_ms=%.1f "
                    "input_pts=%s input_tb=%s input_ms=%s input_dup=%s input_rewind=%s "
                    "output_pts=%s output_tb=%s output_ms=%s output_dup=%s output_rewind=%s"
                ),
                next_seq,
                frame_age_ms,
                queue_depth,
                self._state.dropped_pending_count,
                self._state.last_control_message_type,
                self._state.last_control_message_latency_ms,
                self._state.last_control_error_code,
                self._state.control_message_count,
                getattr(self._state.data_channel, "readyState", None),
                getattr(self._state.data_channel, "bufferedAmount", 0) if self._state.data_channel is not None else 0,
                self._state.data_channel_send_count,
                self._state.last_channel_send_latency_ms,
                float(runtime_result.get("feature_latency_ms", 0.0) or 0.0),
                float(runtime_result.get("primary_overlay_latency_ms", 0.0) or 0.0),
                float(runtime_result.get("fallback_latency_ms", 0.0) or 0.0),
                float(runtime_result.get("overlay_latency_ms", 0.0) or 0.0),
                float(runtime_result.get("user_parsing_latency_ms", 0.0) or 0.0),
                input_pts,
                input_time_base_str,
                input_pts_ms,
                self._input_pts_duplicate_count,
                self._input_pts_rewind_count,
                output_pts,
                self._time_base_to_str(output_time_base),
                self._pts_to_ms(output_pts, output_time_base),
                self._output_pts_duplicate_count,
                self._output_pts_rewind_count,
            )
            attenuation_detail_ms = prepare_metrics.get("hair_attenuation_detail_ms")
            if attenuation_detail_ms:
                logger.info(
                    "rtc attenuation detail: seq=%s status=%s detail=%s",
                    next_seq,
                    attenuation_status,
                    attenuation_detail_ms,
                )
            if (
                float(runtime_result.get("overlay_latency_ms", 0.0) or 0.0) >= 80.0
                or str(runtime_result.get("status") or "ok") != "ok"
            ):
                logger.info(
                    "rtc overlay detail: seq=%s asset=%s status=%s selection_mode=%s overlay_detail=%s compose_detail=%s bundle_detail=%s",
                    next_seq,
                    runtime_result.get("selected_asset_id"),
                    runtime_result.get("status"),
                    runtime_result.get("selection_mode"),
                    runtime_result.get("overlay_detail_ms") or {},
                    runtime_result.get("compose_detail_ms") or {},
                    runtime_result.get("bundle_detail_ms") or {},
                )

        self._maybe_emit_stats(
            queue_depth=queue_depth,
            decode_latency_ms=decode_latency_ms,
            tracking_latency_ms=float(prepare_metrics.get("tracking_latency_ms", 0.0)),
            hair_segmentation_latency_ms=float(prepare_metrics.get("hair_segmentation_latency_ms", 0.0)),
            hair_attenuation_latency_ms=float(prepare_metrics.get("hair_attenuation_latency_ms", 0.0)),
            infer_latency_ms=runtime_latency_ms,
            render_latency_ms=float(runtime_result.get("overlay_latency_ms", 0.0) or 0.0),
            encode_latency_ms=0.0,
            user_parsing_latency_ms=float(runtime_result.get("user_parsing_latency_ms", 0.0) or 0.0),
            total_pipeline_latency_ms=total_pipeline_latency_ms,
            selected_asset_id=selected_asset_id or None,
        )

        next_frame = VideoFrame.from_ndarray(rendered_bgr, format="bgr24")
        next_frame.pts = output_pts
        next_frame.time_base = output_time_base
        self._last_output_sent_at_ms = time.monotonic() * 1000.0
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


def _sdp_video_codec_summary(description: Any) -> list[str]:
    sdp = getattr(description, "sdp", None)
    if not isinstance(sdp, str) or not sdp:
        return []

    lines = [line.strip() for line in sdp.splitlines() if line.strip()]
    video_payload_types: list[str] = []
    rtpmap_by_pt: dict[str, str] = {}
    fmtp_by_pt: dict[str, str] = {}

    in_video_section = False
    for line in lines:
        if line.startswith("m="):
            in_video_section = line.startswith("m=video ")
            if in_video_section:
                parts = line.split()
                if len(parts) >= 4:
                    video_payload_types = parts[3:]
            continue
        if not in_video_section:
            continue
        if line.startswith("a=rtpmap:"):
            payload = line[len("a=rtpmap:") :]
            pt, _, codec = payload.partition(" ")
            if pt and codec:
                rtpmap_by_pt[pt] = codec
        elif line.startswith("a=fmtp:"):
            payload = line[len("a=fmtp:") :]
            pt, _, fmtp = payload.partition(" ")
            if pt and fmtp:
                fmtp_by_pt[pt] = fmtp

    summary: list[str] = []
    for pt in video_payload_types:
        codec = rtpmap_by_pt.get(pt)
        if codec is None:
            summary.append(f"pt={pt}")
            continue
        entry = f"{codec}(pt={pt}"
        fmtp = fmtp_by_pt.get(pt)
        if fmtp:
            entry += f",fmtp={fmtp}"
        entry += ")"
        summary.append(entry)
    return summary


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
        session_state = RtcSessionState(
            active_hair_id=claims.hair_id,
            active_dataset_code=claims.dataset_code,
            active_representative_asset_id=claims.representative_asset_id,
            mirrored=settings.rtc_mirrored_input,
        )

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
            channel_label = str(getattr(channel, "label", "") or "")
            logger.info("rtc data channel opened: label=%s", channel_label)
            if channel_label != settings.rtc_control_channel_name:
                logger.warning(
                    "rtc unexpected data channel label: expected=%s actual=%s",
                    settings.rtc_control_channel_name,
                    channel_label,
                )
                try:
                    _send_channel_json(
                        channel,
                        session_state,
                        _control_error_payload(
                            "UNEXPECTED_CHANNEL_LABEL",
                            (
                                f"expected control channel label "
                                f"{settings.rtc_control_channel_name}, got {channel_label}"
                            ),
                        )
                    )
                except Exception:  # pragma: no cover - browser interoperability
                    logger.warning("rtc failed to report unexpected data channel label")
                return

            session_state.data_channel = channel

            @channel.on("message")
            def _on_message(message: str | bytes) -> None:
                control_started_at = time.perf_counter()
                server_received_ts_ms = _now_ms()
                message_type, client_ts_ms = _extract_control_message_debug(message)
                message_bytes = _raw_message_size_bytes(message)
                session_state.control_message_count += 1
                session_state.control_message_total_bytes += message_bytes
                session_state.last_control_message_type = message_type
                session_state.last_control_message_bytes = message_bytes
                session_state.last_control_message_client_ts_ms = client_ts_ms
                session_state.last_control_message_server_ts_ms = server_received_ts_ms
                try:
                    payloads = _process_control_message(
                        message,
                        state=session_state,
                        settings=settings,
                        claims=claims,
                        catalog=app.state.catalog,
                        hair_runtime_manager=app.state.hair_runtime_manager,
                    )
                    processing_ms = round((time.perf_counter() - control_started_at) * 1000.0, 3)
                    session_state.last_control_message_latency_ms = processing_ms
                    session_state.last_control_error_code = None
                    session_state.last_control_response_count = len(payloads)
                    logger.info(
                        "rtc control message handled: type=%s latency_ms=%.2f bytes=%s responses=%s buffered_amount=%s",
                        message_type,
                        processing_ms,
                        message_bytes,
                        len(payloads),
                        getattr(channel, "bufferedAmount", 0),
                    )
                    for index, response_payload in enumerate(payloads, start=1):
                        _send_channel_json(
                            channel,
                            session_state,
                            _augment_control_payload(
                                response_payload,
                                message_type=message_type,
                                message_bytes=message_bytes,
                                server_received_ts_ms=server_received_ts_ms,
                                processing_ms=processing_ms,
                                response_index=index,
                                response_count=len(payloads),
                                channel=channel,
                                client_ts_ms=client_ts_ms,
                            ),
                        )
                except ControlMessageError as exc:
                    processing_ms = round((time.perf_counter() - control_started_at) * 1000.0, 3)
                    session_state.control_error_count += 1
                    session_state.last_control_message_latency_ms = processing_ms
                    session_state.last_control_error_code = exc.code
                    session_state.last_control_response_count = 1
                    logger.warning(
                        "rtc control message rejected: code=%s message=%s type=%s latency_ms=%.2f bytes=%s",
                        exc.code,
                        exc.message,
                        message_type,
                        processing_ms,
                        message_bytes,
                    )
                    _send_channel_json(
                        channel,
                        session_state,
                        _augment_control_payload(
                            _control_error_payload(exc.code, exc.message),
                            message_type=message_type,
                            message_bytes=message_bytes,
                            server_received_ts_ms=server_received_ts_ms,
                            processing_ms=processing_ms,
                            response_index=1,
                            response_count=1,
                            channel=channel,
                            client_ts_ms=client_ts_ms,
                        ),
                    )
                except Exception as exc:  # pragma: no cover - browser interoperability
                    processing_ms = round((time.perf_counter() - control_started_at) * 1000.0, 3)
                    session_state.control_error_count += 1
                    session_state.last_control_message_latency_ms = processing_ms
                    session_state.last_control_error_code = "CONTROL_MESSAGE_ERROR"
                    session_state.last_control_response_count = 1
                    logger.warning(
                        "rtc control message processing failed: type=%s latency_ms=%.2f bytes=%s error=%s",
                        message_type,
                        processing_ms,
                        message_bytes,
                        exc,
                    )
                    _send_channel_json(
                        channel,
                        session_state,
                        _augment_control_payload(
                            _control_error_payload(
                                "CONTROL_MESSAGE_ERROR",
                                str(exc),
                            ),
                            message_type=message_type,
                            message_bytes=message_bytes,
                            server_received_ts_ms=server_received_ts_ms,
                            processing_ms=processing_ms,
                            response_index=1,
                            response_count=1,
                            channel=channel,
                            client_ts_ms=client_ts_ms,
                        )
                    )

            _send_channel_json(
                channel,
                session_state,
                {
                    "type": "connected",
                    "apply_session_id": claims.apply_session_id,
                    "node_id": settings.node_id,
                    "control_channel": settings.rtc_control_channel_name,
                    "feature_schema_version": settings.feature_schema_version,
                    "transform_version": settings.transform_version,
                    "hello_required": settings.rtc_require_hello,
                    "hair_id": session_state.active_hair_id,
                    "dataset_code": session_state.active_dataset_code,
                    "representative_asset_id": session_state.active_representative_asset_id,
                    "mirrored": session_state.mirrored,
                    "expected_input_width": settings.rtc_input_width,
                    "expected_input_height": settings.rtc_input_height,
                    "expected_input_fps": settings.rtc_input_fps,
                    "expected_output_width": settings.rtc_output_width,
                    "expected_output_height": settings.rtc_output_height,
                    "expected_output_fps": settings.rtc_output_fps,
                    "expected_output_mirrored": settings.rtc_output_mirrored,
                    "server_ts_ms": _now_ms(),
                },
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
                    hair_segmenter=getattr(app.state, "hair_segmenter", None),
                    hair_attenuator=getattr(app.state, "hair_attenuator", None),
                )
            )

        await peer_connection.setRemoteDescription(
            RTCSessionDescription(sdp=payload.sdp, type=payload.type)
        )
        logger.info(
            "rtc remote candidates: %s",
            _sdp_candidate_lines(peer_connection.remoteDescription),
        )
        logger.info(
            "rtc remote video codecs: %s",
            _sdp_video_codec_summary(peer_connection.remoteDescription),
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
        logger.info(
            "rtc local video codecs: %s",
            _sdp_video_codec_summary(local_description),
        )

        return {
            "sdp": local_description.sdp,
            "type": local_description.type,
        }
