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
    ws_protocol: str
    static_root: Path
    face_landmarker_model_path: Path
    hair_segmenter_model_path: Path
    static_base_url: str
    processed_timeout_ms: int
    heartbeat_interval_ms: int
    idle_ttl_ms: int
    hysteresis_margin: float
    min_hold_ms: int
    redis_url: str | None
    rtc_ice_servers: tuple[dict[str, object], ...]
    rtc_internal_ice_servers: tuple[dict[str, object], ...]
    http_test_enabled: bool
    http_test_default_dataset_code: str
    http_test_jpeg_quality: int
    bald_preprocess_enabled: bool

    @classmethod
    def from_env(cls) -> "Settings":
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
            ws_protocol=_env_str("INFERENCE_WS_PROTOCOL", "hairapply.v2"),
            static_root=Path(_env_str("INFERENCE_STATIC_ROOT", "/opt/be-static")).resolve(),
            face_landmarker_model_path=Path(
                _env_str(
                    "INFERENCE_FACE_LANDMARKER_MODEL_PATH",
                    "/opt/inference-models/face_landmarker.task",
                )
            ).resolve(),
            hair_segmenter_model_path=Path(
                _env_str(
                    "INFERENCE_HAIR_SEGMENTER_MODEL_PATH",
                    "/opt/inference-models/hair_segmenter.tflite",
                )
            ).resolve(),
            static_base_url=_env_str("INFERENCE_STATIC_BASE_URL", "/static").rstrip("/"),
            processed_timeout_ms=_env_int("INFERENCE_PROCESSED_TIMEOUT_MS", 250),
            heartbeat_interval_ms=_env_int("INFERENCE_HEARTBEAT_INTERVAL_MS", 5000),
            idle_ttl_ms=_env_int("INFERENCE_IDLE_TTL_MS", 30000),
            hysteresis_margin=float(_env_str("INFERENCE_HYSTERESIS_MARGIN", "4.0")),
            min_hold_ms=_env_int("INFERENCE_MIN_HOLD_MS", 400),
            redis_url=redis_url,
            rtc_ice_servers=_env_json_array("INFERENCE_RTC_ICE_SERVERS_JSON", "[]"),
            rtc_internal_ice_servers=_env_json_array(
                "INFERENCE_RTC_INTERNAL_ICE_SERVERS_JSON",
                "[]",
            ),
            http_test_enabled=_env_bool("INFERENCE_HTTP_TEST_ENABLED", False),
            http_test_default_dataset_code=_env_str("INFERENCE_HTTP_TEST_DEFAULT_DATASET_CODE", "0001"),
            http_test_jpeg_quality=_env_int("INFERENCE_HTTP_TEST_JPEG_QUALITY", 88),
            bald_preprocess_enabled=_env_bool("INFERENCE_BALD_PREPROCESS_ENABLED", False),
        )
