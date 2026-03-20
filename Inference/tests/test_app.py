from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
import numpy as np
from PIL import Image
import pytest

from app.catalog import AssetBundle
from app.main import create_app
from app.models import FeatureMessageModel
from app.face_tracking import TrackingResult


def build_client() -> TestClient:
    project_root = Path(__file__).resolve().parents[2]
    import os

    os.environ["INFERENCE_JWT_SECRET"] = "hairddae-test-secret-key-2026-inference"
    os.environ["INFERENCE_JWT_ISSUER"] = "hairddae-test"
    os.environ["INFERENCE_STATIC_ROOT"] = str(project_root / "static")
    os.environ["INFERENCE_STATIC_BASE_URL"] = "/static"
    os.environ["INFERENCE_FACE_LANDMARKER_MODEL_PATH"] = str(
        project_root / "Inference" / "models" / "face_landmarker.task"
    )
    os.environ["INFERENCE_HAIR_SEGMENTER_MODEL_PATH"] = str(
        project_root / "Inference" / "models" / "hair_segmenter.tflite"
    )
    os.environ["INFERENCE_HTTP_TEST_ENABLED"] = "true"
    os.environ["INFERENCE_NODE_ID"] = "infer-a-01"
    os.environ.pop("INFERENCE_REDIS_URL", None)
    return TestClient(create_app())


def test_healthz_returns_ok() -> None:
    with build_client() as client:
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_apply_route_removed() -> None:
    with build_client() as client:
        response = client.get("/apply")
        assert response.status_code == 404


def test_http_runtime_frame_returns_render_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    with build_client() as client:
        feature = FeatureMessageModel.model_validate(
            {
                "type": "feature",
                "feature_schema_version": 2,
                "coordinate_space": "pixel_v1",
                "anchor_set": "face_anchor_v1",
                "transform_version": "affine_v1",
                "seq": 1,
                "ts_ms": 1710575105123,
                "apply_session_id": "http-test-session",
                "hair_id": 1,
                "image_size": {"width": 32, "height": 32},
                "pose": {
                    "yaw_float": 0.0,
                    "pitch_float": 0.0,
                    "roll_float": 0.0,
                    "yaw_1deg": 0,
                    "pitch_1deg": 0,
                    "roll_1deg": 0,
                },
                "face_bbox": {"x": 4, "y": 4, "w": 24, "h": 24},
                "anchors": {
                    "forehead_center": {"x": 16.0, "y": 8.0, "confidence": 1.0},
                    "left_temple": {"x": 9.0, "y": 12.0, "confidence": 1.0},
                    "right_temple": {"x": 23.0, "y": 12.0, "confidence": 1.0},
                    "crown": {"x": 16.0, "y": 4.0, "confidence": 1.0},
                    "left_ear_root": {"x": 7.0, "y": 16.0, "confidence": 1.0},
                    "right_ear_root": {"x": 25.0, "y": 16.0, "confidence": 1.0},
                    "left_side": {"x": 8.0, "y": 15.0, "confidence": 1.0},
                    "right_side": {"x": 24.0, "y": 15.0, "confidence": 1.0},
                    "lower_left": {"x": 11.0, "y": 25.0, "confidence": 1.0},
                    "lower_right": {"x": 21.0, "y": 25.0, "confidence": 1.0},
                    "neck_left": {"x": 11.0, "y": 29.0, "confidence": 1.0},
                    "neck_right": {"x": 21.0, "y": 29.0, "confidence": 1.0},
                },
            }
        )
        bundle = AssetBundle(
            asset_id="asset-http-test",
            pose_key="yaw+00_pitch+00_roll+00",
            yaw_1deg=0,
            pitch_1deg=0,
            roll_1deg=0,
            hair_rgba_path=None,
            hair_rgba_url="/static/0001/hair_rgba/test.png",
            hair_mask_url=None,
            anchors_url="/static/0001/anchors/test.json",
            metadata_url="/static/0001/metadata/test.json",
            hair_bbox=None,
            face_mask_url=None,
            protect_face_mask_url=None,
            render_task=None,
            revision="0001:asset-http-test",
            score=3.25,
        )

        monkeypatch.setattr(
            client.app.state.face_tracker,
            "extract_tracking_result_from_rgb",
            lambda *args, **kwargs: TrackingResult(
                feature=feature,
                landmarks_px=np.zeros((500, 2), dtype=np.int32),
            ),
        )
        monkeypatch.setattr(
            client.app.state.catalog,
            "recommend",
            lambda *args, **kwargs: bundle,
        )
        monkeypatch.setattr(
            client.app.state.catalog,
            "bundle_for_asset",
            lambda *args, **kwargs: bundle,
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
