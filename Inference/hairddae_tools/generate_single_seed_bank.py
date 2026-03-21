#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


FACE_OVAL_INDICES = [
    10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
    397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
    172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109,
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a coarse/dense pose bank from a single 512 seed image.")
    parser.add_argument("--seed-image", required=True)
    parser.add_argument("--targets-json", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--model-path",
        default="/home/j-j14m101/AI_data_aug/home/ssafy/test_vertical/output_final3/bot/bot/face_landmarker.task",
    )
    return parser.parse_args()


def get_landmarker(model_path: Path) -> vision.FaceLandmarker:
    options = vision.FaceLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=str(model_path)),
        output_facial_transformation_matrixes=True,
        num_faces=1,
    )
    return vision.FaceLandmarker.create_from_options(options)


def detect_landmarks(landmarker: vision.FaceLandmarker, image_path: Path) -> np.ndarray:
    image = mp.Image.create_from_file(str(image_path))
    result = landmarker.detect(image)
    if not result.face_landmarks:
        raise RuntimeError(f"Face not detected: {image_path}")
    lms = result.face_landmarks[0]
    return np.array([[lm.x, lm.y, lm.z] for lm in lms], dtype=np.float32)


def add_border_points(points: np.ndarray) -> np.ndarray:
    border = np.array(
        [
            [0.0, 0.0, 0.0],
            [0.5, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [1.0, 0.5, 0.0],
            [1.0, 1.0, 0.0],
            [0.5, 1.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.5, 0.0],
        ],
        dtype=np.float32,
    )
    return np.vstack([points, border])


def rotate_landmarks(points: np.ndarray, delta_pitch: float, delta_yaw: float, delta_roll: float) -> np.ndarray:
    pts = points.copy()
    center = pts[:, :2].mean(axis=0)
    centered = pts.copy()
    centered[:, 0] -= center[0]
    centered[:, 1] -= center[1]

    yaw = math.radians(delta_yaw * 0.85)
    pitch = math.radians(delta_pitch * 0.22)
    roll = math.radians(delta_roll * 0.95)

    x = centered[:, 0]
    y = centered[:, 1]
    z = centered[:, 2] * 4.5

    x1 = x * math.cos(yaw) + z * math.sin(yaw)
    z1 = -x * math.sin(yaw) + z * math.cos(yaw)
    y2 = y * math.cos(pitch) - z1 * math.sin(pitch)

    xr = x1 * math.cos(roll) - y2 * math.sin(roll)
    yr = x1 * math.sin(roll) + y2 * math.cos(roll)

    pts[:, 0] = xr + center[0]
    pts[:, 1] = yr + center[1]
    pts[:, 2] = z1
    return pts


def landmarks_to_pixels(points: np.ndarray, width: int, height: int) -> np.ndarray:
    out = points.copy()
    out[:, 0] *= width
    out[:, 1] *= height
    out[:, 0] = np.clip(out[:, 0], 0, width - 1)
    out[:, 1] = np.clip(out[:, 1], 0, height - 1)
    return out[:, :2]


def build_triangles(src_pts: np.ndarray, width: int, height: int) -> list[tuple[int, int, int]]:
    subdiv = cv2.Subdiv2D((0, 0, width, height))
    for p in src_pts:
        subdiv.insert((float(p[0]), float(p[1])))

    triangle_list = subdiv.getTriangleList()
    point_map = {(int(round(p[0])), int(round(p[1]))): idx for idx, p in enumerate(src_pts)}
    triangles: list[tuple[int, int, int]] = []
    seen = set()
    for tri in triangle_list:
        coords = [
            (int(round(tri[0])), int(round(tri[1]))),
            (int(round(tri[2])), int(round(tri[3]))),
            (int(round(tri[4])), int(round(tri[5]))),
        ]
        try:
            idxs = tuple(point_map[c] for c in coords)
        except KeyError:
            continue
        if len(set(idxs)) != 3 or idxs in seen:
            continue
        seen.add(idxs)
        triangles.append(idxs)
    return triangles


def warp_triangle(src: np.ndarray, dst: np.ndarray, src_tri: np.ndarray, dst_tri: np.ndarray) -> None:
    src_rect = cv2.boundingRect(src_tri.astype(np.float32))
    dst_rect = cv2.boundingRect(dst_tri.astype(np.float32))

    src_tri_rect = np.array(
        [[src_tri[i][0] - src_rect[0], src_tri[i][1] - src_rect[1]] for i in range(3)],
        dtype=np.float32,
    )
    dst_tri_rect = np.array(
        [[dst_tri[i][0] - dst_rect[0], dst_tri[i][1] - dst_rect[1]] for i in range(3)],
        dtype=np.float32,
    )

    src_crop = src[src_rect[1] : src_rect[1] + src_rect[3], src_rect[0] : src_rect[0] + src_rect[2]]
    warp_mat = cv2.getAffineTransform(src_tri_rect, dst_tri_rect)
    warped = cv2.warpAffine(
        src_crop,
        warp_mat,
        (dst_rect[2], dst_rect[3]),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT_101,
    )

    mask = np.zeros((dst_rect[3], dst_rect[2], 3), dtype=np.float32)
    cv2.fillConvexPoly(mask, np.int32(dst_tri_rect), (1.0, 1.0, 1.0), lineType=cv2.LINE_AA)

    dst_slice = dst[dst_rect[1] : dst_rect[1] + dst_rect[3], dst_rect[0] : dst_rect[0] + dst_rect[2]]
    dst_slice *= (1.0 - mask)
    dst_slice += warped * mask
    dst[dst_rect[1] : dst_rect[1] + dst_rect[3], dst_rect[0] : dst_rect[0] + dst_rect[2]] = dst_slice


def estimate_subject_mask(image: np.ndarray) -> np.ndarray:
    h, w = image.shape[:2]
    patch = 24
    corners = np.concatenate(
        [
            image[:patch, :patch].reshape(-1, 3),
            image[:patch, w - patch :].reshape(-1, 3),
            image[h - patch :, :patch].reshape(-1, 3),
            image[h - patch :, w - patch :].reshape(-1, 3),
        ],
        axis=0,
    ).astype(np.float32)
    bg = np.median(corners, axis=0)
    dist = np.linalg.norm(image.astype(np.float32) - bg, axis=2)
    mask = (dist > 22.0).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.GaussianBlur(mask, (11, 11), 0)
    return mask


def build_face_mask(face_pts: np.ndarray, width: int, height: int) -> np.ndarray:
    mask = np.zeros((height, width), dtype=np.uint8)
    oval = face_pts[FACE_OVAL_INDICES].astype(np.int32)
    cv2.fillPoly(mask, [oval], 255, lineType=cv2.LINE_AA)
    mask = cv2.GaussianBlur(mask, (9, 9), 0)
    return mask


def warp_image_and_mask(
    image: np.ndarray,
    subject_mask: np.ndarray,
    src_pts: np.ndarray,
    dst_pts: np.ndarray,
    triangles: list[tuple[int, int, int]],
) -> tuple[np.ndarray, np.ndarray]:
    warped_image = image.astype(np.float32).copy()
    mask_rgb = np.repeat((subject_mask.astype(np.float32) / 255.0)[..., None], 3, axis=2)
    warped_mask = mask_rgb.copy()

    for i1, i2, i3 in triangles:
        src_tri = np.array([src_pts[i1], src_pts[i2], src_pts[i3]], dtype=np.float32)
        dst_tri = np.array([dst_pts[i1], dst_pts[i2], dst_pts[i3]], dtype=np.float32)
        warp_triangle(image.astype(np.float32), warped_image, src_tri, dst_tri)
        warp_triangle(mask_rgb.astype(np.float32), warped_mask, src_tri, dst_tri)

    return warped_image, np.clip(warped_mask, 0.0, 1.0)


def composite_result(
    original: np.ndarray,
    warped_image: np.ndarray,
    warped_mask: np.ndarray,
    warped_face_pts: np.ndarray,
) -> np.ndarray:
    h, w = original.shape[:2]
    face_mask = build_face_mask(warped_face_pts, w, h).astype(np.float32) / 255.0
    full_alpha = np.clip(warped_mask[..., 0], 0.0, 1.0)
    alpha = np.maximum(full_alpha, face_mask * 0.65)
    alpha = cv2.GaussianBlur(alpha, (9, 9), 0)
    alpha = alpha[..., None]
    result = original.astype(np.float32) * (1.0 - alpha) + warped_image.astype(np.float32) * alpha
    return cv2.GaussianBlur(np.clip(result, 0, 255).astype(np.uint8), (3, 3), 0)


def main() -> None:
    args = parse_args()
    seed_image = Path(args.seed_image)
    targets_json = Path(args.targets_json)
    output_dir = Path(args.output_dir)
    output_images = output_dir / "images"
    output_images.mkdir(parents=True, exist_ok=True)

    targets = json.loads(targets_json.read_text(encoding="utf-8"))["targets"]

    landmarker = get_landmarker(Path(args.model_path))
    try:
        src_landmarks = detect_landmarks(landmarker, seed_image)
    finally:
        landmarker.close()

    image = cv2.imread(str(seed_image))
    if image is None:
        raise SystemExit(f"Failed to read seed image: {seed_image}")
    height, width = image.shape[:2]
    subject_mask = estimate_subject_mask(image)

    all_landmarks = add_border_points(src_landmarks)
    src_pts = landmarks_to_pixels(all_landmarks, width, height)
    triangles = build_triangles(src_pts, width, height)

    metadata: list[dict[str, object]] = []
    total = len(targets)
    for idx, target in enumerate(targets, start=1):
        delta_pitch = target["target_pitch"] - target["reference_pitch"]
        delta_yaw = target["target_yaw"] - target["reference_yaw"]
        delta_roll = target["target_roll"] - target["reference_roll"]

        rotated = rotate_landmarks(all_landmarks, delta_pitch, delta_yaw, delta_roll)
        dst_pts = landmarks_to_pixels(rotated, width, height)
        warped_image, warped_mask = warp_image_and_mask(image, subject_mask, src_pts, dst_pts, triangles)
        result = composite_result(image, warped_image, warped_mask, dst_pts[: len(src_landmarks)])

        out_name = (
            f"aug_{idx:04d}_p{target['target_pitch']:+04d}_"
            f"y{target['target_yaw']:+04d}_r{target['target_roll']:+04d}.png"
        )
        cv2.imwrite(str(output_images / out_name), result)
        metadata.append(
            {
                "output_file": out_name,
                "source_file": seed_image.name,
                "reference_pitch": target["reference_pitch"],
                "reference_yaw": target["reference_yaw"],
                "reference_roll": target["reference_roll"],
                "target_pitch": target["target_pitch"],
                "target_yaw": target["target_yaw"],
                "target_roll": target["target_roll"],
                "region": target.get("region", ""),
                "source": target.get("source", ""),
            }
        )
        if idx % 100 == 0 or idx == total:
            print(f"{idx}/{total}")

    (output_dir / "metadata.json").write_text(
        json.dumps(
            {
                "summary": {
                    "generated_images": len(metadata),
                    "seed_image": str(seed_image.resolve()),
                },
                "items": metadata,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
