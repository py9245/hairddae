#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import mediapipe as mp
import numpy as np
from PIL import Image
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize a frontal seed image to a centered 512x512 portrait.")
    parser.add_argument("--input-image", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--model-path",
        default="/home/j-j14m101/AI_data_aug/home/ssafy/test_vertical/output_final3/bot/bot/face_landmarker.task",
    )
    parser.add_argument("--size", type=int, default=512)
    return parser.parse_args()


def detect_face_bbox(image_path: Path, model_path: Path) -> tuple[np.ndarray, np.ndarray]:
    options = vision.FaceLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=str(model_path)),
        output_facial_transformation_matrixes=True,
        num_faces=1,
    )
    landmarker = vision.FaceLandmarker.create_from_options(options)
    try:
        image = mp.Image.create_from_file(str(image_path))
        result = landmarker.detect(image)
    finally:
        landmarker.close()

    if not result.face_landmarks or not result.facial_transformation_matrixes:
        raise SystemExit(f"Face not detected: {image_path}")

    pil_image = Image.open(image_path)
    width, height = pil_image.size
    landmarks = np.array(
        [[lm.x * width, lm.y * height] for lm in result.face_landmarks[0]],
        dtype=np.float32,
    )
    return landmarks, result.facial_transformation_matrixes[0][:3, :3]


def build_crop_box(landmarks: np.ndarray, image_size: tuple[int, int]) -> tuple[int, int, int, int]:
    width, height = image_size
    min_xy = landmarks.min(axis=0)
    max_xy = landmarks.max(axis=0)
    face_w = float(max_xy[0] - min_xy[0])
    face_h = float(max_xy[1] - min_xy[1])
    center_x = float((min_xy[0] + max_xy[0]) / 2.0)
    center_y = float((min_xy[1] + max_xy[1]) / 2.0)

    side = int(round(max(face_h * 2.25, face_w * 2.60)))
    side = max(512, min(side, min(width, height)))

    left = int(round(center_x - side / 2.0))
    top = int(round(center_y - side / 2.0))
    left = max(0, min(left, width - side))
    top = max(0, min(top, height - side))
    return left, top, left + side, top + side


def main() -> None:
    args = parse_args()
    input_image = Path(args.input_image)
    output_dir = Path(args.output_dir)
    model_path = Path(args.model_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    rgba_image = Image.open(input_image).convert("RGBA")
    pil_image = Image.new("RGBA", rgba_image.size, (0, 255, 0, 255))
    pil_image.alpha_composite(rgba_image)
    landmarks, rotation = detect_face_bbox(input_image, model_path)
    crop_box = build_crop_box(landmarks, pil_image.size)
    cropped = pil_image.crop(crop_box).resize((args.size, args.size), Image.Resampling.LANCZOS).convert("RGB")

    output_image = output_dir / "seed_512.png"
    cropped.save(output_image)

    import cv2

    pitch, yaw, roll = [float(v) for v in cv2.RQDecomp3x3(rotation)[0]]
    meta = {
        "input_image": str(input_image.resolve()),
        "normalized_image": str(output_image.resolve()),
        "output_size": args.size,
        "crop_box_xyxy": list(map(int, crop_box)),
        "original_size": {"width": pil_image.size[0], "height": pil_image.size[1]},
        "background_fill": "green_rgb_0_255_0",
        "seed_pose": {
            "pitch": pitch,
            "yaw": yaw,
            "roll": roll,
        },
        "seed_pose_1deg": {
            "pitch": int(round(pitch)),
            "yaw": int(round(yaw)),
            "roll": int(round(roll)),
        },
    }
    (output_dir / "seed_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
