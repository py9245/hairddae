from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path

DEFAULT_RTC_FPS = 15


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


def _env_json_array_fallback(names: tuple[str, ...], default: str) -> tuple[dict[str, object], ...]:
    for name in names:
        value = os.getenv(name)
        if value is not None and value != "":
            return _env_json_array(name, default)
    raw = default
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return ()
    if not isinstance(payload, list):
        return ()
    return tuple(item for item in payload if isinstance(item, dict))


def _env_csv(name: str, default: str) -> tuple[str, ...]:
    raw = _env_str(name, default)
    values = [item.strip() for item in raw.split(",")]
    return tuple(item for item in values if item)


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
    ticket_algorithms: tuple[str, ...]
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
    rtc_hair_control_map: tuple[dict[str, object], ...]
    rtc_stats_interval_ms: int
    rtc_require_hello: bool
    rtc_control_channel_name: str
    rtc_send_processed_events: bool
    rtc_input_width: int
    rtc_input_height: int
    rtc_input_fps: int
    rtc_output_width: int
    rtc_output_height: int
    rtc_output_fps: int
    rtc_udp_port_min: int
    rtc_udp_port_max: int
    rtc_mirrored_input: bool
    rtc_output_mirrored: bool
    rtc_renderer_name: str
    rtc_latency_renderer_name: str
    rtc_hair_attenuation_enabled: bool
    rtc_hair_segmentation_enabled: bool
    rtc_hair_segmentation_confidence_threshold: float
    rtc_hair_attenuation_strength: float
    rtc_hair_attenuation_desaturation: float
    rtc_hair_attenuation_brightness_lift: float
    rtc_hair_attenuation_blur_kernel_scale: float
    rtc_hair_attenuation_max_work_dimension: int
    rtc_disable_fringe_suppression: bool
    rtc_disable_covered_suppression: bool
    rtc_disable_outer_bulk_suppression: bool
    rtc_disable_hair_overlay: bool
    rtc_preserve_eyes_enabled: bool
    rtc_bald_test_mode: bool
    rtc_enable_h264_nvenc: bool
    rtc_enable_h264_cuvid: bool
    rtc_disable_user_parsing_in_latency_mode: bool
    face_tracker_delegate: str
    hair_segmenter_delegate: str
    face_tracker_num_faces: int
    rtc_max_pending_frames: int
    rtc_process_max_dimension: int
    rtc_process_min_dimension: int
    rtc_process_step_dimension: int
    rtc_target_frame_latency_ms: int
    rtc_adaptive_slow_threshold_ratio: float
    rtc_adaptive_fast_threshold_ratio: float
    rtc_user_parsing_max_reuse_frames: int
    rtc_user_parsing_latency_max_reuse_frames: int
    rtc_user_parsing_pose_delta_threshold_deg: float
    rtc_user_parsing_center_delta_threshold_norm: float
    rtc_user_parsing_size_delta_threshold_norm: float
    rtc_user_parsing_bbox_iou_threshold: float
    startup_prewarm_enabled: bool
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
            ticket_algorithms=_env_csv("INFERENCE_TICKET_ALGORITHMS", "HS256"),
            ticket_audience=_env_str("INFERENCE_TICKET_AUDIENCE", "inference"),
            node_id=_env_str("INFERENCE_NODE_ID", "infer-a-01"),
            feature_schema_version=_env_int("INFERENCE_FEATURE_SCHEMA_VERSION", 2),
            transform_version=_env_str("INFERENCE_TRANSFORM_VERSION", "affine_v1"),
            static_root=Path(
                _env_str(
                    "INFERENCE_STATIC_ROOT",
                    _env_str("INFERENCE_ASSET_ROOT", "/opt/be-static"),
                )
            ).resolve(),
            face_landmarker_model_path=_resolve_model_path(
                "INFERENCE_FACE_LANDMARKER_MODEL_PATH",
                "/opt/inference-models/face_landmarker.task",
                local_models_dir / "face_landmarker.task",
            ),
            hair_segmenter_model_path=_resolve_model_path(
                "INFERENCE_HAIR_SEGMENTER_MODEL_PATH",
                "/opt/inference-models/hair_segmenter.tflite",
                local_models_dir / "mediapipe" / "hair_segmenter.tflite",
            ),
            static_base_url=_env_str("INFERENCE_STATIC_BASE_URL", "/static").rstrip("/"),
            hysteresis_margin=float(_env_str("INFERENCE_HYSTERESIS_MARGIN", "4.0")),
            min_hold_ms=_env_int("INFERENCE_MIN_HOLD_MS", 400),
            redis_url=redis_url,
            rtc_ice_servers=_env_json_array_fallback(
                (
                    "INFERENCE_RTC_ICE_SERVERS_JSON",
                    "APP_INFERENCE_RTC_ICE_SERVERS_JSON",
                ),
                "[]",
            ),
            rtc_internal_ice_servers=_env_json_array_fallback(
                (
                    "INFERENCE_RTC_INTERNAL_ICE_SERVERS_JSON",
                    "APP_INFERENCE_RTC_INTERNAL_ICE_SERVERS_JSON",
                    "APP_INFERENCE_RTC_ICE_SERVERS_JSON",
                ),
                "[]",
            ),
            rtc_hair_control_map=_env_json_array(
                "INFERENCE_RTC_HAIR_CONTROL_MAP_JSON",
                "[]",
            ),
            rtc_stats_interval_ms=max(0, _env_int("INFERENCE_RTC_STATS_INTERVAL_MS", 1000)),
            rtc_require_hello=_env_bool("INFERENCE_RTC_REQUIRE_HELLO", False),
            rtc_control_channel_name=_env_str("INFERENCE_RTC_CONTROL_CHANNEL_NAME", "control"),
            rtc_send_processed_events=_env_bool("INFERENCE_RTC_SEND_PROCESSED_EVENTS", False),
            rtc_input_width=_env_int("INFERENCE_RTC_INPUT_WIDTH", 576),
            rtc_input_height=_env_int("INFERENCE_RTC_INPUT_HEIGHT", 1024),
            rtc_input_fps=_env_int("INFERENCE_RTC_INPUT_FPS", DEFAULT_RTC_FPS),
            rtc_output_width=_env_int("INFERENCE_RTC_OUTPUT_WIDTH", 576),
            rtc_output_height=_env_int("INFERENCE_RTC_OUTPUT_HEIGHT", 1024),
            rtc_output_fps=_env_int("INFERENCE_RTC_OUTPUT_FPS", DEFAULT_RTC_FPS),
            rtc_udp_port_min=_env_int("INFERENCE_RTC_UDP_PORT_MIN", 40000),
            rtc_udp_port_max=_env_int("INFERENCE_RTC_UDP_PORT_MAX", 40199),
            rtc_mirrored_input=_env_bool("INFERENCE_RTC_MIRRORED_INPUT", False),
            rtc_output_mirrored=_env_bool("INFERENCE_RTC_OUTPUT_MIRRORED", True),
            rtc_renderer_name=_env_str("INFERENCE_RTC_RENDERER_NAME", "legacy"),
            rtc_latency_renderer_name=_env_str("INFERENCE_RTC_LATENCY_RENDERER_NAME", "legacy"),
            rtc_hair_attenuation_enabled=_env_bool("INFERENCE_RTC_HAIR_ATTENUATION_ENABLED", True),
            rtc_hair_segmentation_enabled=_env_bool("INFERENCE_RTC_HAIR_SEGMENTATION_ENABLED", True),
            rtc_hair_segmentation_confidence_threshold=float(
                _env_str("INFERENCE_RTC_HAIR_SEGMENTATION_CONFIDENCE_THRESHOLD", "0.32")
            ),
            rtc_hair_attenuation_strength=float(
                _env_str("INFERENCE_RTC_HAIR_ATTENUATION_STRENGTH", "0.78")
            ),
            rtc_hair_attenuation_desaturation=float(
                _env_str("INFERENCE_RTC_HAIR_ATTENUATION_DESATURATION", "0.24")
            ),
            rtc_hair_attenuation_brightness_lift=float(
                _env_str("INFERENCE_RTC_HAIR_ATTENUATION_BRIGHTNESS_LIFT", "0.05")
            ),
            rtc_hair_attenuation_blur_kernel_scale=float(
                _env_str("INFERENCE_RTC_HAIR_ATTENUATION_BLUR_KERNEL_SCALE", "0.085")
            ),
            rtc_hair_attenuation_max_work_dimension=_env_int(
                "INFERENCE_RTC_HAIR_ATTENUATION_MAX_WORK_DIMENSION",
                176,
            ),
            rtc_disable_fringe_suppression=_env_bool("INFERENCE_RTC_DISABLE_FRINGE_SUPPRESSION", False),
            rtc_disable_covered_suppression=_env_bool("INFERENCE_RTC_DISABLE_COVERED_SUPPRESSION", False),
            rtc_disable_outer_bulk_suppression=_env_bool("INFERENCE_RTC_DISABLE_OUTER_BULK_SUPPRESSION", False),
            rtc_disable_hair_overlay=_env_bool("INFERENCE_RTC_DISABLE_HAIR_OVERLAY", False),
            rtc_preserve_eyes_enabled=_env_bool("INFERENCE_RTC_PRESERVE_EYES_ENABLED", False),
            rtc_bald_test_mode=_env_bool("INFERENCE_RTC_BALD_TEST_MODE", False),
            rtc_enable_h264_nvenc=_env_bool("INFERENCE_RTC_ENABLE_H264_NVENC", False),
            rtc_enable_h264_cuvid=_env_bool("INFERENCE_RTC_ENABLE_H264_CUVID", False),
            rtc_disable_user_parsing_in_latency_mode=_env_bool(
                "INFERENCE_RTC_DISABLE_USER_PARSING_IN_LATENCY_MODE",
                False,
            ),
            face_tracker_delegate=_env_str("INFERENCE_FACE_TRACKER_DELEGATE", "cpu"),
            hair_segmenter_delegate=_env_str("INFERENCE_HAIR_SEGMENTER_DELEGATE", "gpu"),
            face_tracker_num_faces=max(1, _env_int("INFERENCE_FACE_TRACKER_NUM_FACES", 1)),
            rtc_max_pending_frames=max(1, _env_int("INFERENCE_RTC_MAX_PENDING_FRAMES", 1)),
            rtc_process_max_dimension=_env_int("INFERENCE_RTC_PROCESS_MAX_DIMENSION", 960),
            rtc_process_min_dimension=_env_int("INFERENCE_RTC_PROCESS_MIN_DIMENSION", 640),
            rtc_process_step_dimension=_env_int("INFERENCE_RTC_PROCESS_STEP_DIMENSION", 160),
            rtc_target_frame_latency_ms=_env_int("INFERENCE_RTC_TARGET_FRAME_LATENCY_MS", 95),
            rtc_adaptive_slow_threshold_ratio=float(
                _env_str("INFERENCE_RTC_ADAPTIVE_SLOW_THRESHOLD_RATIO", "1.45")
            ),
            rtc_adaptive_fast_threshold_ratio=float(
                _env_str("INFERENCE_RTC_ADAPTIVE_FAST_THRESHOLD_RATIO", "0.78")
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
            startup_prewarm_enabled=_env_bool("INFERENCE_STARTUP_PREWARM_ENABLED", False),
            http_test_enabled=_env_bool("INFERENCE_HTTP_TEST_ENABLED", False),
            http_test_default_dataset_code=_env_str("INFERENCE_HTTP_TEST_DEFAULT_DATASET_CODE", "0001"),
            http_test_jpeg_quality=_env_int("INFERENCE_HTTP_TEST_JPEG_QUALITY", 88),
        )
