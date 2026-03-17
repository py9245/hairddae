from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
import json
import logging
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
SERVER_RENDER_READY_MIN_PROCESSED = 1
SERVER_RENDER_READY_MIN_STABLE_ASSET = 1
PROCESSED_BUNDLE_HISTORY_SIZE = 48
FRAME_BUNDLE_MAX_LAG_MS = 280.0
FRAME_BUNDLE_MAX_LEAD_MS = 180.0
RENDER_MATCH_LOG_INTERVAL_MS = 1000.0


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
        face_tracker: ServerFaceTracker,
        bald_processor: BaldPreprocessor | None,
    ) -> None:
        super().__init__()
        self._source_track = source_track
        self._state = state
        self._claims = claims
        self._settings = settings
        self._catalog = catalog
        self._face_tracker = face_tracker
        self._bald_processor = bald_processor

    def _emit_channel_payload(self, payload: dict[str, object]) -> None:
        channel = self._state.data_channel
        if channel is None or getattr(channel, "readyState", None) != "open":
            return
        channel.send(json.dumps(payload))

    async def recv(self) -> Any:
        frame = await self._source_track.recv()
        image = frame.to_image()
        frame_rgb = np.asarray(image.convert("RGB"))

        next_seq = self._state.server_processed_seq + 1
        tracking_result = await asyncio.to_thread(
            self._face_tracker.extract_tracking_result_from_rgb,
            frame_rgb,
            claims=self._claims,
            settings=self._settings,
            seq=next_seq,
            ts_ms=_now_ms(),
        )
        if tracking_result is None:
            return frame
        feature = tracking_result.feature

        self._state.server_processed_seq = next_seq
        selection_feature = _build_selection_feature(self._state, feature)
        candidate = self._catalog.recommend(
            dataset_code=self._claims.dataset_code,
            feature=selection_feature,
            representative_asset_id=self._claims.representative_asset_id,
        )
        candidate = self._catalog.bundle_for_asset(
            dataset_code=self._claims.dataset_code,
            asset_id=candidate.asset_id,
            feature=feature,
        )
        changed, selected = _maybe_switch_asset(
            self._state,
            candidate,
            self._settings,
            self._catalog,
            self._claims.dataset_code,
            feature,
        )
        self._state.latest_feature = feature
        self._state.last_processed_seq = feature.seq
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

        logger.info(
            (
                "rtc server feature: seq=%s changed=%s asset=%s "
                "raw_pose=(%s,%s,%s) smooth_pose=(%s,%s,%s)"
            ),
            feature.seq,
            changed,
            selected.asset_id,
            feature.pose.yaw_1deg,
            feature.pose.pitch_1deg,
            feature.pose.roll_1deg,
            selection_feature.pose.yaw_1deg,
            selection_feature.pose.pitch_1deg,
            selection_feature.pose.roll_1deg,
        )
        self._emit_channel_payload(
            {
                "type": "processed",
                "apply_session_id": self._claims.apply_session_id,
                "accepted_seq": feature.seq,
                "processed_seq": feature.seq,
                "changed": changed,
                "queue_depth": 0,
                "dropped_pending_count": 0,
                "overloaded": False,
                "asset": selected.to_message(),
            }
        )

        render_input = image
        if self._bald_processor is not None:
            render_input = Image.fromarray(
                self._bald_processor.apply(frame_rgb, tracking_result.landmarks_px),
                mode="RGB",
            )
        rendered = compose_bundle_frame(
            render_input,
            selected,
            reference_width=feature.image_size.width,
            reference_height=feature.image_size.height,
        )
        next_frame = VideoFrame.from_image(rendered.convert("RGB"))
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
