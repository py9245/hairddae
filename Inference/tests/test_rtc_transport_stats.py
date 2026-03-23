from __future__ import annotations

from app.rtc_metrics import RtcTransportStats


def test_rtc_transport_stats_skips_first_remote_sample() -> None:
    stats = RtcTransportStats()

    recorded = stats.record(42.5)

    assert recorded is False
    assert stats.first_remote_excluded is True
    assert stats.sample_count == 0
    assert stats.average_ms == 0.0
    assert stats.max_ms == 0.0
    assert stats.last_ms == 42.5


def test_rtc_transport_stats_tracks_average_and_max_after_skip() -> None:
    stats = RtcTransportStats()

    stats.record(100.0)
    assert stats.record(24.0) is True
    assert stats.record(36.0) is True
    assert stats.record(18.0) is True

    assert stats.sample_count == 3
    assert stats.average_ms == 26.0
    assert stats.max_ms == 36.0
    assert stats.last_ms == 18.0
