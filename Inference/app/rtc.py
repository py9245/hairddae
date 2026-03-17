from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import logging
import time
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.auth import TicketValidationError, validate_connect_ticket
from app.catalog import AssetBundle, AssetCatalog
from app.config import Settings
from app.models import FeatureMessageModel
from app.server_render import compose_bundle_frame

try:
    from aiortc import (
        RTCConfiguration,
        RTCIceServer,
        RTCPeerConnection,
        RTCSessionDescription,
        VideoStreamTrack,
    )
    from av import VideoFrame
except ImportError:  # pragma: no cover - runtime guarded
    RTCConfiguration = None
    RTCIceServer = None
    RTCPeerConnection = None
    RTCSessionDescription = None
    VideoStreamTrack = object
    VideoFrame = None


logger = logging.getLogger("uvicorn.error")


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


class RtcRenderTrack(VideoStreamTrack):  # type: ignore[misc]
    kind = "video"

    def __init__(self, source_track: Any, state: RtcSessionState) -> None:
        super().__init__()
        self._source_track = source_track
        self._state = state

    async def recv(self) -> Any:
        frame = await self._source_track.recv()
        image = frame.to_image()
        rendered = compose_bundle_frame(image, self._state.last_selected_bundle)
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


def _create_peer_connection(settings: Settings) -> Any:
    if RTCPeerConnection is None:
        return None
    if RTCConfiguration is None or RTCIceServer is None or not settings.rtc_ice_servers:
        return RTCPeerConnection()

    ice_servers = []
    for payload in settings.rtc_ice_servers:
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

        @peer_connection.on("datachannel")
        def _on_datachannel(channel: Any) -> None:
            logger.info("rtc data channel opened: label=%s", getattr(channel, "label", "unknown"))
            @channel.on("message")
            def _on_message(message: str | bytes) -> None:
                raw_message = message.decode("utf-8") if isinstance(message, bytes) else message
                try:
                    parsed_message = json.loads(raw_message)
                    feature = FeatureMessageModel.model_validate(parsed_message)
                    if feature.feature_schema_version != settings.feature_schema_version:
                        raise ValueError("feature schema version mismatch")
                    if feature.transform_version != settings.transform_version:
                        raise ValueError("transform version mismatch")
                    if feature.apply_session_id != claims.apply_session_id:
                        raise ValueError("apply_session_id mismatch")
                    if feature.hair_id != claims.hair_id:
                        raise ValueError("hair_id mismatch")

                    candidate = app.state.catalog.recommend(
                        dataset_code=claims.dataset_code,
                        feature=feature,
                        representative_asset_id=claims.representative_asset_id,
                    )
                    changed, selected = _maybe_switch_asset(
                        session_state,
                        candidate,
                        settings,
                        app.state.catalog,
                        claims.dataset_code,
                        feature,
                    )
                    session_state.latest_feature = feature
                    session_state.last_processed_seq = feature.seq
                    logger.info(
                        "rtc feature processed: seq=%s changed=%s asset=%s",
                        feature.seq,
                        changed,
                        selected.asset_id,
                    )
                    channel.send(
                        json.dumps(
                            {
                                "type": "processed",
                                "apply_session_id": claims.apply_session_id,
                                "accepted_seq": feature.seq,
                                "processed_seq": feature.seq,
                                "changed": changed,
                                "queue_depth": 0,
                                "dropped_pending_count": session_state.dropped_pending_count,
                                "overloaded": False,
                                "asset": selected.to_message(),
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
            peer_connection.addTrack(RtcRenderTrack(track, session_state))

        await peer_connection.setRemoteDescription(
            RTCSessionDescription(sdp=payload.sdp, type=payload.type)
        )
        answer = await peer_connection.createAnswer()
        await peer_connection.setLocalDescription(answer)
        await _wait_for_ice_gathering_complete(peer_connection)

        local_description = peer_connection.localDescription
        if local_description is None:
            raise HTTPException(status_code=500, detail="failed to create RTC answer")

        return {
            "sdp": local_description.sdp,
            "type": local_description.type,
        }
