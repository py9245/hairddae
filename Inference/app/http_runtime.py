from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
from io import BytesIO
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
import numpy as np
from PIL import Image, UnidentifiedImageError

from app.catalog import _resolve_asset_index_path
from app.config import Settings
from app.hairddae_runtime_manager import HairddaeRuntimeManager


@dataclass(frozen=True)
class HttpFrameResult:
    response_bytes: bytes
    media_type: str
    status: str
    selected_asset_id: str | None
    selected_pose_key: str | None
    retrieval_score: float | None
    yaw_1deg: int | None
    pitch_1deg: int | None
    roll_1deg: int | None
    processed_seq: int
    total_latency_ms: float
    tracking_latency_ms: float
    selection_latency_ms: float
    render_latency_ms: float
    dataset_code: str


def _load_dataset_summary(static_root: Path, dataset_code: str) -> dict[str, object]:
    asset_root_path = static_root / dataset_code
    asset_index_path = _resolve_asset_index_path(asset_root_path)
    if asset_index_path is None:
        return {
            "dataset_code": dataset_code,
            "asset_index_exists": False,
            "asset_index_path": str(asset_root_path / "manifests" / "asset_index_v0.json"),
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


def _extract_pose_angle(user_row: dict[str, object] | None, key: str) -> int | None:
    if user_row is None:
        return None
    value = user_row.get(key)
    if not isinstance(value, (int, float)):
        return None
    return int(round(float(value)))


def _process_http_frame(
    *,
    payload: bytes,
    dataset_code: str,
    apply_session_id: str,
    response_format: Literal["jpeg", "png"],
    settings: Settings,
    hair_runtime_manager: HairddaeRuntimeManager,
) -> HttpFrameResult:
    image = _decode_image(payload)
    frame_rgb = np.asarray(image)
    frame_bgr = np.ascontiguousarray(frame_rgb[:, :, ::-1])
    runtime_result = hair_runtime_manager.process_frame(
        dataset_code=dataset_code,
        frame_bgr=frame_bgr,
        session_id=apply_session_id,
        encode_output=False,
    )

    output_frame_bgr = runtime_result.get("output_frame_bgr")
    if not isinstance(output_frame_bgr, np.ndarray):
        output_frame_bgr = frame_bgr

    rendered = Image.fromarray(output_frame_bgr[:, :, ::-1], mode="RGB")
    response_bytes = _encode_image(rendered, response_format, settings.http_test_jpeg_quality)
    user_row = runtime_result.get("user_row") if isinstance(runtime_result.get("user_row"), dict) else None

    return HttpFrameResult(
        response_bytes=response_bytes,
        media_type="image/png" if response_format == "png" else "image/jpeg",
        status=str(runtime_result.get("status", "error")),
        selected_asset_id=(
            None
            if runtime_result.get("selected_asset_id") in (None, "")
            else str(runtime_result["selected_asset_id"])
        ),
        selected_pose_key=(
            None
            if runtime_result.get("selected_pose_key") in (None, "")
            else str(runtime_result["selected_pose_key"])
        ),
        retrieval_score=(
            None
            if runtime_result.get("score") is None
            else float(runtime_result["score"])
        ),
        yaw_1deg=_extract_pose_angle(user_row, "face_yaw_deg"),
        pitch_1deg=_extract_pose_angle(user_row, "face_pitch_deg"),
        roll_1deg=_extract_pose_angle(user_row, "face_roll_deg"),
        processed_seq=1,
        total_latency_ms=round(float(runtime_result.get("latency_ms", 0.0)), 3),
        tracking_latency_ms=round(float(runtime_result.get("feature_latency_ms", 0.0)), 3),
        selection_latency_ms=0.0,
        render_latency_ms=round(float(runtime_result.get("overlay_latency_ms", 0.0)), 3),
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
        "X-Selected-Asset-Id": result.selected_asset_id or "",
        "X-Selected-Pose-Key": result.selected_pose_key or "",
        "X-Retrieval-Score": "" if result.retrieval_score is None else str(result.retrieval_score),
        "Cache-Control": "no-store",
    }
    if result.yaw_1deg is not None:
        headers["X-User-Yaw-1deg"] = str(result.yaw_1deg)
    if result.pitch_1deg is not None:
        headers["X-User-Pitch-1deg"] = str(result.pitch_1deg)
    if result.roll_1deg is not None:
        headers["X-User-Roll-1deg"] = str(result.roll_1deg)
    return headers


def attach_http_runtime_routes(app: FastAPI) -> None:
    async def runtime_frame_response(
        request: Request,
        *,
        dataset_code: str | None,
        apply_session_id: str,
        response_format: Literal["jpeg", "png"],
    ) -> Response:
        settings: Settings = app.state.settings
        resolved_dataset_code = dataset_code or settings.http_test_default_dataset_code
        payload = await request.body()
        try:
            result = await asyncio.to_thread(
                _process_http_frame,
                payload=payload,
                dataset_code=resolved_dataset_code,
                apply_session_id=apply_session_id,
                response_format=response_format,
                settings=settings,
                hair_runtime_manager=app.state.hair_runtime_manager,
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
                "static_root": str(settings.static_root),
                "face_landmarker_model_path": str(settings.face_landmarker_model_path),
                "face_landmarker_model_exists": settings.face_landmarker_model_path.is_file(),
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
        return await runtime_frame_response(
            request,
            dataset_code=dataset_code,
            apply_session_id=apply_session_id,
            response_format=response_format,
        )

    @app.post("/api/runtime/render-frame")
    @app.post("/v2/api/runtime/render-frame")
    async def runtime_render_frame(
        request: Request,
        dataset_code: str | None = None,
        hair_id: int = 1,
        apply_session_id: str = "local-render-session",
        representative_asset_id: str | None = None,
        response_format: Literal["jpeg", "png"] = "jpeg",
    ) -> Response:
        return await runtime_frame_response(
            request,
            dataset_code=dataset_code,
            apply_session_id=apply_session_id,
            response_format=response_format,
        )
