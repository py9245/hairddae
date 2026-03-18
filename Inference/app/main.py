from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.auth import build_replay_store
from app.catalog import AssetCatalog
from app.config import Settings
from app.hairddae_runtime_manager import HairddaeRuntimeManager
from app.http_runtime import attach_http_runtime_routes
from app.lazy_runtime_dependencies import LazyBaldPreprocessor, LazyFaceTracker
from app.rtc import attach_rtc_routes


def create_app() -> FastAPI:
    settings = Settings.from_env()
    replay_store = build_replay_store(settings)
    catalog = AssetCatalog(settings)
    face_tracker = LazyFaceTracker(settings.face_landmarker_model_path)
    bald_processor = LazyBaldPreprocessor(settings.hair_segmenter_model_path)
    hair_runtime_manager = HairddaeRuntimeManager(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            yield
        finally:
            for peer_connection in list(getattr(app.state, "rtc_peer_connections", set())):
                await peer_connection.close()
            hair_runtime_manager.close()
            bald_processor.close()
            face_tracker.close()
            await replay_store.close()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.state.settings = settings
    app.state.replay_store = replay_store
    app.state.catalog = catalog
    app.state.face_tracker = face_tracker
    app.state.bald_processor = bald_processor
    app.state.hair_runtime_manager = hair_runtime_manager
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
