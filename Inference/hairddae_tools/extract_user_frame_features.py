#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import cv2

from face_feature_utils import extract_feature_from_frame_bgr, build_landmarker
from local_demo_paths import default_face_landmarker_model_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract CPU-friendly user frame features with MediaPipe.")
    parser.add_argument("--pose-bank-dir", required=True, help="Directory containing selected_frames or selected_pose.json")
    parser.add_argument("--output-dir", help="Default: <pose-bank-dir>/user_feature_v0")
    parser.add_argument(
        "--model-path",
        default=str(default_face_landmarker_model_path()),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pose_bank_dir = Path(args.pose_bank_dir).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else pose_bank_dir / "user_feature_v0"
    output_dir.mkdir(parents=True, exist_ok=True)

    selected_frames_dir = pose_bank_dir / "selected_frames"
    images = sorted(selected_frames_dir.glob("*.png"))
    if not images:
        raise FileNotFoundError(f"No PNGs found in {selected_frames_dir}")

    landmarker = build_landmarker(args.model_path)

    rows: list[dict[str, Any]] = []
    try:
        for image_path in images:
            image = cv2.imread(str(image_path))
            row = extract_feature_from_frame_bgr(image, landmarker, file_name=image_path.name)
            row["image_path"] = str(image_path)
            rows.append(row)
    finally:
        landmarker.close()

    summary = {
        "pose_bank_dir": str(pose_bank_dir),
        "output_dir": str(output_dir),
        "total_images": len(images),
        "detected_faces": sum(1 for row in rows if row.get("ok")),
    }

    json_path = output_dir / "user_features.json"
    csv_path = output_dir / "user_features.csv"
    summary_path = output_dir / "summary.json"

    json_path.write_text(json.dumps({"summary": summary, "items": rows}, indent=2, ensure_ascii=True), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "file",
            "ok",
            "yaw_1deg",
            "pitch_1deg",
            "roll_1deg",
            "face_bbox_x",
            "face_bbox_y",
            "face_bbox_w",
            "face_bbox_h",
            "face_ratio",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "file": row["file"],
                    "ok": row.get("ok", False),
                    "yaw_1deg": row.get("pose", {}).get("yaw_1deg"),
                    "pitch_1deg": row.get("pose", {}).get("pitch_1deg"),
                    "roll_1deg": row.get("pose", {}).get("roll_1deg"),
                    "face_bbox_x": row.get("face_bbox", {}).get("x"),
                    "face_bbox_y": row.get("face_bbox", {}).get("y"),
                    "face_bbox_w": row.get("face_bbox", {}).get("w"),
                    "face_bbox_h": row.get("face_bbox", {}).get("h"),
                    "face_ratio": row.get("face_ratio"),
                }
            )
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")


if __name__ == "__main__":
    main()
