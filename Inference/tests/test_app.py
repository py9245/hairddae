from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
import jwt
import numpy as np
from PIL import Image
import pytest
from starlette.websockets import WebSocketDisconnect

from app.catalog import AssetBundle
from app.main import create_app
from app.models import FeatureMessageModel
from app.face_tracking import TrackingResult


def make_ticket(
    *,
    secret: str,
    issuer: str,
    audience: str,
    node_id: str,
    dataset_code: str = "0001",
    hair_id: int = 1,
    apply_session_id: str = "session-123",
    device_id: str = "device-123",
) -> str:
    now = datetime.now(tz=timezone.utc)
    payload = {
        "jti": "ticket-123",
        "sub": "user-123",
        "iss": issuer,
        "aud": audience,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(seconds=30),
        "tokenType": "INFERENCE_CONNECT",
        "single_use": True,
        "sid": apply_session_id,
        "did": device_id,
        "hid": hair_id,
        "node": node_id,
        "ver": 2,
        "dataset_code": dataset_code,
        "representative_asset_id": None,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def build_client() -> TestClient:
    project_root = Path(__file__).resolve().parents[2]
    import os

    os.environ["INFERENCE_JWT_SECRET"] = "hairddae-test-secret-key-2026-inference"
    os.environ["INFERENCE_JWT_ISSUER"] = "hairddae-test"
    os.environ["INFERENCE_STATIC_ROOT"] = str(project_root / "static")
    os.environ["INFERENCE_STATIC_BASE_URL"] = "/static"
    os.environ["INFERENCE_FACE_LANDMARKER_MODEL_PATH"] = str(
        project_root / "FE" / "public" / "models" / "face_landmarker.task"
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


def test_websocket_requires_ticket_protocol() -> None:
    with build_client() as client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/apply", subprotocols=["hairapply.v2"]):
                pass
        assert exc_info.value.code == 4401


def test_websocket_processes_feature_message() -> None:
    with build_client() as client:
        secret = "hairddae-test-secret-key-2026-inference"
        ticket = make_ticket(
            secret=secret,
            issuer="hairddae-test",
            audience="inference",
            node_id="infer-a-01",
        )

        with client.websocket_connect(
            "/apply",
            subprotocols=["hairapply.v2", f"ticket.{ticket}"],
        ) as websocket:
            connected = websocket.receive_json()
            assert connected["type"] == "connected"

            websocket.send_json(
                {
                    "type": "feature",
                    "feature_schema_version": 2,
                    "coordinate_space": "pixel_v1",
                    "anchor_set": "face_anchor_v1",
                    "transform_version": "affine_v1",
                    "seq": 1,
                    "ts_ms": 1710575105123,
                    "apply_session_id": "session-123",
                    "hair_id": 1,
                    "image_size": {"width": 430, "height": 932},
                    "pose": {
                        "yaw_float": 0.0,
                        "pitch_float": 0.0,
                        "roll_float": 0.0,
                        "yaw_1deg": 0,
                        "pitch_1deg": 0,
                        "roll_1deg": 0,
                    },
                    "face_bbox": {"x": 100, "y": 160, "w": 200, "h": 300},
                    "anchors": {
                        "forehead_center": {"x": 214.5, "y": 193.3, "confidence": 1.0},
                        "left_temple": {"x": 162.4, "y": 221.3, "confidence": 1.0},
                        "right_temple": {"x": 267.5, "y": 220.3, "confidence": 1.0},
                        "crown": {"x": 215.5, "y": 128.1, "confidence": 1.0},
                        "left_ear_root": {"x": 145.8, "y": 255.9, "confidence": 1.0},
                        "right_ear_root": {"x": 283.9, "y": 255.1, "confidence": 1.0},
                        "left_side": {"x": 151.7, "y": 244.1, "confidence": 1.0},
                        "right_side": {"x": 277.9, "y": 243.8, "confidence": 1.0},
                        "lower_left": {"x": 173.4, "y": 395.5, "confidence": 1.0},
                        "lower_right": {"x": 246.5, "y": 394.5, "confidence": 1.0},
                        "neck_left": {"x": 173.4, "y": 432.2, "confidence": 1.0},
                        "neck_right": {"x": 246.5, "y": 431.2, "confidence": 1.0},
                    },
                }
            )

            processed = websocket.receive_json()
            assert processed["type"] == "processed"
            assert processed["processed_seq"] == 1
            assert processed["changed"] is True
            assert processed["asset"]["asset_bundle_schema_version"] == 1
            assert processed["asset"]["asset_id"]
            assert processed["asset"]["hair_rgba_url"].startswith("/static/0001/")
            assert processed["asset"]["face_mask_url"].startswith("/static/0001/")
            assert processed["asset"]["protect_face_mask_url"].startswith("/static/0001/")
            assert processed["asset"]["render_task"]["render_task_schema_version"] == 1
            assert processed["asset"]["render_task"]["mode"] == "affine_crop_v1"
            assert processed["asset"]["render_task"]["source_crop"]["w"] > 0
            assert processed["asset"]["render_task"]["destination_roi"]["h"] > 0

            websocket.send_json(
                {
                    "type": "feature",
                    "feature_schema_version": 2,
                    "coordinate_space": "pixel_v1",
                    "anchor_set": "face_anchor_v1",
                    "transform_version": "affine_v1",
                    "seq": 2,
                    "ts_ms": 1710575105189,
                    "apply_session_id": "session-123",
                    "hair_id": 1,
                    "image_size": {"width": 430, "height": 932},
                    "pose": {
                        "yaw_float": 0.0,
                        "pitch_float": 0.0,
                        "roll_float": 0.0,
                        "yaw_1deg": 0,
                        "pitch_1deg": 0,
                        "roll_1deg": 0,
                    },
                    "face_bbox": {"x": 100, "y": 160, "w": 200, "h": 300},
                    "anchors": {
                        "forehead_center": {"x": 216.5, "y": 194.3, "confidence": 1.0},
                        "left_temple": {"x": 163.4, "y": 222.3, "confidence": 1.0},
                        "right_temple": {"x": 268.5, "y": 221.3, "confidence": 1.0},
                        "crown": {"x": 216.5, "y": 129.1, "confidence": 1.0},
                        "left_ear_root": {"x": 146.8, "y": 256.9, "confidence": 1.0},
                        "right_ear_root": {"x": 284.9, "y": 256.1, "confidence": 1.0},
                        "left_side": {"x": 152.7, "y": 245.1, "confidence": 1.0},
                        "right_side": {"x": 278.9, "y": 244.8, "confidence": 1.0},
                        "lower_left": {"x": 174.4, "y": 396.5, "confidence": 1.0},
                        "lower_right": {"x": 247.5, "y": 395.5, "confidence": 1.0},
                        "neck_left": {"x": 174.4, "y": 433.2, "confidence": 1.0},
                        "neck_right": {"x": 247.5, "y": 432.2, "confidence": 1.0},
                    },
                }
            )

            processed_again = websocket.receive_json()
            assert processed_again["type"] == "processed"
            assert processed_again["processed_seq"] == 2
            assert processed_again["asset"]["render_task"]["render_task_schema_version"] == 1


def test_ticket_is_single_use() -> None:
    with build_client() as client:
        secret = "hairddae-test-secret-key-2026-inference"
        ticket = make_ticket(
            secret=secret,
            issuer="hairddae-test",
            audience="inference",
            node_id="infer-a-01",
        )

        with client.websocket_connect(
            "/apply",
            subprotocols=["hairapply.v2", f"ticket.{ticket}"],
        ) as websocket:
            assert websocket.receive_json()["type"] == "connected"

        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(
                "/apply",
                subprotocols=["hairapply.v2", f"ticket.{ticket}"],
            ):
                pass
        assert exc_info.value.code == 4401


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
