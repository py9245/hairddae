from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
import numpy as np
from PIL import Image
import pytest

pytest.importorskip("cv2")
pytest.importorskip("mediapipe")
pytest.importorskip("torch")
pytest.importorskip("torchvision")

from app.main import create_app
from app.lazy_runtime_dependencies import LazyFaceTracker, LazyHairSegmenter
from conftest import apply_test_env


def build_client() -> TestClient:
    apply_test_env(
        INFERENCE_HTTP_TEST_ENABLED="true",
        INFERENCE_NODE_ID="infer-a-01",
    )
    return TestClient(create_app())


def test_healthz_returns_ok() -> None:
    with build_client() as client:
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_startup_prewarm_warms_face_tracker_and_hair_segmenter(monkeypatch: pytest.MonkeyPatch) -> None:
    apply_test_env(
        monkeypatch,
        INFERENCE_HTTP_TEST_ENABLED="true",
        INFERENCE_NODE_ID="infer-a-01",
        INFERENCE_STARTUP_PREWARM_ENABLED="true",
    )
    warmed_dependencies: list[str] = []

    monkeypatch.setattr(
        LazyFaceTracker,
        "warm_up",
        lambda self: warmed_dependencies.append("face_tracker") or 1.0,
    )
    monkeypatch.setattr(
        LazyHairSegmenter,
        "warm_up",
        lambda self: warmed_dependencies.append("hair_segmenter") or 1.0,
    )

    with TestClient(create_app()):
        pass

    assert warmed_dependencies == ["face_tracker", "hair_segmenter"]


def test_apply_route_removed() -> None:
    with build_client() as client:
        response = client.get("/apply")
        assert response.status_code == 404


def test_http_runtime_frame_returns_render_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    with build_client() as client:
        monkeypatch.setattr(
            client.app.state.hair_runtime_manager,
            "process_frame",
            lambda *args, **kwargs: {
                "status": "ok",
                "selected_asset_id": "asset-http-test",
                "selected_pose_key": "yaw+00_pitch+00_roll+00",
                "score": 3.25,
                "output_frame_bgr": np.full((32, 32, 3), 140, dtype=np.uint8),
                "user_row": {
                    "face_yaw_deg": 0,
                    "face_pitch_deg": 0,
                    "face_roll_deg": 0,
                },
                "feature_latency_ms": 4.0,
                "overlay_latency_ms": 7.5,
                "latency_ms": 12.3,
            },
        )

        image = Image.new("RGB", (32, 32), color=(120, 130, 140))
        buffer = BytesIO()
        image.save(buffer, format="JPEG")

        response = client.post(
            "/api/runtime/frame?dataset_code=0001&hair_id=1&apply_session_id=http-test-session",
            content=buffer.getvalue(),
            headers={"content-type": "image/jpeg"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"
        assert response.headers["x-inference-status"] == "ok"
        assert response.headers["x-selected-asset-id"] == "asset-http-test"
        assert response.headers["x-selected-pose-key"] == "yaw+00_pitch+00_roll+00"
        assert response.headers["x-processed-seq"] == "1"
