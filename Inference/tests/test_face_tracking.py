from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("mediapipe")

from app.face_tracking import ServerFaceTracker


class DummyLandmarker:
    def close(self) -> None:
        return None


def test_face_tracker_uses_requested_cpu_delegate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = []

    def fake_create_from_options(options: object) -> DummyLandmarker:
        created.append(options)
        return DummyLandmarker()

    monkeypatch.setattr(
        "app.face_tracking.vision.FaceLandmarker.create_from_options",
        fake_create_from_options,
    )

    tracker = ServerFaceTracker(Path("fake.task"), delegate="cpu")
    try:
        assert tracker.delegate == "cpu"
        assert len(created) == 1
    finally:
        tracker.close()


def test_face_tracker_falls_back_to_cpu_when_gpu_init_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = []
    calls = {"count": 0}

    def fake_create_from_options(options: object) -> DummyLandmarker:
        calls["count"] += 1
        created.append(options)
        if calls["count"] == 1:
            raise RuntimeError("gpu init failed")
        return DummyLandmarker()

    monkeypatch.setattr(
        "app.face_tracking.vision.FaceLandmarker.create_from_options",
        fake_create_from_options,
    )

    tracker = ServerFaceTracker(Path("fake.task"), delegate="gpu")
    try:
        assert tracker.delegate == "cpu"
        assert len(created) == 2
    finally:
        tracker.close()
