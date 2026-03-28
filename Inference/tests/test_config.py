from __future__ import annotations

from app.config import DEFAULT_RTC_FPS, Settings
from conftest import apply_test_env


def test_settings_default_rtc_fps_matches_constant(monkeypatch) -> None:
    apply_test_env(monkeypatch)
    monkeypatch.delenv("INFERENCE_RTC_INPUT_FPS", raising=False)
    monkeypatch.delenv("INFERENCE_RTC_OUTPUT_FPS", raising=False)

    settings = Settings.from_env()

    assert settings.rtc_input_fps == DEFAULT_RTC_FPS
    assert settings.rtc_output_fps == DEFAULT_RTC_FPS
