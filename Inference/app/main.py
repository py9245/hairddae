from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.acceleration import detect_runtime_acceleration
from app.auth import build_replay_store
from app.bald import BaldPreprocessor
from app.catalog import AssetCatalog
from app.config import Settings
from app.face_tracking import ServerFaceTracker
from app.http_runtime import attach_http_runtime_routes
from app.rtc import attach_rtc_routes
from app.rtc_h264_acceleration import install_aiortc_h264_acceleration


def create_app() -> FastAPI:
    settings = Settings.from_env()
    replay_store = build_replay_store(settings)
    catalog = AssetCatalog(settings)
    acceleration = detect_runtime_acceleration()
    rtc_h264_acceleration = install_aiortc_h264_acceleration()
    face_tracker = ServerFaceTracker(
        settings.face_landmarker_model_path,
        delegate_preference=settings.mediapipe_delegate,
        running_mode=settings.http_face_landmarker_running_mode,
    )
    bald_processor = BaldPreprocessor(
        settings.hair_segmenter_model_path,
        delegate_preference=settings.mediapipe_delegate,
        running_mode=settings.http_hair_segmenter_running_mode,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            yield
        finally:
            for peer_connection in list(getattr(app.state, "rtc_peer_connections", set())):
                await peer_connection.close()
            bald_processor.close()
            face_tracker.close()
            await replay_store.close()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.state.settings = settings
    app.state.replay_store = replay_store
    app.state.catalog = catalog
    app.state.face_tracker = face_tracker
    app.state.bald_processor = bald_processor
    app.state.acceleration = acceleration
    app.state.rtc_h264_acceleration = rtc_h264_acceleration
    attach_rtc_routes(app)
    attach_http_runtime_routes(app)

    @app.get("/healthz")
    async def healthz() -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "service": settings.app_name,
                "node_id": settings.node_id,
                "acceleration": acceleration.to_dict(),
                "rtc_h264_acceleration": rtc_h264_acceleration,
                "http_processors": {
                    "face_tracker_delegate": face_tracker.acceleration,
                    "bald_processor_delegate": bald_processor.acceleration,
                    "bald_processor_warning": getattr(bald_processor, "initialization_warning", None),
                    "render_acceleration": settings.render_acceleration,
                    "face_tracker_running_mode": settings.http_face_landmarker_running_mode,
                    "bald_processor_running_mode": settings.http_hair_segmenter_running_mode,
                },
            }
        )

    return app
