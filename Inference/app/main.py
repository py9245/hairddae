from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
import logging
import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.auth import ReplayStore, build_replay_store
from app.catalog import AssetCatalog
from app.config import Settings
from app.hairddae_runtime_manager import HairddaeRuntimeManager
from app.http_runtime import attach_http_runtime_routes
from app.lazy_runtime_dependencies import LazyFaceTracker, LazyHairAttenuator, LazyHairSegmenter
from app.rtc_codec_accel import apply_rtc_codec_acceleration
from app.rtc import attach_rtc_routes
from app.rtc_udp_port_range import configure_aioice_udp_port_range

logger = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class AppDependencies:
    replay_store: ReplayStore
    catalog: AssetCatalog
    face_tracker: LazyFaceTracker
    hair_attenuator: LazyHairAttenuator | None
    hair_segmenter: LazyHairSegmenter | None
    hair_runtime_manager: HairddaeRuntimeManager


def _build_hair_attenuator(settings: Settings) -> LazyHairAttenuator | None:
    if not settings.rtc_hair_attenuation_enabled:
        return None
    return LazyHairAttenuator(
        strength=settings.rtc_hair_attenuation_strength,
        segmentation_confidence_threshold=settings.rtc_hair_segmentation_confidence_threshold,
        desaturation=settings.rtc_hair_attenuation_desaturation,
        brightness_lift=settings.rtc_hair_attenuation_brightness_lift,
        blur_kernel_scale=settings.rtc_hair_attenuation_blur_kernel_scale,
        max_work_dimension=settings.rtc_hair_attenuation_max_work_dimension,
        preserve_eyes_enabled=settings.rtc_preserve_eyes_enabled,
        disable_fringe_suppression=settings.rtc_disable_fringe_suppression,
        disable_covered_suppression=settings.rtc_disable_covered_suppression,
        disable_outer_bulk_suppression=settings.rtc_disable_outer_bulk_suppression,
        bald_test_mode=settings.rtc_bald_test_mode,
    )


def _build_hair_segmenter(settings: Settings) -> LazyHairSegmenter | None:
    if not settings.rtc_hair_segmentation_enabled:
        return None
    return LazyHairSegmenter(
        settings.hair_segmenter_model_path,
        delegate=settings.hair_segmenter_delegate,
    )


def _build_app_dependencies(settings: Settings) -> AppDependencies:
    return AppDependencies(
        replay_store=build_replay_store(settings),
        catalog=AssetCatalog(settings),
        face_tracker=LazyFaceTracker(
            settings.face_landmarker_model_path,
            num_faces=settings.face_tracker_num_faces,
            delegate=settings.face_tracker_delegate,
        ),
        hair_attenuator=_build_hair_attenuator(settings),
        hair_segmenter=_build_hair_segmenter(settings),
        hair_runtime_manager=HairddaeRuntimeManager(settings),
    )


def _attach_app_state(app: FastAPI, settings: Settings, dependencies: AppDependencies) -> None:
    app.state.settings = settings
    app.state.replay_store = dependencies.replay_store
    app.state.catalog = dependencies.catalog
    app.state.face_tracker = dependencies.face_tracker
    app.state.hair_segmenter = dependencies.hair_segmenter
    app.state.hair_attenuator = dependencies.hair_attenuator
    app.state.hair_runtime_manager = dependencies.hair_runtime_manager


def _startup_prewarm_dependencies(settings: Settings, dependencies: AppDependencies) -> None:
    if not settings.startup_prewarm_enabled:
        return

    started_at = time.perf_counter()
    face_tracker_ms = dependencies.face_tracker.warm_up()
    hair_segmenter_ms = None
    if dependencies.hair_segmenter is not None:
        hair_segmenter_ms = dependencies.hair_segmenter.warm_up()

    logger.info(
        "startup prewarm summary: enabled=%s face_tracker_ms=%.1f hair_segmenter_ms=%s total_ms=%.1f",
        settings.startup_prewarm_enabled,
        face_tracker_ms,
        None if hair_segmenter_ms is None else round(hair_segmenter_ms, 3),
        round((time.perf_counter() - started_at) * 1000.0, 3),
    )


async def _close_app_dependencies(app: FastAPI, dependencies: AppDependencies) -> None:
    for peer_connection in list(getattr(app.state, "rtc_peer_connections", set())):
        await peer_connection.close()
    dependencies.hair_runtime_manager.close()
    if dependencies.hair_segmenter is not None:
        dependencies.hair_segmenter.close()
    if dependencies.hair_attenuator is not None:
        dependencies.hair_attenuator.close()
    dependencies.face_tracker.close()
    await dependencies.replay_store.close()


def create_app() -> FastAPI:
    settings = Settings.from_env()
    apply_rtc_codec_acceleration(settings)
    configure_aioice_udp_port_range(
        settings.rtc_udp_port_min,
        settings.rtc_udp_port_max,
    )
    dependencies = _build_app_dependencies(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await asyncio.to_thread(_startup_prewarm_dependencies, settings, dependencies)
        try:
            yield
        finally:
            await _close_app_dependencies(app, dependencies)

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    _attach_app_state(app, settings, dependencies)
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
