#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Estimate face pose for all images in a bank.")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument(
        "--model-path",
        default="/home/j-j14m101/AI_data_aug/home/ssafy/test_vertical/output_final3/bot/bot/face_landmarker.task",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_json = Path(args.output_json)
    images = sorted([p for p in input_dir.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}])

    options = vision.FaceLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=args.model_path),
        output_facial_transformation_matrixes=True,
        num_faces=1,
    )
    landmarker = vision.FaceLandmarker.create_from_options(options)

    rows = []
    try:
        for image_path in images:
            result = landmarker.detect(mp.Image.create_from_file(str(image_path)))
            if not result.face_landmarks or not result.facial_transformation_matrixes:
                rows.append({"file": image_path.name, "ok": False, "reason": "no_face_or_pose"})
                continue
            pitch, yaw, roll = [float(v) for v in cv2.RQDecomp3x3(result.facial_transformation_matrixes[0][:3, :3])[0]]
            rows.append(
                {
                    "file": image_path.name,
                    "ok": True,
                    "angles": {"pitch": pitch, "yaw": yaw, "roll": roll},
                    "angles_1deg": {
                        "pitch": int(round(pitch)),
                        "yaw": int(round(yaw)),
                        "roll": int(round(roll)),
                    },
                }
            )
    finally:
        landmarker.close()

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(
            {
                "summary": {
                    "total_images": len(images),
                    "detected_faces": sum(1 for row in rows if row.get("ok")),
                },
                "items": rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
