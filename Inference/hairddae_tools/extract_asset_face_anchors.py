#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import cv2
from face_feature_utils import (
    bbox_from_landmarks,
    build_anchor_points,
    build_landmarker,
    build_mp_image_from_bgr,
    choose_face_index,
)
from local_demo_paths import default_face_landmarker_model_path, load_manifest_items, read_json, resolve_asset_path, write_json


ANCHOR_COLORS = {
    "forehead_center": (0, 255, 255),
    "left_temple": (255, 0, 0),
    "right_temple": (0, 0, 255),
    "crown": (0, 255, 0),
    "left_ear_root": (255, 100, 0),
    "right_ear_root": (0, 100, 255),
    "left_side": (255, 255, 0),
    "right_side": (0, 255, 255),
    "lower_left": (150, 0, 255),
    "lower_right": (255, 0, 150),
    "neck_left": (100, 255, 100),
    "neck_right": (100, 100, 255),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract initial MediaPipe-based anchors for asset factory views.")
    parser.add_argument("--asset-root", required=True, help="Asset factory root containing manifests/manifest.jsonl")
    parser.add_argument(
        "--model-path",
        default=str(default_face_landmarker_model_path()),
    )
    parser.add_argument("--delegate", choices=["cpu", "gpu"], default="gpu")
    parser.add_argument("--num-faces", type=int, default=3)
    parser.add_argument("--anchor-pipeline-version", default="mediapipe_face_anchor_v1")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit for debugging.")
    parser.add_argument("--skip-current-version", action="store_true")
    return parser.parse_args()


def draw_preview(image: Any, bbox: dict[str, int], anchors: dict[str, dict[str, float]]) -> Any:
    preview = image.copy()
    x0, y0, w, h = bbox["x"], bbox["y"], bbox["w"], bbox["h"]
    cv2.rectangle(preview, (x0, y0), (x0 + w, y0 + h), (0, 255, 0), 2)
    for name, point in anchors.items():
        x = int(round(point["x"]))
        y = int(round(point["y"]))
        color = ANCHOR_COLORS.get(name, (255, 255, 255))
        cv2.circle(preview, (x, y), 5, color, -1)
        cv2.putText(preview, name, (x + 6, y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)
    return preview


def serialize_landmarks(landmarks: list[Any]) -> list[dict[str, float]]:
    return [
        {
            "x": round(float(point.x), 6),
            "y": round(float(point.y), 6),
            "z": round(float(point.z), 6),
        }
        for point in landmarks
    ]


def serialize_matrix(matrix: Any) -> list[list[float]]:
    return [[round(float(value), 6) for value in row] for row in matrix]

def main() -> None:
    args = parse_args()
    asset_root = Path(args.asset_root).resolve()
    rows = load_manifest_items(asset_root)
    if args.skip_current_version:
        filtered_rows: list[dict[str, Any]] = []
        for row in rows:
            metadata_path = resolve_asset_path(asset_root, row["metadata_path"])
            metadata = read_json(metadata_path)
            current_version = metadata.get("lineage", {}).get("anchor_pipeline_version")
            if current_version == args.anchor_pipeline_version:
                continue
            filtered_rows.append(row)
        rows = filtered_rows
    if args.limit > 0:
        rows = rows[: args.limit]

    landmarker = build_landmarker(args.model_path, delegate=args.delegate, num_faces=args.num_faces)

    updated = 0
    failed = 0

    try:
        for row in rows:
            image_path = resolve_asset_path(asset_root, row["image_path"])
            metadata_path = resolve_asset_path(asset_root, row["metadata_path"])
            anchors_path = resolve_asset_path(asset_root, row["anchors_path"])
            qa_preview_path = asset_root / "qa" / "anchor_preview" / f"{row['asset_id']}.png"
            qa_preview_path.parent.mkdir(parents=True, exist_ok=True)
            metadata = read_json(metadata_path)

            image = cv2.imread(str(image_path))
            if image is None:
                failed += 1
                continue

            height, width = image.shape[:2]
            result = landmarker.detect(build_mp_image_from_bgr(image))
            if not result.face_landmarks:
                failed += 1
                continue

            bboxes = [bbox_from_landmarks(face_landmarks, width, height) for face_landmarks in result.face_landmarks]
            reference_face_bbox = metadata.get("face_bbox")
            face_index = choose_face_index(
                bboxes,
                width,
                height,
                reference_face_bbox=reference_face_bbox if isinstance(reference_face_bbox, dict) else None,
            )
            landmarks = result.face_landmarks[face_index]
            transform_matrix = result.facial_transformation_matrixes[face_index] if result.facial_transformation_matrixes else None
            bbox = bbox_from_landmarks(landmarks, width, height)
            anchors = build_anchor_points(landmarks, width, height)
            face_ratio = round((bbox["w"] * bbox["h"]) / float(width * height), 6)

            metadata["face_bbox"] = bbox
            metadata["face_ratio"] = face_ratio
            metadata["image_size"] = {"width": width, "height": height}
            metadata["face_index"] = int(face_index)
            metadata["candidate_face_count"] = len(result.face_landmarks)
            metadata["lineage"]["anchor_pipeline_version"] = args.anchor_pipeline_version
            write_json(metadata_path, metadata)

            anchors_payload = read_json(anchors_path)
            anchors_payload["image_size"] = {"width": width, "height": height}
            anchors_payload["anchors"] = anchors
            anchors_payload["landmarks_normalized"] = serialize_landmarks(landmarks)
            anchors_payload["facial_transformation_matrix"] = serialize_matrix(transform_matrix) if transform_matrix is not None else None
            anchors_payload["face_index"] = int(face_index)
            anchors_payload["candidate_face_count"] = len(result.face_landmarks)
            anchors_payload["anchor_pipeline_version"] = args.anchor_pipeline_version
            write_json(anchors_path, anchors_payload)

            preview = draw_preview(image, bbox, anchors)
            cv2.imwrite(str(qa_preview_path), preview)
            updated += 1
    finally:
        landmarker.close()

    summary_path = asset_root / "manifests" / "anchor_extraction_summary.json"
    write_json(
        summary_path,
        {
            "asset_root": str(asset_root),
            "model_path": args.model_path,
            "delegate": args.delegate,
            "num_faces": args.num_faces,
            "anchor_pipeline_version": args.anchor_pipeline_version,
            "processed_rows": len(rows),
            "updated_rows": updated,
            "failed_rows": failed,
        },
    )


if __name__ == "__main__":
    main()
