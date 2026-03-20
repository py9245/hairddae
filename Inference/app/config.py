from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_json_array(name: str, default: str) -> tuple[dict[str, object], ...]:
    raw = _env_str(name, default)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return ()
    if not isinstance(payload, list):
        return ()
    return tuple(item for item in payload if isinstance(item, dict))


def _resolve_model_path(env_name: str, default_path: str, local_fallback: Path) -> Path:
    configured = os.getenv(env_name)
    if configured:
        return Path(configured).expanduser().resolve()

    default_resolved = Path(default_path).expanduser().resolve()
    if default_resolved.is_file():
        return default_resolved

    if local_fallback.is_file():
        return local_fallback.resolve()

    return default_resolved


@dataclass(frozen=True)
class Settings:
    app_name: str
    host: str
    port: int
    jwt_secret: str
    jwt_issuer: str
    ticket_audience: str
    node_id: str
    feature_schema_version: int
    transform_version: str
    static_root: Path
    face_landmarker_model_path: Path
    hair_segmenter_model_path: Path
    static_base_url: str
    hysteresis_margin: float
    min_hold_ms: int
    redis_url: str | None
    rtc_ice_servers: tuple[dict[str, object], ...]
    rtc_internal_ice_servers: tuple[dict[str, object], ...]
    rtc_process_max_dimension: int
    rtc_process_min_dimension: int
    rtc_process_step_dimension: int
    rtc_target_frame_latency_ms: int
    rtc_bald_cache_max_reuse_frames: int
    rtc_bald_cache_pose_delta_threshold_deg: float
    rtc_bald_cache_bbox_iou_threshold: float
    rtc_user_parsing_max_reuse_frames: int
    rtc_user_parsing_latency_max_reuse_frames: int
    rtc_user_parsing_pose_delta_threshold_deg: float
    rtc_user_parsing_center_delta_threshold_norm: float
    rtc_user_parsing_size_delta_threshold_norm: float
    rtc_user_parsing_bbox_iou_threshold: float
    http_test_enabled: bool
    http_test_default_dataset_code: str
    http_test_jpeg_quality: int

    @classmethod
    def from_env(cls) -> "Settings":
        project_root = Path(__file__).resolve().parents[1]
        local_models_dir = project_root / "models"
        redis_url = os.getenv("INFERENCE_REDIS_URL")
        if not redis_url:
            redis_host = os.getenv("REDIS_HOST")
            redis_port = os.getenv("REDIS_PORT", "6379")
            redis_password = os.getenv("REDIS_PASSWORD")
            if redis_host:
                if redis_password:
                    redis_url = f"redis://:{redis_password}@{redis_host}:{redis_port}/0"
                else:
                    redis_url = f"redis://{redis_host}:{redis_port}/0"

        return cls(
            app_name=_env_str("INFERENCE_APP_NAME", "hairapply-inference"),
            host=_env_str("INFERENCE_HOST", "0.0.0.0"),
            port=_env_int("INFERENCE_PORT", 8090),
            jwt_secret=_env_str(
                "INFERENCE_JWT_SECRET",
                _env_str(
                    "APP_SECURITY_JWT_SECRET",
                    "hairddae-local-jwt-secret-key-for-dev-only-2026",
                ),
            ),
            jwt_issuer=_env_str(
                "INFERENCE_JWT_ISSUER",
                _env_str("APP_SECURITY_JWT_ISSUER", "hairddae"),
            ),
            ticket_audience=_env_str("INFERENCE_TICKET_AUDIENCE", "inference"),
            node_id=_env_str("INFERENCE_NODE_ID", "infer-a-01"),
            feature_schema_version=_env_int("INFERENCE_FEATURE_SCHEMA_VERSION", 2),
            transform_version=_env_str("INFERENCE_TRANSFORM_VERSION", "affine_v1"),
            static_root=Path(_env_str("INFERENCE_STATIC_ROOT", "/opt/be-static")).resolve(),
            face_landmarker_model_path=_resolve_model_path(
                "INFERENCE_FACE_LANDMARKER_MODEL_PATH",
                "/opt/inference-models/face_landmarker.task",
                local_models_dir / "face_landmarker.task",
            ),
            hair_segmenter_model_path=_resolve_model_path(
                "INFERENCE_HAIR_SEGMENTER_MODEL_PATH",
                "/opt/inference-models/hair_segmenter.tflite",
                local_models_dir / "hair_segmenter.tflite",
            ),
            static_base_url=_env_str("INFERENCE_STATIC_BASE_URL", "/static").rstrip("/"),
            hysteresis_margin=float(_env_str("INFERENCE_HYSTERESIS_MARGIN", "4.0")),
            min_hold_ms=_env_int("INFERENCE_MIN_HOLD_MS", 400),
            redis_url=redis_url,
            rtc_ice_servers=_env_json_array("INFERENCE_RTC_ICE_SERVERS_JSON", "[]"),
            rtc_internal_ice_servers=_env_json_array(
                "INFERENCE_RTC_INTERNAL_ICE_SERVERS_JSON",
                "[]",
            ),
            rtc_process_max_dimension=_env_int("INFERENCE_RTC_PROCESS_MAX_DIMENSION", 960),
            rtc_process_min_dimension=_env_int("INFERENCE_RTC_PROCESS_MIN_DIMENSION", 640),
            rtc_process_step_dimension=_env_int("INFERENCE_RTC_PROCESS_STEP_DIMENSION", 160),
            rtc_target_frame_latency_ms=_env_int("INFERENCE_RTC_TARGET_FRAME_LATENCY_MS", 95),
            rtc_bald_cache_max_reuse_frames=_env_int("INFERENCE_RTC_BALD_CACHE_MAX_REUSE_FRAMES", 1),
            rtc_bald_cache_pose_delta_threshold_deg=float(
                _env_str("INFERENCE_RTC_BALD_CACHE_POSE_DELTA_THRESHOLD_DEG", "1.5")
            ),
            rtc_bald_cache_bbox_iou_threshold=float(
                _env_str("INFERENCE_RTC_BALD_CACHE_BBOX_IOU_THRESHOLD", "0.92")
            ),
            rtc_user_parsing_max_reuse_frames=_env_int(
                "INFERENCE_RTC_USER_PARSING_MAX_REUSE_FRAMES",
                1,
            ),
            rtc_user_parsing_latency_max_reuse_frames=_env_int(
                "INFERENCE_RTC_USER_PARSING_LATENCY_MAX_REUSE_FRAMES",
                2,
            ),
            rtc_user_parsing_pose_delta_threshold_deg=float(
                _env_str("INFERENCE_RTC_USER_PARSING_POSE_DELTA_THRESHOLD_DEG", "1.2")
            ),
            rtc_user_parsing_center_delta_threshold_norm=float(
                _env_str("INFERENCE_RTC_USER_PARSING_CENTER_DELTA_THRESHOLD_NORM", "0.018")
            ),
            rtc_user_parsing_size_delta_threshold_norm=float(
                _env_str("INFERENCE_RTC_USER_PARSING_SIZE_DELTA_THRESHOLD_NORM", "0.018")
            ),
            rtc_user_parsing_bbox_iou_threshold=float(
                _env_str("INFERENCE_RTC_USER_PARSING_BBOX_IOU_THRESHOLD", "0.86")
            ),
            http_test_enabled=_env_bool("INFERENCE_HTTP_TEST_ENABLED", False),
            http_test_default_dataset_code=_env_str("INFERENCE_HTTP_TEST_DEFAULT_DATASET_CODE", "0001"),
            http_test_jpeg_quality=_env_int("INFERENCE_HTTP_TEST_JPEG_QUALITY", 88),
        )
