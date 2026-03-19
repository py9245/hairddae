#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import cv2
import mediapipe as mp
import numpy as np

from face_feature_utils import (
    bbox_from_landmarks,
    build_anchor_points,
    build_landmarker,
    build_mp_image_from_bgr,
    choose_face_index,
    pose_from_matrix,
)
from local_demo_paths import default_face_landmarker_model_path, write_json
from realtime_face_parsing import RuntimeFaceParsing


POSE_LANDMARK_NAMES = [landmark.name.lower() for landmark in mp.solutions.pose.PoseLandmark]
HAND_LANDMARK_NAMES = [landmark.name.lower() for landmark in mp.solutions.hands.HandLandmark]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract comprehensive frame features for natural hair overlay tuning."
    )
    parser.add_argument("--pose-bank-dir", required=True, help="Pose bank directory containing selected_frames")
    parser.add_argument(
        "--output-dir",
        help="Default: <pose-bank-dir>/comprehensive_feature_v1",
    )
    parser.add_argument(
        "--model-path",
        default=str(default_face_landmarker_model_path()),
        help="Path to MediaPipe face_landmarker.task",
    )
    parser.add_argument(
        "--landmarker-delegate",
        default="gpu",
        choices=["cpu", "gpu"],
        help="Delegate for face landmarker",
    )
    parser.add_argument(
        "--face-parsing-device",
        default=None,
        help="Override device for RuntimeFaceParsing (cpu or cuda)",
    )
    parser.add_argument("--skip-existing", action="store_true", help="Skip frames with existing metadata output")
    parser.add_argument("--limit", type=int, default=0, help="Optional cap on number of frames")
    return parser.parse_args()


def ensure_dirs(output_dir: Path) -> dict[str, Path]:
    paths = {
        "metadata": output_dir / "metadata",
        "parsing": output_dir / "parsing",
        "hair_confidence": output_dir / "confidence" / "hair",
        "pose_segmentation_confidence": output_dir / "confidence" / "pose_segmentation",
        "selfie_segmentation_confidence": output_dir / "confidence" / "selfie_segmentation",
        "combined_person_confidence": output_dir / "confidence" / "combined_person",
        "hair": output_dir / "masks" / "hair",
        "face": output_dir / "masks" / "face",
        "forehead": output_dir / "masks" / "forehead",
        "ear_left": output_dir / "masks" / "ear_left",
        "ear_right": output_dir / "masks" / "ear_right",
        "neck_shoulder": output_dir / "masks" / "neck_shoulder",
        "protect_face": output_dir / "masks" / "protect_face",
        "suppress_prior": output_dir / "masks" / "suppress_prior",
        "alpha": output_dir / "masks" / "alpha",
        "blur": output_dir / "masks" / "blur",
        "head_silhouette": output_dir / "masks" / "head_silhouette",
        "person_pose": output_dir / "masks" / "person_pose",
        "person_selfie": output_dir / "masks" / "person_selfie",
        "person_combined": output_dir / "masks" / "person_combined",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def float_mask_to_u8(mask: np.ndarray) -> np.ndarray:
    return np.clip(np.asarray(mask, dtype=np.float32), 0.0, 1.0) * 255.0


def save_mask(path: Path, mask: np.ndarray) -> None:
    array = np.asarray(mask)
    if array.dtype.kind == "f":
        array = float_mask_to_u8(array)
    array = np.clip(array, 0, 255).astype(np.uint8)
    cv2.imwrite(str(path), array)


def serialize_face_landmarks(landmarks: list[Any], width: int, height: int) -> dict[str, Any]:
    normalized = []
    pixels = []
    for landmark in landmarks:
        normalized.append(
            {
                "x": round(float(landmark.x), 6),
                "y": round(float(landmark.y), 6),
                "z": round(float(landmark.z), 6),
            }
        )
        pixels.append(
            {
                "x": round(float(landmark.x) * width, 3),
                "y": round(float(landmark.y) * height, 3),
                "z": round(float(landmark.z), 6),
            }
        )
    return {"normalized": normalized, "pixels": pixels}


def serialize_matrix(matrix: Any) -> list[list[float]]:
    return [
        [round(float(value), 6) for value in row]
        for row in np.asarray(matrix, dtype=np.float32).tolist()
    ]


def mask_ratio(mask: np.ndarray | None) -> float:
    if mask is None or mask.size == 0:
        return 0.0
    array = np.asarray(mask)
    if array.dtype.kind == "f":
        return float(np.mean(np.clip(array.astype(np.float32), 0.0, 1.0)))
    return float(np.count_nonzero(array)) / float(array.shape[0] * array.shape[1])


def mask_bbox(mask: np.ndarray | None) -> dict[str, int] | None:
    if mask is None or mask.size == 0:
        return None
    ys, xs = np.where(np.asarray(mask) > 0)
    if xs.size == 0 or ys.size == 0:
        return None
    x0 = int(xs.min())
    y0 = int(ys.min())
    x1 = int(xs.max()) + 1
    y1 = int(ys.max()) + 1
    return {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}


def contour_stats(mask: np.ndarray | None) -> dict[str, Any]:
    if mask is None or mask.size == 0:
        return {"count": 0, "largest_area": 0.0, "largest_perimeter": 0.0}
    array = np.asarray(mask)
    if array.dtype.kind == "f":
        array = (np.asarray(array, dtype=np.float32) > 0.5).astype(np.uint8) * 255
    contours, _ = cv2.findContours(array.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return {"count": 0, "largest_area": 0.0, "largest_perimeter": 0.0}
    areas = [cv2.contourArea(contour) for contour in contours]
    perimeters = [cv2.arcLength(contour, True) for contour in contours]
    return {
        "count": len(contours),
        "largest_area": round(float(max(areas)), 3),
        "largest_perimeter": round(float(max(perimeters)), 3),
    }


def ring_mask(mask: np.ndarray | None, inner_radius: int = 5, outer_radius: int = 13) -> np.ndarray | None:
    if mask is None or mask.size == 0:
        return None
    array = (np.asarray(mask) > 0).astype(np.uint8) * 255
    if np.count_nonzero(array) == 0:
        return None
    outer = cv2.dilate(array, np.ones((outer_radius, outer_radius), np.uint8), iterations=1)
    inner = cv2.dilate(array, np.ones((inner_radius, inner_radius), np.uint8), iterations=1)
    ring = cv2.bitwise_and(outer, cv2.bitwise_not(inner))
    if np.count_nonzero(ring) == 0:
        return None
    return ring


def color_stats(image_bgr: np.ndarray, mask: np.ndarray | None) -> dict[str, Any] | None:
    if mask is None or mask.size == 0:
        return None
    active = np.asarray(mask) > 0
    if not np.any(active):
        return None
    pixels = image_bgr[active]
    if pixels.size == 0:
        return None
    mean = np.mean(pixels, axis=0)
    median = np.median(pixels, axis=0)
    return {
        "mean_bgr": [round(float(value), 3) for value in mean.tolist()],
        "median_bgr": [round(float(value), 3) for value in median.tolist()],
    }


def image_quality_stats(image_bgr: np.ndarray, roi_bbox: dict[str, Any] | None) -> dict[str, Any]:
    if roi_bbox:
        x0 = max(0, int(roi_bbox.get("x", 0)))
        y0 = max(0, int(roi_bbox.get("y", 0)))
        x1 = min(image_bgr.shape[1], x0 + max(1, int(roi_bbox.get("w", 0))))
        y1 = min(image_bgr.shape[0], y0 + max(1, int(roi_bbox.get("h", 0))))
        roi = image_bgr[y0:y1, x0:x1]
    else:
        roi = image_bgr
    if roi.size == 0:
        roi = image_bgr
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    return {
        "brightness_mean": round(float(np.mean(gray)), 4),
        "brightness_std": round(float(np.std(gray)), 4),
        "laplacian_variance": round(float(cv2.Laplacian(gray, cv2.CV_32F).var()), 4),
    }


def serialize_pose_landmarks(landmarks: list[Any], width: int, height: int) -> list[dict[str, Any]]:
    rows = []
    for name, landmark in zip(POSE_LANDMARK_NAMES, landmarks):
        rows.append(
            {
                "name": name,
                "x": round(float(landmark.x), 6),
                "y": round(float(landmark.y), 6),
                "z": round(float(landmark.z), 6),
                "visibility": round(float(getattr(landmark, "visibility", 0.0)), 6),
                "presence": round(float(getattr(landmark, "presence", 0.0)), 6),
                "x_px": round(float(landmark.x) * width, 3),
                "y_px": round(float(landmark.y) * height, 3),
            }
        )
    return rows


def serialize_pose_world_landmarks(landmarks: list[Any]) -> list[dict[str, Any]]:
    rows = []
    for name, landmark in zip(POSE_LANDMARK_NAMES, landmarks):
        rows.append(
            {
                "name": name,
                "x": round(float(landmark.x), 6),
                "y": round(float(landmark.y), 6),
                "z": round(float(landmark.z), 6),
                "visibility": round(float(getattr(landmark, "visibility", 0.0)), 6),
            }
        )
    return rows


def serialize_hand_landmarks(landmarks: list[Any], width: int, height: int) -> list[dict[str, Any]]:
    rows = []
    for name, landmark in zip(HAND_LANDMARK_NAMES, landmarks):
        rows.append(
            {
                "name": name,
                "x": round(float(landmark.x), 6),
                "y": round(float(landmark.y), 6),
                "z": round(float(landmark.z), 6),
                "x_px": round(float(landmark.x) * width, 3),
                "y_px": round(float(landmark.y) * height, 3),
            }
        )
    return rows


def landmark_by_name(rows: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for row in rows:
        if row["name"] == name:
            return row
    return None


def shoulder_metrics(pose_landmarks: list[dict[str, Any]], world_landmarks: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    left_shoulder = landmark_by_name(pose_landmarks, "left_shoulder")
    right_shoulder = landmark_by_name(pose_landmarks, "right_shoulder")
    left_hip = landmark_by_name(pose_landmarks, "left_hip")
    right_hip = landmark_by_name(pose_landmarks, "right_hip")
    if left_shoulder is None or right_shoulder is None:
        return None

    dx = float(right_shoulder["x_px"]) - float(left_shoulder["x_px"])
    dy = float(right_shoulder["y_px"]) - float(left_shoulder["y_px"])
    metrics: dict[str, Any] = {
        "left_shoulder": left_shoulder,
        "right_shoulder": right_shoulder,
        "shoulder_width_px": round(float(np.hypot(dx, dy)), 3),
        "shoulder_tilt_deg": round(float(np.degrees(np.arctan2(dy, dx))), 3),
        "shoulder_center_px": {
            "x": round((float(left_shoulder["x_px"]) + float(right_shoulder["x_px"])) * 0.5, 3),
            "y": round((float(left_shoulder["y_px"]) + float(right_shoulder["y_px"])) * 0.5, 3),
        },
    }
    if left_hip is not None and right_hip is not None:
        x0 = min(float(left_shoulder["x_px"]), float(right_shoulder["x_px"]), float(left_hip["x_px"]), float(right_hip["x_px"]))
        y0 = min(float(left_shoulder["y_px"]), float(right_shoulder["y_px"]), float(left_hip["y_px"]), float(right_hip["y_px"]))
        x1 = max(float(left_shoulder["x_px"]), float(right_shoulder["x_px"]), float(left_hip["x_px"]), float(right_hip["x_px"]))
        y1 = max(float(left_shoulder["y_px"]), float(right_shoulder["y_px"]), float(left_hip["y_px"]), float(right_hip["y_px"]))
        metrics["torso_bbox"] = {
            "x": int(round(x0)),
            "y": int(round(y0)),
            "w": int(round(max(0.0, x1 - x0))),
            "h": int(round(max(0.0, y1 - y0))),
        }
    if world_landmarks:
        left_world = landmark_by_name(world_landmarks, "left_shoulder")
        right_world = landmark_by_name(world_landmarks, "right_shoulder")
        if left_world is not None and right_world is not None:
            metrics["shoulder_depth_delta"] = round(float(right_world["z"]) - float(left_world["z"]), 6)
    return metrics


def head_silhouette_mask(
    hair_mask: np.ndarray | None,
    forehead_mask: np.ndarray | None,
    ear_left_mask: np.ndarray | None,
    ear_right_mask: np.ndarray | None,
    face_mask: np.ndarray | None,
) -> np.ndarray | None:
    layers = [layer for layer in (hair_mask, forehead_mask, ear_left_mask, ear_right_mask, face_mask) if layer is not None]
    if not layers:
        return None
    combined = np.zeros_like(np.asarray(layers[0]), dtype=np.uint8)
    for layer in layers:
        combined = np.maximum(combined, np.asarray(layer, dtype=np.uint8))
    return cv2.GaussianBlur(cv2.dilate(combined, np.ones((7, 7), np.uint8), iterations=1), (0, 0), sigmaX=3.0, sigmaY=3.0)


def make_binary_mask(confidence: np.ndarray | None, threshold: float = 0.5) -> np.ndarray | None:
    if confidence is None:
        return None
    return (np.asarray(confidence, dtype=np.float32) >= threshold).astype(np.uint8) * 255


def relative_output_path(base_dir: Path, path: Path) -> str:
    return str(path.relative_to(base_dir))


def main() -> None:
    args = parse_args()
    pose_bank_dir = Path(args.pose_bank_dir).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else pose_bank_dir / "comprehensive_feature_v1"
    paths = ensure_dirs(output_dir)

    selected_frames_dir = pose_bank_dir / "selected_frames"
    images = sorted(selected_frames_dir.glob("*.png"))
    if args.limit > 0:
        images = images[: args.limit]
    if not images:
        raise FileNotFoundError(f"No PNGs found in {selected_frames_dir}")

    landmarker = build_landmarker(args.model_path, delegate=args.landmarker_delegate, num_faces=3)
    runtime_parser = RuntimeFaceParsing(device=args.face_parsing_device)
    pose_model = mp.solutions.pose.Pose(static_image_mode=True, model_complexity=1, enable_segmentation=True)
    selfie_model = mp.solutions.selfie_segmentation.SelfieSegmentation(model_selection=1)
    hands_model = mp.solutions.hands.Hands(static_image_mode=True, max_num_hands=2)

    index_rows: list[dict[str, Any]] = []
    stats = {
        "total_images": len(images),
        "face_feature_ok": 0,
        "face_parsing_ok": 0,
        "pose_model_ok": 0,
        "selfie_segmentation_ok": 0,
        "hand_model_ok": 0,
        "skipped_existing": 0,
    }
    reference_face_bbox: dict[str, Any] | None = None

    try:
        for index, image_path in enumerate(images, start=1):
            base_name = image_path.stem
            metadata_path = paths["metadata"] / f"{base_name}.json"
            if args.skip_existing and metadata_path.is_file():
                payload = json.loads(metadata_path.read_text(encoding="utf-8"))
                stats["skipped_existing"] += 1
                if payload.get("face", {}).get("ok") and payload["face"].get("face_bbox"):
                    reference_face_bbox = payload["face"]["face_bbox"]
                index_rows.append(
                    {
                        "file": payload.get("file", image_path.name),
                        "image_path": payload.get("image_path", str(image_path)),
                        "metadata_path": relative_output_path(output_dir, metadata_path),
                        "face_ok": bool(payload.get("face", {}).get("ok")),
                        "parsing_ok": bool(payload.get("parsing", {}).get("ok")),
                        "body_pose_ok": bool(payload.get("body_pose", {}).get("ok")),
                        "selfie_ok": bool(payload.get("person_segmentation", {}).get("selfie", {}).get("ok")),
                    }
                )
                continue

            frame_bgr = cv2.imread(str(image_path))
            if frame_bgr is None:
                row = {
                    "file": image_path.name,
                    "image_path": str(image_path),
                    "ok": False,
                    "reason": "image_read_failed",
                }
                write_json(metadata_path, row)
                index_rows.append(
                    {
                        "file": image_path.name,
                        "image_path": str(image_path),
                        "metadata_path": relative_output_path(output_dir, metadata_path),
                        "face_ok": False,
                        "parsing_ok": False,
                        "body_pose_ok": False,
                        "selfie_ok": False,
                    }
                )
                continue

            height, width = frame_bgr.shape[:2]
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            mp_image = build_mp_image_from_bgr(frame_bgr)
            face_result = landmarker.detect(mp_image)
            face_payload: dict[str, Any] = {
                "ok": False,
                "candidate_face_count": 0,
            }
            user_row: dict[str, Any] | None = None
            if face_result.face_landmarks and face_result.facial_transformation_matrixes:
                bboxes = [bbox_from_landmarks(face_landmarks, width, height) for face_landmarks in face_result.face_landmarks]
                face_index = choose_face_index(
                    bboxes,
                    width,
                    height,
                    reference_face_bbox=reference_face_bbox,
                )
                selected_landmarks = face_result.face_landmarks[face_index]
                face_bbox = bbox_from_landmarks(selected_landmarks, width, height)
                reference_face_bbox = face_bbox
                anchors = build_anchor_points(selected_landmarks, width, height)
                pose = pose_from_matrix(face_result.facial_transformation_matrixes[face_index])
                user_row = {
                    "file": image_path.name,
                    "ok": True,
                    "image_size": {"width": width, "height": height},
                    "pose": pose,
                    "face_bbox": face_bbox,
                    "face_ratio": round((face_bbox["w"] * face_bbox["h"]) / float(width * height), 6),
                    "anchors": anchors,
                    "face_index": int(face_index),
                    "candidate_face_count": len(face_result.face_landmarks),
                }
                face_payload = {
                    **user_row,
                    "face_landmarks": serialize_face_landmarks(selected_landmarks, width, height),
                    "facial_transformation_matrix": serialize_matrix(face_result.facial_transformation_matrixes[face_index]),
                }
                stats["face_feature_ok"] += 1

            parsing_payload: dict[str, Any] = {"ok": False}
            if user_row is not None:
                parsing_bundle = runtime_parser.parse_frame(frame_bgr, user_row)
                if parsing_bundle is not None:
                    stats["face_parsing_ok"] += 1
                    parsing_paths = {}
                    for key, dir_key in [
                        ("parsing", "parsing"),
                        ("hair_confidence", "hair_confidence"),
                        ("hair_mask", "hair"),
                        ("face_mask", "face"),
                        ("forehead_mask", "forehead"),
                        ("ear_left_mask", "ear_left"),
                        ("ear_right_mask", "ear_right"),
                        ("neck_shoulder_mask", "neck_shoulder"),
                        ("protect_face_mask", "protect_face"),
                        ("suppress_prior_mask", "suppress_prior"),
                        ("alpha_mask", "alpha"),
                        ("blur_mask", "blur"),
                    ]:
                        output_path = paths[dir_key] / f"{base_name}.png"
                        save_mask(output_path, parsing_bundle[key])
                        parsing_paths[key] = relative_output_path(output_dir, output_path)

                    head_mask = head_silhouette_mask(
                        parsing_bundle.get("hair_mask"),
                        parsing_bundle.get("forehead_mask"),
                        parsing_bundle.get("ear_left_mask"),
                        parsing_bundle.get("ear_right_mask"),
                        parsing_bundle.get("face_mask"),
                    )
                    head_mask_path = None
                    if head_mask is not None:
                        output_path = paths["head_silhouette"] / f"{base_name}.png"
                        save_mask(output_path, head_mask)
                        head_mask_path = relative_output_path(output_dir, output_path)

                    parsing_payload = {
                        "ok": True,
                        "roi": parsing_bundle.get("roi"),
                        "metrics": parsing_bundle.get("metrics", {}),
                        "mask_paths": parsing_paths,
                        "head_silhouette_mask_path": head_mask_path,
                        "mask_bboxes": {
                            "hair": mask_bbox(parsing_bundle.get("hair_mask")),
                            "face": mask_bbox(parsing_bundle.get("face_mask")),
                            "forehead": mask_bbox(parsing_bundle.get("forehead_mask")),
                            "ear_left": mask_bbox(parsing_bundle.get("ear_left_mask")),
                            "ear_right": mask_bbox(parsing_bundle.get("ear_right_mask")),
                            "neck_shoulder": mask_bbox(parsing_bundle.get("neck_shoulder_mask")),
                            "blur": mask_bbox(parsing_bundle.get("blur_mask")),
                            "head_silhouette": mask_bbox(head_mask),
                        },
                        "contours": {
                            "hair": contour_stats(parsing_bundle.get("hair_mask")),
                            "blur": contour_stats(parsing_bundle.get("blur_mask")),
                            "head_silhouette": contour_stats(head_mask),
                        },
                    }
                else:
                    parsing_bundle = None
            else:
                parsing_bundle = None

            pose_result = pose_model.process(rgb)
            body_pose_payload: dict[str, Any] = {"ok": False}
            pose_seg_conf = None
            pose_seg_mask = None
            if pose_result.pose_landmarks:
                stats["pose_model_ok"] += 1
                pose_landmarks = serialize_pose_landmarks(pose_result.pose_landmarks.landmark, width, height)
                pose_world_landmarks = (
                    serialize_pose_world_landmarks(pose_result.pose_world_landmarks.landmark)
                    if pose_result.pose_world_landmarks
                    else None
                )
                pose_seg_conf = (
                    np.asarray(pose_result.segmentation_mask, dtype=np.float32)
                    if pose_result.segmentation_mask is not None
                    else None
                )
                pose_seg_mask = make_binary_mask(pose_seg_conf, threshold=0.35)
                pose_seg_conf_path = None
                pose_seg_mask_path = None
                if pose_seg_conf is not None:
                    pose_seg_conf_path = relative_output_path(output_dir, paths["pose_segmentation_confidence"] / f"{base_name}.png")
                    save_mask(paths["pose_segmentation_confidence"] / f"{base_name}.png", pose_seg_conf)
                if pose_seg_mask is not None:
                    pose_seg_mask_path = relative_output_path(output_dir, paths["person_pose"] / f"{base_name}.png")
                    save_mask(paths["person_pose"] / f"{base_name}.png", pose_seg_mask)
                body_pose_payload = {
                    "ok": True,
                    "landmarks": pose_landmarks,
                    "world_landmarks": pose_world_landmarks,
                    "shoulder_metrics": shoulder_metrics(pose_landmarks, pose_world_landmarks),
                    "segmentation_confidence_path": pose_seg_conf_path,
                    "segmentation_mask_path": pose_seg_mask_path,
                    "segmentation_area_ratio": round(mask_ratio(pose_seg_conf), 6) if pose_seg_conf is not None else 0.0,
                    "segmentation_bbox": mask_bbox(pose_seg_mask),
                }

            selfie_result = selfie_model.process(rgb)
            selfie_payload: dict[str, Any] = {"ok": False}
            if selfie_result.segmentation_mask is not None:
                stats["selfie_segmentation_ok"] += 1
                selfie_conf = np.asarray(selfie_result.segmentation_mask, dtype=np.float32)
                selfie_mask = make_binary_mask(selfie_conf, threshold=0.35)
                save_mask(paths["selfie_segmentation_confidence"] / f"{base_name}.png", selfie_conf)
                save_mask(paths["person_selfie"] / f"{base_name}.png", selfie_mask)
                selfie_payload = {
                    "ok": True,
                    "segmentation_confidence_path": relative_output_path(output_dir, paths["selfie_segmentation_confidence"] / f"{base_name}.png"),
                    "segmentation_mask_path": relative_output_path(output_dir, paths["person_selfie"] / f"{base_name}.png"),
                    "segmentation_area_ratio": round(mask_ratio(selfie_conf), 6),
                    "segmentation_bbox": mask_bbox(selfie_mask),
                }
            else:
                selfie_conf = None
                selfie_mask = None

            combined_person_payload: dict[str, Any] = {"ok": False}
            combined_conf = None
            combined_mask = None
            if pose_result.pose_landmarks or selfie_result.segmentation_mask is not None:
                layers = [layer for layer in (pose_seg_conf, selfie_conf) if layer is not None]
                if layers:
                    combined_conf = np.maximum.reduce(layers).astype(np.float32)
                    combined_mask = make_binary_mask(combined_conf, threshold=0.35)
                    save_mask(paths["combined_person_confidence"] / f"{base_name}.png", combined_conf)
                    save_mask(paths["person_combined"] / f"{base_name}.png", combined_mask)
                    combined_person_payload = {
                        "ok": True,
                        "segmentation_confidence_path": relative_output_path(output_dir, paths["combined_person_confidence"] / f"{base_name}.png"),
                        "segmentation_mask_path": relative_output_path(output_dir, paths["person_combined"] / f"{base_name}.png"),
                        "segmentation_area_ratio": round(mask_ratio(combined_conf), 6),
                        "segmentation_bbox": mask_bbox(combined_mask),
                        "contours": contour_stats(combined_mask),
                    }

            hand_result = hands_model.process(rgb)
            hands_payload: dict[str, Any] = {"ok": False, "count": 0}
            if hand_result.multi_hand_landmarks:
                stats["hand_model_ok"] += 1
                hands_rows: list[dict[str, Any]] = []
                handedness_rows = hand_result.multi_handedness or []
                for hand_index, hand_landmarks in enumerate(hand_result.multi_hand_landmarks):
                    serialized_landmarks = serialize_hand_landmarks(hand_landmarks.landmark, width, height)
                    xs = [float(row["x_px"]) for row in serialized_landmarks]
                    ys = [float(row["y_px"]) for row in serialized_landmarks]
                    handedness_label = None
                    handedness_score = None
                    if hand_index < len(handedness_rows):
                        classification = handedness_rows[hand_index].classification[0]
                        handedness_label = str(classification.label).lower()
                        handedness_score = round(float(classification.score), 6)
                    hands_rows.append(
                        {
                            "index": hand_index,
                            "handedness": handedness_label,
                            "handedness_score": handedness_score,
                            "bbox": {
                                "x": int(round(min(xs))),
                                "y": int(round(min(ys))),
                                "w": int(round(max(xs) - min(xs))),
                                "h": int(round(max(ys) - min(ys))),
                            },
                            "landmarks": serialized_landmarks,
                        }
                    )
                hands_payload = {"ok": True, "count": len(hands_rows), "hands": hands_rows}

            hair_ring = ring_mask(parsing_bundle.get("hair_mask") if parsing_bundle else None)
            derived_payload = {
                "quality": image_quality_stats(frame_bgr, face_payload.get("face_bbox") if face_payload.get("ok") else None),
                "frame_color": {
                    "mean_bgr": [round(float(value), 3) for value in np.mean(frame_bgr.reshape(-1, 3), axis=0).tolist()],
                    "median_bgr": [round(float(value), 3) for value in np.median(frame_bgr.reshape(-1, 3), axis=0).tolist()],
                },
                "hair_ring_color": color_stats(frame_bgr, hair_ring),
                "mask_overlap": {
                    "hair_with_person_ratio": round(
                        float(
                            np.count_nonzero(
                                (np.asarray(parsing_bundle.get("hair_mask")) > 0)
                                & (np.asarray(combined_mask) > 0)
                            )
                        )
                        / max(1, int(np.count_nonzero(np.asarray(parsing_bundle.get("hair_mask")) > 0)))
                        if parsing_bundle is not None and combined_person_payload.get("ok")
                        else 0.0,
                        6,
                    ),
                },
            }

            row = {
                "file": image_path.name,
                "image_path": str(image_path),
                "models": {
                    "face_landmarker": "mediapipe_face_landmarker",
                    "face_parsing": "bisenet_face_parsing",
                    "body_pose": "mediapipe_pose",
                    "person_segmentation": "mediapipe_selfie_segmentation",
                    "hands": "mediapipe_hands",
                    "unavailable_models": ["depth_estimation", "high_quality_matting"],
                },
                "face": face_payload,
                "parsing": parsing_payload,
                "body_pose": body_pose_payload,
                "hands": hands_payload,
                "person_segmentation": {
                    "selfie": selfie_payload,
                    "combined": combined_person_payload,
                },
                "derived": derived_payload,
            }
            write_json(metadata_path, row)
            index_rows.append(
                {
                    "file": image_path.name,
                    "image_path": str(image_path),
                    "metadata_path": relative_output_path(output_dir, metadata_path),
                    "face_ok": bool(face_payload.get("ok")),
                    "parsing_ok": bool(parsing_payload.get("ok")),
                    "body_pose_ok": bool(body_pose_payload.get("ok")),
                    "selfie_ok": bool(selfie_payload.get("ok")),
                }
            )

            if index % 100 == 0 or index == len(images):
                print(
                    json.dumps(
                        {
                            "processed": index,
                            "total": len(images),
                            "face_feature_ok": stats["face_feature_ok"],
                        "face_parsing_ok": stats["face_parsing_ok"],
                        "pose_model_ok": stats["pose_model_ok"],
                        "selfie_segmentation_ok": stats["selfie_segmentation_ok"],
                        "hand_model_ok": stats["hand_model_ok"],
                    },
                    ensure_ascii=True,
                ),
                    flush=True,
                )
    finally:
        landmarker.close()
        pose_model.close()
        selfie_model.close()
        hands_model.close()

    summary = {
        "pose_bank_dir": str(pose_bank_dir),
        "output_dir": str(output_dir),
        "total_items": len(index_rows),
        **stats,
    }
    write_json(output_dir / "summary.json", summary)
    write_json(output_dir / "manifest.json", {"summary": summary, "items": index_rows})
    (output_dir / "manifest.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=True) for item in index_rows) + ("\n" if index_rows else ""),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
