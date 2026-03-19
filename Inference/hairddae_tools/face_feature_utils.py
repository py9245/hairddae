from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from local_demo_paths import default_face_landmarker_model_path


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


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def build_landmarker(
    model_path: str | Path | None = None,
    delegate: str = "cpu",
    num_faces: int = 1,
) -> vision.FaceLandmarker:
    resolved_model_path = Path(model_path).expanduser() if model_path else default_face_landmarker_model_path()
    delegate_enum = (
        python.BaseOptions.Delegate.GPU
        if str(delegate).lower() == "gpu"
        else python.BaseOptions.Delegate.CPU
    )
    options = vision.FaceLandmarkerOptions(
        base_options=python.BaseOptions(
            model_asset_path=str(resolved_model_path),
            delegate=delegate_enum,
        ),
        output_facial_transformation_matrixes=True,
        num_faces=max(1, int(num_faces)),
    )
    return vision.FaceLandmarker.create_from_options(options)


def build_mp_image_from_bgr(image_bgr: Any) -> mp.Image:
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    if not rgb.flags["C_CONTIGUOUS"]:
        rgb = rgb.copy()
    return mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)


def point_to_pixel(landmarks: list[Any], idx: int, width: int, height: int) -> tuple[float, float]:
    point = landmarks[idx]
    return (float(point.x) * width, float(point.y) * height)


def averaged_point(points: list[tuple[float, float]]) -> tuple[float, float]:
    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )


def bbox_from_landmarks(landmarks: list[Any], width: int, height: int) -> dict[str, int]:
    xs = [float(point.x) * width for point in landmarks]
    ys = [float(point.y) * height for point in landmarks]
    x0 = int(max(0, round(min(xs))))
    y0 = int(max(0, round(min(ys))))
    x1 = int(min(width, round(max(xs))))
    y1 = int(min(height, round(max(ys))))
    return {"x": x0, "y": y0, "w": max(0, x1 - x0), "h": max(0, y1 - y0)}


def build_anchor_points(landmarks: list[Any], width: int, height: int) -> dict[str, dict[str, float]]:
    forehead_center = averaged_point(
        [
            point_to_pixel(landmarks, FACE_LANDMARK_INDEX["forehead_top"], width, height),
            point_to_pixel(landmarks, FACE_LANDMARK_INDEX["forehead_mid"], width, height),
        ]
    )
    chin_center = point_to_pixel(landmarks, FACE_LANDMARK_INDEX["chin_center"], width, height)
    face_height = max(1.0, chin_center[1] - forehead_center[1])
    lower_left = point_to_pixel(landmarks, FACE_LANDMARK_INDEX["lower_left"], width, height)
    lower_right = point_to_pixel(landmarks, FACE_LANDMARK_INDEX["lower_right"], width, height)

    points = {
        "forehead_center": forehead_center,
        "left_temple": point_to_pixel(landmarks, FACE_LANDMARK_INDEX["left_temple"], width, height),
        "right_temple": point_to_pixel(landmarks, FACE_LANDMARK_INDEX["right_temple"], width, height),
        "crown": (
            clamp(forehead_center[0], 0, width - 1),
            clamp(forehead_center[1] - face_height * 0.38, 0, height - 1),
        ),
        "left_ear_root": point_to_pixel(landmarks, FACE_LANDMARK_INDEX["left_ear_root"], width, height),
        "right_ear_root": point_to_pixel(landmarks, FACE_LANDMARK_INDEX["right_ear_root"], width, height),
        "left_side": point_to_pixel(landmarks, FACE_LANDMARK_INDEX["left_side"], width, height),
        "right_side": point_to_pixel(landmarks, FACE_LANDMARK_INDEX["right_side"], width, height),
        "lower_left": lower_left,
        "lower_right": lower_right,
        "neck_left": (
            clamp(lower_left[0], 0, width - 1),
            clamp(lower_left[1] + face_height * 0.22, 0, height - 1),
        ),
        "neck_right": (
            clamp(lower_right[0], 0, width - 1),
            clamp(lower_right[1] + face_height * 0.22, 0, height - 1),
        ),
    }
    return {
        name: {"x": round(x, 3), "y": round(y, 3), "confidence": 1.0}
        for name, (x, y) in points.items()
    }


def pose_from_matrix(matrix: Any) -> dict[str, float | int]:
    pitch, yaw, roll = [float(v) for v in cv2.RQDecomp3x3(matrix[:3, :3])[0]]
    return {
        "yaw_float": yaw,
        "pitch_float": pitch,
        "roll_float": roll,
        "yaw_1deg": int(round(yaw)),
        "pitch_1deg": int(round(pitch)),
        "roll_1deg": int(round(roll)),
    }


def bbox_center(bbox: dict[str, int]) -> tuple[float, float]:
    return (
        float(bbox["x"]) + float(bbox["w"]) * 0.5,
        float(bbox["y"]) + float(bbox["h"]) * 0.5,
    )


def choose_face_index(
    bboxes: list[dict[str, int]],
    width: int,
    height: int,
    reference_face_bbox: dict[str, Any] | None = None,
) -> int:
    if not bboxes:
        return 0

    if reference_face_bbox:
        ref_center_x, ref_center_y = bbox_center(reference_face_bbox)
        ref_width = max(1.0, float(reference_face_bbox.get("w", 0.0)))
        ref_height = max(1.0, float(reference_face_bbox.get("h", 0.0)))

        scored_candidates: list[tuple[float, float, float, int]] = []
        for index, bbox in enumerate(bboxes):
            center_x, center_y = bbox_center(bbox)
            center_delta_norm = max(
                abs(center_x - ref_center_x) / ref_width,
                abs(center_y - ref_center_y) / ref_height,
            )
            size_delta_norm = max(
                abs(float(bbox["w"]) - ref_width) / ref_width,
                abs(float(bbox["h"]) - ref_height) / ref_height,
            )
            area_ratio = (float(bbox["w"]) * float(bbox["h"])) / max(1.0, float(width * height))
            scored_candidates.append(
                (
                    round(center_delta_norm + 0.65 * size_delta_norm, 6),
                    round(size_delta_norm, 6),
                    -round(area_ratio, 6),
                    index,
                )
            )
        scored_candidates.sort()
        return int(scored_candidates[0][3])

    frame_center_x = float(width) * 0.5
    frame_center_y = float(height) * 0.5
    scored_candidates = []
    for index, bbox in enumerate(bboxes):
        center_x, center_y = bbox_center(bbox)
        area_ratio = (float(bbox["w"]) * float(bbox["h"])) / max(1.0, float(width * height))
        center_bias = max(
            abs(center_x - frame_center_x) / max(1.0, float(width)),
            abs(center_y - frame_center_y) / max(1.0, float(height)),
        )
        scored_candidates.append((-round(area_ratio, 6), round(center_bias, 6), index))
    scored_candidates.sort()
    return int(scored_candidates[0][2])


def extract_feature_from_frame_bgr(
    frame_bgr: Any,
    landmarker: vision.FaceLandmarker,
    file_name: str = "frame.jpg",
    reference_face_bbox: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if frame_bgr is None:
        return {"file": file_name, "ok": False, "reason": "image_read_failed"}

    height, width = frame_bgr.shape[:2]
    result = landmarker.detect(build_mp_image_from_bgr(frame_bgr))
    if not result.face_landmarks or not result.facial_transformation_matrixes:
        return {"file": file_name, "ok": False, "reason": "no_face_or_pose"}

    bboxes = [bbox_from_landmarks(face_landmarks, width, height) for face_landmarks in result.face_landmarks]
    face_index = choose_face_index(bboxes, width, height, reference_face_bbox=reference_face_bbox)
    landmarks = result.face_landmarks[face_index]
    bbox = bbox_from_landmarks(landmarks, width, height)
    anchors = build_anchor_points(landmarks, width, height)
    pose = pose_from_matrix(result.facial_transformation_matrixes[face_index])
    return {
        "file": file_name,
        "ok": True,
        "image_size": {"width": width, "height": height},
        "pose": pose,
        "face_bbox": bbox,
        "face_ratio": round((bbox["w"] * bbox["h"]) / float(width * height), 6),
        "anchors": anchors,
        "face_index": int(face_index),
        "candidate_face_count": len(result.face_landmarks),
    }
