from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
from pathlib import Path
import time
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
import numpy as np
from PIL import Image, UnidentifiedImageError

from app.auth import TicketClaims
from app.bald import BaldPreprocessor
from app.catalog import AssetBundle, AssetCatalog
from app.config import Settings
from app.face_tracking import ServerFaceTracker
from app.server_render import compose_bundle_frame_rgb


@dataclass(frozen=True)
class HttpFrameResult:
    response_bytes: bytes
    media_type: str
    status: str
    selected_bundle: AssetBundle | None
    feature: object | None
    processed_seq: int
    total_latency_ms: float
    tracking_latency_ms: float
    selection_latency_ms: float
    render_latency_ms: float
    dataset_code: str


def _now_ms() -> int:
    return int(time.time() * 1000)


def _load_dataset_summary(static_root: Path, dataset_code: str) -> dict[str, object]:
    asset_index_path = static_root / dataset_code / "manifests" / "asset_index_v0.json"
    if not asset_index_path.is_file():
        return {
            "dataset_code": dataset_code,
            "asset_index_exists": False,
            "asset_index_path": str(asset_index_path),
            "asset_count": 0,
            "approved_asset_count": 0,
        }

    payload = json.loads(asset_index_path.read_text())
    items = payload.get("items", [])
    approved_count = sum(1 for item in items if isinstance(item, dict) and item.get("approved"))
    return {
        "dataset_code": dataset_code,
        "asset_index_exists": True,
        "asset_index_path": str(asset_index_path),
        "asset_count": len(items),
        "approved_asset_count": approved_count,
    }


def _decode_image(payload: bytes) -> Image.Image:
    if not payload:
        raise ValueError("empty image payload")

    try:
        decoded = Image.open(BytesIO(payload))
    except UnidentifiedImageError as exc:
        raise ValueError("unsupported image payload") from exc
    return decoded.convert("RGB")


def _encode_image(image: Image.Image, response_format: Literal["jpeg", "png"], jpeg_quality: int) -> bytes:
    buffer = BytesIO()
    if response_format == "png":
        image.save(buffer, format="PNG", optimize=False)
        return buffer.getvalue()

    image.save(buffer, format="JPEG", quality=jpeg_quality, optimize=False)
    return buffer.getvalue()


def _build_http_claims(
    *,
    settings: Settings,
    dataset_code: str,
    hair_id: int,
    apply_session_id: str,
    representative_asset_id: str | None,
) -> TicketClaims:
    now = datetime.now(tz=timezone.utc)
    return TicketClaims(
        user_id="http-test-user",
        apply_session_id=apply_session_id,
        device_id="http-test-device",
        hair_id=hair_id,
        node_id=settings.node_id,
        schema_version=settings.feature_schema_version,
        dataset_code=dataset_code,
        representative_asset_id=representative_asset_id,
        token_id="http-test",
        expires_at=now + timedelta(hours=1),
    )


def _process_http_frame(
    *,
    payload: bytes,
    dataset_code: str,
    hair_id: int,
    apply_session_id: str,
    representative_asset_id: str | None,
    response_format: Literal["jpeg", "png"],
    settings: Settings,
    face_tracker: ServerFaceTracker,
    catalog: AssetCatalog,
    bald_processor: BaldPreprocessor | None,
) -> HttpFrameResult:
    total_started_at = time.perf_counter()
    image = _decode_image(payload)
    frame_rgb = np.asarray(image)
    claims = _build_http_claims(
        settings=settings,
        dataset_code=dataset_code,
        hair_id=hair_id,
        apply_session_id=apply_session_id,
        representative_asset_id=representative_asset_id,
    )

    tracking_started_at = time.perf_counter()
    tracking_result = face_tracker.extract_tracking_result_from_rgb(
        frame_rgb,
        claims=claims,
        settings=settings,
        seq=1,
        ts_ms=_now_ms(),
    )
    tracking_latency_ms = round((time.perf_counter() - tracking_started_at) * 1000.0, 3)

    selected_bundle: AssetBundle | None = None
    selection_latency_ms = 0.0
    render_started_at = time.perf_counter()
    status = "no_face"
    rendered_rgb = frame_rgb
    processed_seq = 0
    feature = None

    if tracking_result is not None:
        feature = tracking_result.feature
        processed_seq = feature.seq
        selection_started_at = time.perf_counter()
        selected_bundle = catalog.bundle_for_recommended_asset(
            dataset_code=dataset_code,
            selection_feature=feature,
            render_feature=feature,
            representative_asset_id=representative_asset_id,
        )
        selection_latency_ms = round((time.perf_counter() - selection_started_at) * 1000.0, 3)
        render_input_rgb = frame_rgb
        if bald_processor is not None:
            render_input_rgb = bald_processor.apply(frame_rgb, tracking_result.landmarks_px)
        rendered_rgb = compose_bundle_frame_rgb(
            render_input_rgb,
            selected_bundle,
            reference_width=feature.image_size.width,
            reference_height=feature.image_size.height,
            acceleration_preference=settings.render_acceleration,
        )
        status = "ok"

    render_latency_ms = round((time.perf_counter() - render_started_at) * 1000.0, 3)
    response_bytes = _encode_image(
        Image.fromarray(rendered_rgb),
        response_format,
        settings.http_test_jpeg_quality,
    )
    total_latency_ms = round((time.perf_counter() - total_started_at) * 1000.0, 3)
    return HttpFrameResult(
        response_bytes=response_bytes,
        media_type="image/png" if response_format == "png" else "image/jpeg",
        status=status,
        selected_bundle=selected_bundle,
        feature=feature,
        processed_seq=processed_seq,
        total_latency_ms=total_latency_ms,
        tracking_latency_ms=tracking_latency_ms,
        selection_latency_ms=selection_latency_ms,
        render_latency_ms=render_latency_ms,
        dataset_code=dataset_code,
    )


def _headers_from_result(result: HttpFrameResult, settings: Settings) -> dict[str, str]:
    headers = {
        "X-Inference-Status": result.status,
        "X-Processed-Seq": str(result.processed_seq),
        "X-Node-Id": settings.node_id,
        "X-Dataset-Code": result.dataset_code,
        "X-Feature-Schema-Version": str(settings.feature_schema_version),
        "X-Transform-Version": settings.transform_version,
        "X-Total-Latency-Ms": str(result.total_latency_ms),
        "X-Tracking-Latency-Ms": str(result.tracking_latency_ms),
        "X-Selection-Latency-Ms": str(result.selection_latency_ms),
        "X-Render-Latency-Ms": str(result.render_latency_ms),
        "X-Selected-Asset-Id": "",
        "X-Selected-Pose-Key": "",
        "X-Retrieval-Score": "",
        "Cache-Control": "no-store",
    }
    if result.selected_bundle is not None:
        headers["X-Selected-Asset-Id"] = result.selected_bundle.asset_id
        headers["X-Selected-Pose-Key"] = result.selected_bundle.pose_key
        headers["X-Retrieval-Score"] = str(result.selected_bundle.score)
    if result.feature is not None:
        headers["X-User-Yaw-1deg"] = str(result.feature.pose.yaw_1deg)
        headers["X-User-Pitch-1deg"] = str(result.feature.pose.pitch_1deg)
        headers["X-User-Roll-1deg"] = str(result.feature.pose.roll_1deg)
    return headers


def attach_http_runtime_routes(app: FastAPI) -> None:
    @app.get("/api/runtime/health")
    async def runtime_health(dataset_code: str | None = None) -> JSONResponse:
        settings: Settings = app.state.settings
        resolved_dataset_code = dataset_code or settings.http_test_default_dataset_code
        summary = _load_dataset_summary(settings.static_root, resolved_dataset_code)
        return JSONResponse(
            {
                "ready": True,
                "http_test_enabled": settings.http_test_enabled,
                "node_id": settings.node_id,
                "acceleration": app.state.acceleration.to_dict(),
                "rtc_h264_acceleration": app.state.rtc_h264_acceleration,
                "static_root": str(settings.static_root),
                "face_landmarker_model_path": str(settings.face_landmarker_model_path),
                "face_landmarker_model_exists": settings.face_landmarker_model_path.is_file(),
                "mediapipe_delegate": settings.mediapipe_delegate,
                "http_face_tracker_delegate": app.state.face_tracker.acceleration,
                "http_bald_processor_delegate": app.state.bald_processor.acceleration,
                "http_bald_processor_warning": getattr(app.state.bald_processor, "initialization_warning", None),
                "render_acceleration": settings.render_acceleration,
                "http_face_landmarker_running_mode": settings.http_face_landmarker_running_mode,
                "http_hair_segmenter_running_mode": settings.http_hair_segmenter_running_mode,
                "rtc_face_landmarker_running_mode": settings.rtc_face_landmarker_running_mode,
                "rtc_hair_segmenter_running_mode": settings.rtc_hair_segmenter_running_mode,
                "rtc_session_local_processors": settings.rtc_session_local_processors,
                "default_dataset_code": settings.http_test_default_dataset_code,
                "dataset": summary,
            }
        )

    @app.post("/api/runtime/frame")
    @app.post("/v2/api/runtime/frame")
    async def runtime_frame(
        request: Request,
        dataset_code: str | None = None,
        hair_id: int = 1,
        apply_session_id: str = "http-test-session",
        representative_asset_id: str | None = None,
        response_format: Literal["jpeg", "png"] = "jpeg",
    ) -> Response:
        settings: Settings = app.state.settings
        if not settings.http_test_enabled:
            raise HTTPException(status_code=404, detail="HTTP runtime test endpoint is disabled")

        payload = await request.body()
        try:
            result = await asyncio.to_thread(
                _process_http_frame,
                payload=payload,
                dataset_code=dataset_code or settings.http_test_default_dataset_code,
                hair_id=hair_id,
                apply_session_id=apply_session_id,
                representative_asset_id=representative_asset_id,
                response_format=response_format,
                settings=settings,
                face_tracker=app.state.face_tracker,
                catalog=app.state.catalog,
                bald_processor=getattr(app.state, "bald_processor", None),
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return Response(
            content=result.response_bytes,
            media_type=result.media_type,
            headers=_headers_from_result(result, settings),
        )
