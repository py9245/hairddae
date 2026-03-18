from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from app.auth import TicketClaims
from app.config import Settings
from app.models import FeatureMessageModel


FACE_LANDMARK_INDEX = {
    "forehead_top": 10,
    "forehead_mid": 151,
    "left_temple": 127,
    "right_temple": 356,
    "left_ear_root": 234,
    "right_ear_root": 454,
    "left_side": 93,
    "right_side": 323,
    "lower_left": 172,
    "lower_right": 397,
    "chin_center": 152,
}


@dataclass(frozen=True)
class TrackingResult:
    feature: FeatureMessageModel
    landmarks_px: np.ndarray


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _point_to_pixel(landmarks: list[object], index: int, width: int, height: int) -> tuple[float, float]:
    point = landmarks[index]
    return (float(point.x) * width, float(point.y) * height)


def _landmarks_to_pixel_array(landmarks: list[object], width: int, height: int) -> np.ndarray:
    return np.array(
        [
            [
                int(np.clip(round(float(point.x) * width), 0, max(width - 1, 0))),
                int(np.clip(round(float(point.y) * height), 0, max(height - 1, 0))),
            ]
            for point in landmarks
        ],
        dtype=np.int32,
    )


def _averaged_point(points: list[tuple[float, float]]) -> tuple[float, float]:
    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )


def _bbox_from_landmarks(landmarks: list[object], width: int, height: int) -> dict[str, int]:
    xs = [float(point.x) * width for point in landmarks]
    ys = [float(point.y) * height for point in landmarks]
    x0 = int(max(0, round(min(xs))))
    y0 = int(max(0, round(min(ys))))
    x1 = int(min(width, round(max(xs))))
    y1 = int(min(height, round(max(ys))))
    return {"x": x0, "y": y0, "w": max(0, x1 - x0), "h": max(0, y1 - y0)}


def _anchor_points(landmarks: list[object], width: int, height: int) -> dict[str, dict[str, float]]:
    forehead_center = _averaged_point(
        [
            _point_to_pixel(landmarks, FACE_LANDMARK_INDEX["forehead_top"], width, height),
            _point_to_pixel(landmarks, FACE_LANDMARK_INDEX["forehead_mid"], width, height),
        ]
    )
    chin_center = _point_to_pixel(landmarks, FACE_LANDMARK_INDEX["chin_center"], width, height)
    face_height = max(1.0, chin_center[1] - forehead_center[1])
    lower_left = _point_to_pixel(landmarks, FACE_LANDMARK_INDEX["lower_left"], width, height)
    lower_right = _point_to_pixel(landmarks, FACE_LANDMARK_INDEX["lower_right"], width, height)

    points = {
        "forehead_center": forehead_center,
        "left_temple": _point_to_pixel(landmarks, FACE_LANDMARK_INDEX["left_temple"], width, height),
        "right_temple": _point_to_pixel(landmarks, FACE_LANDMARK_INDEX["right_temple"], width, height),
        "crown": (
            _clamp(forehead_center[0], 0, width - 1),
            _clamp(forehead_center[1] - face_height * 0.38, 0, height - 1),
        ),
        "left_ear_root": _point_to_pixel(landmarks, FACE_LANDMARK_INDEX["left_ear_root"], width, height),
        "right_ear_root": _point_to_pixel(landmarks, FACE_LANDMARK_INDEX["right_ear_root"], width, height),
        "left_side": _point_to_pixel(landmarks, FACE_LANDMARK_INDEX["left_side"], width, height),
        "right_side": _point_to_pixel(landmarks, FACE_LANDMARK_INDEX["right_side"], width, height),
        "lower_left": lower_left,
        "lower_right": lower_right,
        "neck_left": (
            _clamp(lower_left[0], 0, width - 1),
            _clamp(lower_left[1] + face_height * 0.22, 0, height - 1),
        ),
        "neck_right": (
            _clamp(lower_right[0], 0, width - 1),
            _clamp(lower_right[1] + face_height * 0.22, 0, height - 1),
        ),
    }
    return {
        name: {"x": round(x, 3), "y": round(y, 3), "confidence": 1.0}
        for name, (x, y) in points.items()
    }


def _pose_from_result(result: vision.FaceLandmarkerResult) -> dict[str, float | int]:
    pitch, yaw, roll = [
        float(value)
        for value in cv2.RQDecomp3x3(result.facial_transformation_matrixes[0][:3, :3])[0]
    ]
    return {
        "yaw_float": yaw,
        "pitch_float": pitch,
        "roll_float": roll,
        "yaw_1deg": int(round(yaw)),
        "pitch_1deg": int(round(pitch)),
        "roll_1deg": int(round(roll)),
    }


class ServerFaceTracker:
    def __init__(self, model_path: Path) -> None:
        resolved_model_path = model_path.expanduser().resolve()
        options = vision.FaceLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=str(resolved_model_path)),
            output_facial_transformation_matrixes=True,
            num_faces=1,
        )
        self._landmarker = vision.FaceLandmarker.create_from_options(options)
        self._lock = Lock()

    def close(self) -> None:
        self._landmarker.close()

    def extract_tracking_result_from_rgb(
        self,
        frame_rgb: np.ndarray,
        *,
        claims: TicketClaims,
        settings: Settings,
        seq: int,
        ts_ms: int,
    ) -> TrackingResult | None:
        if frame_rgb.ndim != 3 or frame_rgb.shape[2] != 3:
            return None

        if not frame_rgb.flags["C_CONTIGUOUS"]:
            frame_rgb = np.ascontiguousarray(frame_rgb)

        height, width = frame_rgb.shape[:2]
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

        with self._lock:
            result = self._landmarker.detect(mp_image)

        if not result.face_landmarks or not result.facial_transformation_matrixes:
            return None

        landmarks = result.face_landmarks[0]
        feature = FeatureMessageModel.model_validate(
            {
                "type": "feature",
                "feature_schema_version": settings.feature_schema_version,
                "coordinate_space": "pixel_v1",
                "anchor_set": "face_anchor_v1",
                "transform_version": settings.transform_version,
                "seq": seq,
                "ts_ms": ts_ms,
                "apply_session_id": claims.apply_session_id,
                "hair_id": claims.hair_id,
                "image_size": {"width": width, "height": height},
                "pose": _pose_from_result(result),
                "face_bbox": _bbox_from_landmarks(landmarks, width, height),
                "anchors": _anchor_points(landmarks, width, height),
            }
        )
        return TrackingResult(
            feature=feature,
            landmarks_px=_landmarks_to_pixel_array(landmarks, width, height),
        )

    def extract_feature_from_rgb(
        self,
        frame_rgb: np.ndarray,
        *,
        claims: TicketClaims,
        settings: Settings,
        seq: int,
        ts_ms: int,
    ) -> FeatureMessageModel | None:
        tracking_result = self.extract_tracking_result_from_rgb(
            frame_rgb,
            claims=claims,
            settings=settings,
            seq=seq,
            ts_ms=ts_ms,
        )
        if tracking_result is None:
            return None
        return tracking_result.feature
