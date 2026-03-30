from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.hairddae_runtime_manager import HairddaeRuntimeManager
from conftest import apply_test_env


class FakeRuntime:
    created_count = 0

    def __init__(
        self,
        *,
        asset_root: str | Path | None = None,
        model_path: str | Path | None = None,
        jpeg_quality: int = 88,
        renderer_name: str = "legacy",
    ) -> None:
        self.asset_root = Path(asset_root or ".")
        self.model_path = Path(model_path or ".")
        self.jpeg_quality = jpeg_quality
        self.renderer_name = renderer_name
        self.index = FakeRuntime.created_count
        FakeRuntime.created_count += 1
        self.process_calls: list[dict[str, object]] = []
        self.reference_calls: list[str | None] = []
        self.reset_calls: list[str | None] = []
        self.closed = False

    def process_frame(self, *args: object, **kwargs: object) -> dict[str, object]:
        self.process_calls.append(dict(kwargs))
        return {"slot_index": self.index, "status": "ok"}

    def reference_face_bbox(self, session_id: str | None) -> dict[str, object]:
        self.reference_calls.append(session_id)
        return {"slot_index": self.index}

    def health(self) -> dict[str, object]:
        return {
            "ready": True,
            "active_session_count": len(self.process_calls),
            "shared_inference_lock": True,
        }

    def reset_session(self, session_id: str | None) -> None:
        self.reset_calls.append(session_id)

    def close(self) -> None:
        self.closed = True


def build_settings(monkeypatch: pytest.MonkeyPatch, *, slots: int) -> Settings:
    apply_test_env(
        monkeypatch,
        INFERENCE_RTC_RUNTIME_SLOTS_PER_DATASET=str(slots),
    )
    return Settings.from_env()


def test_runtime_manager_routes_new_sessions_round_robin_and_keeps_session_sticky(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = build_settings(monkeypatch, slots=2)
    FakeRuntime.created_count = 0
    monkeypatch.setattr("app.hairddae_runtime_manager.HairOverlayRuntime", FakeRuntime)

    manager = HairddaeRuntimeManager(settings)
    try:
        result_a = manager.process_frame(
            dataset_code="0001",
            frame_bgr=None,  # type: ignore[arg-type]
            session_id="session-a",
            encode_output=False,
        )
        result_a_repeat = manager.process_frame(
            dataset_code="0001",
            frame_bgr=None,  # type: ignore[arg-type]
            session_id="session-a",
            encode_output=False,
        )
        result_b = manager.process_frame(
            dataset_code="0001",
            frame_bgr=None,  # type: ignore[arg-type]
            session_id="session-b",
            encode_output=False,
        )
        result_c = manager.process_frame(
            dataset_code="0001",
            frame_bgr=None,  # type: ignore[arg-type]
            session_id="session-c",
            encode_output=False,
        )
    finally:
        manager.close()

    assert FakeRuntime.created_count == 2
    assert result_a["slot_index"] == 0
    assert result_b["slot_index"] == 1
    assert result_a["slot_index"] == result_a_repeat["slot_index"]
    assert result_c["slot_index"] == 0
    assert result_a["status"] == "ok"
    assert result_b["status"] == "ok"
    assert result_c["status"] == "ok"


def test_runtime_manager_health_aggregates_slot_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = build_settings(monkeypatch, slots=2)
    FakeRuntime.created_count = 0
    monkeypatch.setattr("app.hairddae_runtime_manager.HairOverlayRuntime", FakeRuntime)

    manager = HairddaeRuntimeManager(settings)
    try:
        manager.process_frame(
            dataset_code="0001",
            frame_bgr=None,  # type: ignore[arg-type]
            session_id="session-a",
            encode_output=False,
        )
        manager.process_frame(
            dataset_code="0001",
            frame_bgr=None,  # type: ignore[arg-type]
            session_id="session-b",
            encode_output=False,
        )
        health = manager.health("0001")
    finally:
        manager.close()

    assert health["runtime_slots"] == 2
    assert len(health["slot_active_session_counts"]) == 2
    assert health["active_session_count"] == sum(health["slot_active_session_counts"])
    assert health["shared_inference_lock"] is False


def test_runtime_manager_reset_targets_session_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = build_settings(monkeypatch, slots=2)
    FakeRuntime.created_count = 0
    monkeypatch.setattr("app.hairddae_runtime_manager.HairOverlayRuntime", FakeRuntime)

    manager = HairddaeRuntimeManager(settings)
    try:
        manager.process_frame(
            dataset_code="0001",
            frame_bgr=None,  # type: ignore[arg-type]
            session_id="session-a",
            encode_output=False,
        )
        runtime_pool = manager._runtime_cache["0001"]
        target_slot = runtime_pool[0].index if runtime_pool[0].process_calls else runtime_pool[1].index
        manager.reset_session("0001", "session-a")
    finally:
        manager.close()

    reset_counts = {
        runtime.index: len(runtime.reset_calls)
        for runtime in runtime_pool
    }
    assert reset_counts[target_slot] == 1
    assert sum(reset_counts.values()) == 1
