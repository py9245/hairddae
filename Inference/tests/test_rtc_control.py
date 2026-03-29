from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pytest
from aiortc.mediastreams import VIDEO_CLOCK_RATE, VIDEO_TIME_BASE

pytest.importorskip("cv2")
pytest.importorskip("mediapipe")
pytest.importorskip("torch")
pytest.importorskip("torchvision")

from app.config import Settings
from app.rtc import (
    ControlMessageError,
    RtcSessionState,
    RtcServerTrackedRenderTrack,
    _augment_control_payload,
    _process_control_message,
    _send_channel_json,
)
from conftest import apply_test_env


class DummyCatalog:
    def __init__(self, valid_targets: set[tuple[str, str | None]]) -> None:
        self._valid_targets = valid_targets

    def ensure_control_target(
        self,
        dataset_code: str,
        representative_asset_id: str | None = None,
    ) -> None:
        target = (dataset_code, representative_asset_id)
        if target in self._valid_targets:
            return
        if representative_asset_id is not None and (dataset_code, None) in self._valid_targets:
            raise ValueError(
                f"unknown representative_asset_id {representative_asset_id} for dataset {dataset_code}"
            )
        raise ValueError(f"unknown dataset_code {dataset_code}")


class DummyRuntimeManager:
    def __init__(self) -> None:
        self.reset_calls: list[tuple[str, str]] = []
        self.process_calls = 0
        self.last_process_kwargs: dict[str, object] | None = None

    def reset_session(self, dataset_code: str, session_id: str) -> None:
        self.reset_calls.append((dataset_code, session_id))

    def process_frame(self, **_: object) -> dict[str, object]:
        self.process_calls += 1
        self.last_process_kwargs = dict(_)
        return {
            "output_frame_bgr": None,
            "selected_asset_id": None,
            "status": "ok",
        }


class DummyChannel:
    def __init__(self) -> None:
        self.readyState = "open"
        self.label = "control"
        self.bufferedAmount = 7
        self.bufferedAmountLowThreshold = 4
        self.sent_payloads: list[dict[str, object]] = []

    def send(self, payload: str) -> None:
        self.sent_payloads.append(json.loads(payload))


def build_settings(
    monkeypatch: pytest.MonkeyPatch,
    *,
    require_hello: bool = False,
    hair_control_map_json: str = "[]",
    mirrored_input: bool = False,
) -> Settings:
    apply_test_env(
        monkeypatch,
        INFERENCE_NODE_ID="infer-gpu-01",
        INFERENCE_RTC_REQUIRE_HELLO="true" if require_hello else "false",
        INFERENCE_RTC_HAIR_CONTROL_MAP_JSON=hair_control_map_json,
        INFERENCE_RTC_MIRRORED_INPUT="true" if mirrored_input else "false",
    )
    return Settings.from_env()


def build_claims() -> SimpleNamespace:
    return SimpleNamespace(
        apply_session_id="rtc-control-test-session",
        hair_id=12,
        dataset_code="0001",
        representative_asset_id="asset-12",
    )


def test_hello_updates_stage_and_returns_hair_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = build_settings(monkeypatch, mirrored_input=False)
    claims = build_claims()
    state = RtcSessionState(
        active_hair_id=claims.hair_id,
        active_dataset_code=claims.dataset_code,
        active_representative_asset_id=claims.representative_asset_id,
    )
    catalog = DummyCatalog({("0001", "asset-12")})
    runtime_manager = DummyRuntimeManager()

    payloads = _process_control_message(
        json.dumps(
            {
                "type": "hello",
                "session_version": 1,
                "stage_width": 576,
                "stage_height": 1024,
                "fps": 15,
                "mirrored": True,
                "hair_id": 12,
                "representative_asset_id": "asset-12",
            }
        ),
        state=state,
        settings=settings,
        claims=claims,
        catalog=catalog,
        hair_runtime_manager=runtime_manager,
    )

    assert state.hello_received is True
    assert state.stage_width == 576
    assert state.stage_height == 1024
    assert state.stage_fps == 15.0
    assert state.mirrored is True
    assert len(payloads) == 1
    assert payloads[0]["type"] == "hair_applied"
    assert payloads[0]["hair_id"] == 12
    assert payloads[0]["dataset_code"] == "0001"
    assert payloads[0]["changed"] is False
    assert payloads[0]["source"] == "hello"
    assert payloads[0]["representative_asset_id"] == "asset-12"
    assert isinstance(payloads[0]["server_ts_ms"], int)
    assert runtime_manager.reset_calls == []


def test_select_hair_uses_env_mapping_and_resets_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = build_settings(
        monkeypatch,
        hair_control_map_json='[{"hair_id":27,"dataset_code":"0002","representative_asset_id":"asset-27"}]',
    )
    claims = build_claims()
    state = RtcSessionState(
        active_hair_id=claims.hair_id,
        active_dataset_code=claims.dataset_code,
        active_representative_asset_id=claims.representative_asset_id,
        hello_received=True,
    )
    catalog = DummyCatalog(
        {
            ("0001", "asset-12"),
            ("0002", "asset-27"),
        }
    )
    runtime_manager = DummyRuntimeManager()

    payloads = _process_control_message(
        '{"type":"select_hair","hair_id":27}',
        state=state,
        settings=settings,
        claims=claims,
        catalog=catalog,
        hair_runtime_manager=runtime_manager,
    )

    assert state.active_hair_id == 27
    assert state.active_dataset_code == "0002"
    assert state.active_representative_asset_id == "asset-27"
    assert payloads[0]["type"] == "hair_applied"
    assert payloads[0]["hair_id"] == 27
    assert payloads[0]["dataset_code"] == "0002"
    assert payloads[0]["source"] == "select_hair"
    assert payloads[0]["changed"] is True
    assert payloads[0]["representative_asset_id"] == "asset-27"
    assert runtime_manager.reset_calls == [
        ("0001", claims.apply_session_id),
        ("0002", claims.apply_session_id),
    ]


def test_select_hair_uses_dataset_code_from_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = build_settings(monkeypatch)
    claims = build_claims()
    state = RtcSessionState(
        active_hair_id=claims.hair_id,
        active_dataset_code=claims.dataset_code,
        active_representative_asset_id=claims.representative_asset_id,
        hello_received=True,
    )
    catalog = DummyCatalog(
        {
            ("0001", "asset-12"),
            ("0002", None),
        }
    )
    runtime_manager = DummyRuntimeManager()

    payloads = _process_control_message(
        '{"type":"select_hair","hair_id":77,"dataset_code":"0002"}',
        state=state,
        settings=settings,
        claims=claims,
        catalog=catalog,
        hair_runtime_manager=runtime_manager,
    )

    assert state.active_hair_id == 77
    assert state.active_dataset_code == "0002"
    assert state.active_representative_asset_id is None
    assert payloads[0]["type"] == "hair_applied"
    assert payloads[0]["hair_id"] == 77
    assert payloads[0]["dataset_code"] == "0002"
    assert "representative_asset_id" not in payloads[0]
    assert runtime_manager.reset_calls == [
        ("0001", claims.apply_session_id),
        ("0002", claims.apply_session_id),
    ]


def test_heartbeat_ack_echoes_client_timestamp(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = build_settings(monkeypatch)
    claims = build_claims()
    state = RtcSessionState(
        active_hair_id=claims.hair_id,
        active_dataset_code=claims.dataset_code,
        active_representative_asset_id=claims.representative_asset_id,
    )
    catalog = DummyCatalog({("0001", "asset-12")})
    runtime_manager = DummyRuntimeManager()

    payloads = _process_control_message(
        '{"type":"heartbeat","ts_ms":1774086000000}',
        state=state,
        settings=settings,
        claims=claims,
        catalog=catalog,
        hair_runtime_manager=runtime_manager,
    )

    assert len(payloads) == 1
    assert payloads[0]["type"] == "heartbeat_ack"
    assert payloads[0]["apply_session_id"] == claims.apply_session_id
    assert payloads[0]["ts_ms"] == 1774086000000
    assert isinstance(payloads[0]["server_ts_ms"], int)


def test_augment_control_payload_includes_debug_fields() -> None:
    channel = DummyChannel()

    payload = _augment_control_payload(
        {"type": "heartbeat_ack", "server_ts_ms": 123},
        message_type="heartbeat",
        message_bytes=28,
        server_received_ts_ms=111,
        processing_ms=2.75,
        response_index=1,
        response_count=1,
        channel=channel,
        client_ts_ms=99,
    )

    assert payload["control_message_type"] == "heartbeat"
    assert payload["control_message_bytes"] == 28
    assert payload["control_processing_ms"] == 2.75
    assert payload["control_response_index"] == 1
    assert payload["control_response_count"] == 1
    assert payload["server_received_ts_ms"] == 111
    assert payload["client_ts_ms"] == 99
    assert payload["data_channel_ready_state"] == "open"
    assert payload["data_channel_buffered_amount"] == 7
    assert payload["data_channel_label"] == "control"


def test_send_channel_json_updates_channel_metrics() -> None:
    state = RtcSessionState()
    channel = DummyChannel()

    sent = _send_channel_json(channel, state, {"type": "connected"})

    assert sent is True
    assert len(channel.sent_payloads) == 1
    assert channel.sent_payloads[0]["type"] == "connected"
    assert state.data_channel_send_count == 1
    assert state.last_channel_payload_type == "connected"
    assert state.last_channel_buffered_amount == 7
    assert state.last_channel_send_latency_ms >= 0.0


def test_bald_test_mode_keeps_prepared_frame_as_runtime_base(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = build_settings(monkeypatch)
    object.__setattr__(settings, "rtc_bald_test_mode", True)

    track = RtcServerTrackedRenderTrack.__new__(RtcServerTrackedRenderTrack)
    runtime_manager = DummyRuntimeManager()
    claims = build_claims()
    track._settings = settings
    track._hair_runtime_manager = runtime_manager
    track._claims = claims
    track._state = RtcSessionState(
        active_hair_id=claims.hair_id,
        active_dataset_code=claims.dataset_code,
        active_representative_asset_id=claims.representative_asset_id,
    )

    prepared_frame = np.full((12, 10, 3), 91, dtype=np.uint8)
    tracked_user_row = {
        "ok": True,
        "pose": {"yaw_1deg": 0, "pitch_1deg": 0, "roll_1deg": 0},
    }

    def _prepare(
        frame_bgr: np.ndarray,
        seq: int,
    ) -> tuple[np.ndarray, dict[str, object], str, dict[str, float], None]:
        assert seq == 7
        assert frame_bgr.shape == prepared_frame.shape
        return (
            prepared_frame,
            tracked_user_row,
            "segmented",
            {
                "tracking_latency_ms": 1.2,
                "hair_segmentation_latency_ms": 2.3,
                "hair_attenuation_latency_ms": 3.4,
            },
            None,
        )

    track._prepare_frame_for_hair_runtime = _prepare

    runtime_result, attenuation_status, prepare_metrics, tracking_feature = track._process_runtime_frame(
        prepared_frame,
        7,
        True,
    )

    assert attenuation_status == "segmented"
    assert prepare_metrics["hair_segmentation_latency_ms"] == 2.3
    assert tracking_feature is None
    assert runtime_result["status"] == "ok"
    assert runtime_manager.process_calls == 1
    assert runtime_manager.last_process_kwargs is not None
    assert runtime_manager.last_process_kwargs["render_frame_bgr"] is prepared_frame
    assert runtime_manager.last_process_kwargs["source_frame_bgr"] is prepared_frame
    assert runtime_manager.last_process_kwargs["frame_bgr"] is prepared_frame


def test_select_hair_requires_hello_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = build_settings(monkeypatch, require_hello=True)
    claims = build_claims()
    state = RtcSessionState(
        active_hair_id=claims.hair_id,
        active_dataset_code=claims.dataset_code,
        active_representative_asset_id=claims.representative_asset_id,
    )
    catalog = DummyCatalog({("0001", "asset-12")})
    runtime_manager = DummyRuntimeManager()

    with pytest.raises(ControlMessageError) as exc_info:
        _process_control_message(
            '{"type":"select_hair","hair_id":12}',
            state=state,
            settings=settings,
            claims=claims,
            catalog=catalog,
            hair_runtime_manager=runtime_manager,
        )

    assert exc_info.value.code == "HELLO_REQUIRED"


def test_select_hair_without_mapping_raises_error(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = build_settings(monkeypatch)
    claims = build_claims()
    state = RtcSessionState(
        active_hair_id=claims.hair_id,
        active_dataset_code=claims.dataset_code,
        active_representative_asset_id=claims.representative_asset_id,
        hello_received=True,
    )
    catalog = DummyCatalog({("0001", "asset-12")})
    runtime_manager = DummyRuntimeManager()

    with pytest.raises(ControlMessageError) as exc_info:
        _process_control_message(
            '{"type":"select_hair","hair_id":999}',
            state=state,
            settings=settings,
            claims=claims,
            catalog=catalog,
            hair_runtime_manager=runtime_manager,
        )

    assert exc_info.value.code == "HAIR_MAPPING_NOT_FOUND"


def test_bundle_fallback_frame_passes_original_frame_image(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyCatalogWithBundle:
        def recommend(self, dataset_code: str, feature: object, representative_asset_id: str | None = None) -> object:
            return object()

    track = RtcServerTrackedRenderTrack.__new__(RtcServerTrackedRenderTrack)
    track._catalog = DummyCatalogWithBundle()
    track._active_dataset_code = lambda: "0003"  # type: ignore[method-assign]
    track._active_representative_asset_id = lambda: None  # type: ignore[method-assign]

    captured: dict[str, object] = {"original_frame_image": None}

    def fake_compose_bundle_frame(frame_image: object, bundle: object, **kwargs: object) -> object:
        captured["original_frame_image"] = kwargs.get("original_frame_image")
        return frame_image

    monkeypatch.setattr("app.fallback_render_pipeline.compose_bundle_frame", fake_compose_bundle_frame)

    frame_bgr = np.full((8, 8, 3), 90, dtype=np.uint8)
    original_bgr = np.full((8, 8, 3), 25, dtype=np.uint8)
    rendered_bgr, bundle, _ = track._render_bundle_fallback_frame(frame_bgr, original_bgr, object())

    assert bundle is not None
    assert rendered_bgr is not None
    assert captured["original_frame_image"] is not None


def test_output_timestamp_uses_configured_output_fps(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = build_settings(monkeypatch)
    object.__setattr__(settings, "rtc_output_fps", 15)

    track = RtcServerTrackedRenderTrack.__new__(RtcServerTrackedRenderTrack)
    track._settings = settings
    track._output_timestamp = None

    first_pts, first_time_base = track._next_output_timestamp()
    second_pts, second_time_base = track._next_output_timestamp()

    assert first_pts == 0
    assert second_pts - first_pts == int(round(VIDEO_CLOCK_RATE / 15.0))
    assert first_time_base == VIDEO_TIME_BASE
    assert second_time_base == VIDEO_TIME_BASE


def test_target_output_size_uses_configured_output_dimensions(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = build_settings(monkeypatch)
    object.__setattr__(settings, "rtc_output_width", 576)
    object.__setattr__(settings, "rtc_output_height", 1024)

    track = RtcServerTrackedRenderTrack.__new__(RtcServerTrackedRenderTrack)
    track._settings = settings

    assert track._target_output_size((432, 768)) == (576, 1024)
