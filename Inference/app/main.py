from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
import time
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.auth import ReplayStore, TicketClaims, TicketValidationError, build_replay_store, validate_connect_ticket
from app.bald import BaldPreprocessor
from app.catalog import AssetBundle, AssetCatalog
from app.config import Settings
from app.face_tracking import ServerFaceTracker
from app.http_runtime import attach_http_runtime_routes
from app.models import FeatureMessageModel, HeartbeatMessageModel
from app.rtc import attach_rtc_routes


def _now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class SessionState:
    processing_slot: FeatureMessageModel | None = None
    pending_slot: FeatureMessageModel | None = None
    last_processed_seq: int = 0
    dropped_pending_count: int = 0
    last_activity_ms: int = 0
    last_selected_bundle: AssetBundle | None = None
    last_switch_at_ms: int = 0


async def _send_json(websocket: WebSocket, payload: dict[str, Any]) -> None:
    await websocket.send_json(payload)


async def _reader_loop(
    websocket: WebSocket,
    claims: TicketClaims,
    settings: Settings,
    state: SessionState,
    ready_event: asyncio.Event,
    shutdown_event: asyncio.Event,
) -> None:
    while not shutdown_event.is_set():
        message = await websocket.receive_json()
        message_type = message.get("type")
        state.last_activity_ms = _now_ms()

        if message_type == "heartbeat":
            heartbeat = HeartbeatMessageModel.model_validate(message)
            if heartbeat.apply_session_id != claims.apply_session_id:
                raise ValueError("apply_session_id mismatch")
            await _send_json(
                websocket,
                {
                    "type": "heartbeat_ack",
                    "apply_session_id": claims.apply_session_id,
                    "ts_ms": _now_ms(),
                },
            )
            continue

        if message_type != "feature":
            await _send_json(
                websocket,
                {
                    "type": "error",
                    "code": 400,
                    "message": "unsupported message type",
                },
            )
            continue

        feature = FeatureMessageModel.model_validate(message)
        if feature.feature_schema_version != settings.feature_schema_version:
            raise ValueError("feature schema version mismatch")
        if feature.transform_version != settings.transform_version:
            raise ValueError("transform version mismatch")
        if feature.apply_session_id != claims.apply_session_id:
            raise ValueError("apply_session_id mismatch")
        if feature.hair_id != claims.hair_id:
            raise ValueError("hair_id mismatch")

        if state.processing_slot is None:
            state.processing_slot = feature
            ready_event.set()
            continue

        if state.pending_slot is not None:
            state.dropped_pending_count += 1
        state.pending_slot = feature


def _maybe_switch_asset(
    state: SessionState,
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


async def _processor_loop(
    websocket: WebSocket,
    claims: TicketClaims,
    settings: Settings,
    catalog: AssetCatalog,
    state: SessionState,
    ready_event: asyncio.Event,
    shutdown_event: asyncio.Event,
) -> None:
    while not shutdown_event.is_set():
        await ready_event.wait()
        feature = state.processing_slot
        if feature is None:
            ready_event.clear()
            continue

        candidate = catalog.recommend(
            dataset_code=claims.dataset_code,
            feature=feature,
            representative_asset_id=claims.representative_asset_id,
        )
        changed, selected = _maybe_switch_asset(
            state,
            candidate,
            settings,
            catalog,
            claims.dataset_code,
            feature,
        )
        queue_depth = 1 if state.pending_slot is not None else 0
        payload: dict[str, Any] = {
            "type": "processed",
            "apply_session_id": claims.apply_session_id,
            "accepted_seq": feature.seq,
            "processed_seq": feature.seq,
            "changed": changed,
            "queue_depth": queue_depth,
            "dropped_pending_count": state.dropped_pending_count,
            "overloaded": False,
            "asset": selected.to_message(),
        }

        await _send_json(websocket, payload)

        state.last_processed_seq = feature.seq
        state.processing_slot = state.pending_slot
        state.pending_slot = None
        if state.processing_slot is None:
            ready_event.clear()
        else:
            ready_event.set()


async def _idle_watchdog(
    websocket: WebSocket,
    settings: Settings,
    state: SessionState,
    shutdown_event: asyncio.Event,
) -> None:
    while not shutdown_event.is_set():
        await asyncio.sleep(1)
        if state.last_activity_ms == 0:
            continue
        if _now_ms() - state.last_activity_ms < settings.idle_ttl_ms:
            continue
        await websocket.close(code=1001, reason="idle session expired")
        shutdown_event.set()
        return


def create_app() -> FastAPI:
    settings = Settings.from_env()
    replay_store = build_replay_store(settings)
    catalog = AssetCatalog(settings)
    face_tracker = ServerFaceTracker(settings.face_landmarker_model_path)
    bald_processor = (
        BaldPreprocessor(settings.hair_segmenter_model_path)
        if settings.bald_preprocess_enabled
        else None
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            yield
        finally:
            for peer_connection in list(getattr(app.state, "rtc_peer_connections", set())):
                await peer_connection.close()
            if bald_processor is not None:
                bald_processor.close()
            face_tracker.close()
            await replay_store.close()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.state.settings = settings
    app.state.replay_store = replay_store
    app.state.catalog = catalog
    app.state.face_tracker = face_tracker
    app.state.bald_processor = bald_processor
    attach_rtc_routes(app)
    attach_http_runtime_routes(app)

    @app.get("/healthz")
    async def healthz() -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "service": settings.app_name,
                "node_id": settings.node_id,
            }
        )

    @app.websocket("/apply")
    @app.websocket("/v2/apply")
    async def apply(websocket: WebSocket) -> None:
        subprotocols = list(websocket.scope.get("subprotocols", []))
        ticket_protocol = next((value for value in subprotocols if value.startswith("ticket.")), None)
        if settings.ws_protocol not in subprotocols or ticket_protocol is None:
            await websocket.close(code=4401, reason="missing ticket protocol")
            return

        ticket = ticket_protocol.removeprefix("ticket.")
        try:
            claims = await validate_connect_ticket(ticket, settings, app.state.replay_store)
        except TicketValidationError as exc:
            await websocket.close(code=4401, reason=str(exc))
            return

        await websocket.accept(subprotocol=settings.ws_protocol)
        state = SessionState(last_activity_ms=_now_ms())
        await _send_json(
            websocket,
            {
                "type": "connected",
                "apply_session_id": claims.apply_session_id,
                "node_id": claims.node_id,
                "feature_schema_version": settings.feature_schema_version,
                "transform_version": settings.transform_version,
            },
        )

        ready_event = asyncio.Event()
        shutdown_event = asyncio.Event()
        reader = asyncio.create_task(_reader_loop(websocket, claims, settings, state, ready_event, shutdown_event))
        processor = asyncio.create_task(_processor_loop(websocket, claims, settings, app.state.catalog, state, ready_event, shutdown_event))
        watchdog = asyncio.create_task(_idle_watchdog(websocket, settings, state, shutdown_event))

        tasks = {reader, processor, watchdog}
        try:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
            for task in done:
                exc = task.exception()
                if exc is None:
                    continue
                if isinstance(exc, WebSocketDisconnect):
                    break
                if isinstance(exc, (ValidationError, ValueError)):
                    await _send_json(
                        websocket,
                        {
                            "type": "error",
                            "code": 400,
                            "message": str(exc),
                        },
                    )
                    break
                raise exc
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
        except WebSocketDisconnect:
            pass
        finally:
            shutdown_event.set()
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    return app
