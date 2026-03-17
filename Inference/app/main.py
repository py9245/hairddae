from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.auth import build_replay_store
from app.bald import BaldPreprocessor
from app.catalog import AssetCatalog
from app.config import Settings
from app.face_tracking import ServerFaceTracker
from app.http_runtime import attach_http_runtime_routes
from app.rtc import attach_rtc_routes


def create_app() -> FastAPI:
    settings = Settings.from_env()
    replay_store = build_replay_store(settings)
    catalog = AssetCatalog(settings)
    face_tracker = ServerFaceTracker(settings.face_landmarker_model_path)
    bald_processor = BaldPreprocessor(settings.hair_segmenter_model_path)

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

    return app
