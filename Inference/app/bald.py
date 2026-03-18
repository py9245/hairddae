from __future__ import annotations

import logging
from pathlib import Path
from threading import Lock

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from app.acceleration import select_mediapipe_delegate


LEFT_TEMPLE = 127
RIGHT_TEMPLE = 356
CHIN = 152
FOREHEAD = 10
NOSE_TIP = 4
LEFT_CHEEK = 234
RIGHT_CHEEK = 454
LEFT_EYEBROW = [70, 63, 105, 66, 107, 55, 65, 52, 53, 46]
RIGHT_EYEBROW = [336, 296, 334, 293, 300, 285, 295, 282, 283, 276]
HAIR_CATEGORY_INDEX = 1
logger = logging.getLogger("uvicorn.error")
_KNOWN_GPU_INCOMPATIBLE_SEGMENTER_MODELS: dict[str, str] = {}


def _polygon_mask(indices: list[int], landmarks_px: np.ndarray, width: int, height: int) -> np.ndarray:
    points = np.array([landmarks_px[index] for index in indices], dtype=np.int32)
    mask = np.zeros((height, width), dtype=np.uint8)
    if len(points) >= 3:
        cv2.fillConvexPoly(mask, cv2.convexHull(points), 255)
    return mask


def _refine_mask(mask: np.ndarray) -> np.ndarray:
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8), iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8), iterations=1)
    return cv2.dilate(mask, np.ones((5, 5), np.uint8), iterations=1)


def _keep_top_connected_hair(mask: np.ndarray, forehead_y: int) -> np.ndarray:
    binary = (mask > 0).astype(np.uint8)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if num_labels <= 1:
        return mask

    best_label = 0
    best_score = -1e18
    for label in range(1, num_labels):
        _, y, _, _, area = stats[label]
        if area < 100:
            continue
        top_bonus = max(forehead_y - y, 0) * 12
        score = float(area) + top_bonus - max(y - forehead_y, 0) * 4
        if score > best_score:
            best_score = score
            best_label = label

    if best_label == 0:
        return mask
    return np.where(labels == best_label, mask, 0).astype(np.uint8)


def _build_face_lower_protect_mask(landmarks_px: np.ndarray, width: int, height: int) -> np.ndarray:
    left_temple = landmarks_px[LEFT_TEMPLE]
    right_temple = landmarks_px[RIGHT_TEMPLE]
    chin = landmarks_px[CHIN]
    nose = landmarks_px[NOSE_TIP]
    left_cheek = landmarks_px[LEFT_CHEEK]
    right_cheek = landmarks_px[RIGHT_CHEEK]

    face_width = max(abs(int(right_temple[0]) - int(left_temple[0])), 1)
    face_height = max(abs(int(chin[1]) - int(nose[1])), 1)
    center = (
        int((int(left_cheek[0]) + int(right_cheek[0])) * 0.5),
        int(int(nose[1]) + face_height * 0.72),
    )
    axes = (
        max(int(face_width * 0.62), 12),
        max(int(face_height * 0.42), 10),
    )
    mask = np.zeros((height, width), dtype=np.uint8)
    cv2.ellipse(mask, center, axes, 0, 0, 360, 255, -1)

    jaw_points = np.array([left_cheek, chin, right_cheek], dtype=np.int32)
    cv2.fillConvexPoly(mask, jaw_points, 255)

    x1 = max(min(int(left_cheek[0]), int(left_temple[0])) - int(face_width * 0.08), 0)
    x2 = min(max(int(right_cheek[0]), int(right_temple[0])) + int(face_width * 0.08), width - 1)
    y1 = max(int(int(nose[1]) + (int(chin[1]) - int(nose[1])) * 0.18), 0)
    y2 = min(height - 1, int(chin[1]) + int((int(chin[1]) - int(nose[1])) * 0.22))
    cv2.rectangle(mask, (x1, y1), (x2, y2), 255, -1)
    return cv2.GaussianBlur(mask, (71, 71), 0).astype(np.float32) / 255.0


def _build_neck_side_protect_mask(landmarks_px: np.ndarray, width: int, height: int) -> np.ndarray:
    left_temple = landmarks_px[LEFT_TEMPLE]
    right_temple = landmarks_px[RIGHT_TEMPLE]
    chin = landmarks_px[CHIN]
    left_cheek = landmarks_px[LEFT_CHEEK]
    right_cheek = landmarks_px[RIGHT_CHEEK]

    face_width = max(abs(int(right_temple[0]) - int(left_temple[0])), 1)
    face_height = max(abs(int(chin[1]) - min(int(left_temple[1]), int(right_temple[1]))), 1)
    mask = np.zeros((height, width), dtype=np.uint8)

    y_top = max(int(chin[1] - face_height * 0.08), 0)
    y_bottom = min(int(chin[1] + face_height * 0.42), height - 1)

    left_poly = np.array(
        [
            [max(int(left_cheek[0] - face_width * 0.14), 0), y_top],
            [max(int(left_cheek[0] - face_width * 0.34), 0), min(int(chin[1] + face_height * 0.10), height - 1)],
            [max(int(left_cheek[0] - face_width * 0.28), 0), y_bottom],
            [max(int(left_cheek[0] - face_width * 0.06), 0), y_bottom],
            [max(int(left_cheek[0] + face_width * 0.04), 0), min(int(chin[1] + face_height * 0.06), height - 1)],
        ],
        dtype=np.int32,
    )
    right_poly = np.array(
        [
            [min(int(right_cheek[0] + face_width * 0.14), width - 1), y_top],
            [min(int(right_cheek[0] + face_width * 0.34), width - 1), min(int(chin[1] + face_height * 0.10), height - 1)],
            [min(int(right_cheek[0] + face_width * 0.28), width - 1), y_bottom],
            [min(int(right_cheek[0] + face_width * 0.06), width - 1), y_bottom],
            [min(int(right_cheek[0] - face_width * 0.04), width - 1), min(int(chin[1] + face_height * 0.06), height - 1)],
        ],
        dtype=np.int32,
    )

    cv2.fillConvexPoly(mask, left_poly, 255)
    cv2.fillConvexPoly(mask, right_poly, 255)
    return cv2.GaussianBlur(mask, (51, 51), 0).astype(np.float32) / 255.0


def _extract_hair_mask(
    result: object,
    height: int,
    width: int,
) -> tuple[np.ndarray, np.ndarray | None]:
    confidence_masks = getattr(result, "confidence_masks", None)
    hair_confidence: np.ndarray | None = None

    if confidence_masks is not None and len(confidence_masks) > HAIR_CATEGORY_INDEX:
        hair_confidence = confidence_masks[HAIR_CATEGORY_INDEX].numpy_view()
        if hair_confidence.ndim == 3 and hair_confidence.shape[-1] == 1:
            hair_confidence = hair_confidence[..., 0]
        if hair_confidence.shape[:2] != (height, width):
            hair_confidence = cv2.resize(
                hair_confidence.astype(np.float32),
                (width, height),
                interpolation=cv2.INTER_LINEAR,
            )
        hair_mask = (hair_confidence > 0.55).astype(np.uint8) * 255
        return hair_mask, hair_confidence

    category_mask = result.category_mask.numpy_view()  # type: ignore[attr-defined]
    if category_mask.ndim == 3 and category_mask.shape[-1] == 1:
        category_mask = category_mask[..., 0]
    hair_mask = (category_mask == HAIR_CATEGORY_INDEX).astype(np.uint8) * 255
    if hair_mask.shape[:2] != (height, width):
        hair_mask = cv2.resize(hair_mask, (width, height), interpolation=cv2.INTER_NEAREST)
    return hair_mask, None


def _is_known_gpu_incompatible_segmenter_error(exc: Exception) -> bool:
    message = str(exc)
    return (
        "TfLiteGpuDelegate Prepare: Batch size mismatch" in message
        or "expected 1 but got 8" in message
    )


def _sample_skin_color(
    image_rgb: np.ndarray,
    nose: np.ndarray,
    left_cheek: np.ndarray,
    right_cheek: np.ndarray,
    left_temple: np.ndarray,
    right_temple: np.ndarray,
    chin: np.ndarray,
) -> np.ndarray:
    face_width = max(abs(int(right_temple[0]) - int(left_temple[0])), 1)
    face_height = max(abs(int(chin[1]) - int(nose[1])), 1)
    specs = [
        (nose, 0.16, 0.12, 0.00, 0.00),
        (nose, 0.14, 0.10, -0.12, 0.08),
        (nose, 0.14, 0.10, 0.12, 0.08),
        (left_cheek, 0.18, 0.14, 0.00, 0.00),
        (right_cheek, 0.18, 0.14, 0.00, 0.00),
    ]
    patches: list[np.ndarray] = []
    for anchor, width_ratio, height_ratio, x_shift, y_shift in specs:
        patch_width = max(int(face_width * width_ratio), 12)
        patch_height = max(int(face_height * height_ratio), 10)
        center_x = int(anchor[0] + face_width * x_shift)
        center_y = int(anchor[1] + face_height * y_shift)
        x1 = max(center_x - patch_width // 2, 0)
        y1 = max(center_y - patch_height // 2, 0)
        x2 = min(x1 + patch_width, image_rgb.shape[1])
        y2 = min(y1 + patch_height, image_rgb.shape[0])
        patch = image_rgb[y1:y2, x1:x2]
        if patch.size:
            patches.append(patch)

    if not patches:
        return np.array([170, 170, 170], dtype=np.float32)

    merged = np.concatenate([patch.reshape(-1, 3) for patch in patches], axis=0)
    hsv = cv2.cvtColor(
        np.clip(merged.reshape(1, -1, 3), 0, 255).astype(np.uint8),
        cv2.COLOR_RGB2HSV,
    ).reshape(-1, 3)
    keep = (hsv[:, 1] > 18) & (hsv[:, 1] < 170) & (hsv[:, 2] > 45)
    if np.any(keep):
        merged = merged[keep]
    return np.clip(np.percentile(merged, 52, axis=0), 0, 255).astype(np.float32)


def _inpaint_mask_crop(image_rgb: np.ndarray, mask: np.ndarray, radius: int = 5, pad: int = 24) -> np.ndarray:
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        return image_rgb.copy()

    x1 = max(int(xs.min()) - pad, 0)
    y1 = max(int(ys.min()) - pad, 0)
    x2 = min(int(xs.max()) + pad + 1, image_rgb.shape[1])
    y2 = min(int(ys.max()) + pad + 1, image_rgb.shape[0])
    output = image_rgb.copy()
    crop_image = image_rgb[y1:y2, x1:x2]
    crop_mask = mask[y1:y2, x1:x2].astype(np.uint8)
    output[y1:y2, x1:x2] = cv2.inpaint(crop_image, crop_mask, radius, cv2.INPAINT_TELEA)
    return output


def _paint_segmented_hair_as_skin(
    image_rgb: np.ndarray,
    target_mask: np.ndarray,
    forehead_color: np.ndarray,
) -> np.ndarray:
    if not np.any(target_mask):
        return image_rgb

    solid_target = cv2.morphologyEx(target_mask.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((11, 11), np.uint8), 1)
    solid_target = cv2.morphologyEx(solid_target, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8), 1)
    cleaned = _inpaint_mask_crop(image_rgb, solid_target, radius=5).astype(np.float32)

    base_alpha = cv2.GaussianBlur(solid_target, (31, 31), 0).astype(np.float32) / 255.0
    base_alpha = np.clip((base_alpha - 0.04) / 0.96, 0.0, 1.0)
    alpha = np.clip(base_alpha * 1.02, 0.0, 1.0)
    edge_alpha = np.clip(base_alpha - (solid_target.astype(np.float32) / 255.0), 0.0, 1.0)

    skin = forehead_color.reshape(1, 1, 3).astype(np.float32)
    skin_fill = cleaned * 0.38 + skin * 0.62
    skin_fill = cv2.GaussianBlur(np.clip(skin_fill, 0, 255).astype(np.uint8), (0, 0), 1.2).astype(np.float32)

    outer_ring = cv2.dilate(solid_target, np.ones((25, 25), np.uint8), 1)
    inner_ring = cv2.dilate(solid_target, np.ones((9, 9), np.uint8), 1)
    ring_mask = cv2.subtract(outer_ring, inner_ring)
    ring_pixels = cleaned[ring_mask > 0]
    if ring_pixels.size:
        ring_color = np.percentile(ring_pixels, 55, axis=0).astype(np.float32)
    else:
        ring_color = cleaned.reshape(-1, 3).mean(axis=0).astype(np.float32)
    ring_fill = np.full_like(cleaned, ring_color, dtype=np.float32)
    ring_fill = ring_fill * 0.72 + cleaned * 0.28
    fill = skin_fill * (1.0 - edge_alpha[..., None]) + ring_fill * edge_alpha[..., None]

    output = (
        image_rgb.astype(np.float32) * (1.0 - alpha[..., None])
        + fill * alpha[..., None]
    )
    return np.clip(output, 0, 255).astype(np.uint8)


class BaldPreprocessor:
    def __init__(
        self,
        model_path: Path,
        *,
        delegate_preference: str = "auto",
        running_mode: str = "image",
    ) -> None:
        resolved_model_path = model_path.expanduser().resolve()
        self._running_mode = self._resolve_running_mode(running_mode)
        self._video_timestamp_ms = 0
        self._acceleration = "cpu"
        self._initialization_warning: str | None = None
        self._segmenter = self._build_segmenter(
            resolved_model_path,
            delegate_preference=delegate_preference,
        )
        self._lock = Lock()

    def close(self) -> None:
        self._segmenter.close()

    @property
    def acceleration(self) -> str:
        return self._acceleration

    @property
    def initialization_warning(self) -> str | None:
        return self._initialization_warning

    @staticmethod
    def _resolve_running_mode(running_mode: str) -> vision.RunningMode:
        resolved = running_mode.strip().lower()
        if resolved == "video":
            return vision.RunningMode.VIDEO
        return vision.RunningMode.IMAGE

    def _build_segmenter(
        self,
        model_path: Path,
        *,
        delegate_preference: str,
    ) -> vision.ImageSegmenter:
        delegate, delegate_name = select_mediapipe_delegate(delegate_preference)
        model_key = str(model_path)
        cached_gpu_failure = _KNOWN_GPU_INCOMPATIBLE_SEGMENTER_MODELS.get(model_key)
        if delegate_name == "gpu" and cached_gpu_failure:
            self._initialization_warning = cached_gpu_failure
            logger.warning(
                "bald preprocessor skipping GPU delegate for known-incompatible model %s: %s",
                model_path.name,
                cached_gpu_failure,
            )
            delegate = python.BaseOptions.Delegate.CPU
            delegate_name = "cpu"
        options = vision.ImageSegmenterOptions(
            base_options=python.BaseOptions(
                model_asset_path=str(model_path),
                delegate=delegate,
            ),
            running_mode=self._running_mode,
            output_category_mask=True,
            output_confidence_masks=True,
        )
        try:
            segmenter = vision.ImageSegmenter.create_from_options(options)
            self._acceleration = delegate_name
            logger.info(
                "bald preprocessor initialized: delegate=%s running_mode=%s",
                delegate_name,
                self._running_mode.name.lower(),
            )
            return segmenter
        except Exception as exc:
            if delegate_name != "gpu":
                raise
            if _is_known_gpu_incompatible_segmenter_error(exc):
                _KNOWN_GPU_INCOMPATIBLE_SEGMENTER_MODELS[model_key] = str(exc)
            self._initialization_warning = str(exc)
            logger.warning("bald preprocessor GPU delegate unavailable, falling back to CPU: %s", exc)
            fallback_options = vision.ImageSegmenterOptions(
                base_options=python.BaseOptions(
                    model_asset_path=str(model_path),
                    delegate=python.BaseOptions.Delegate.CPU,
                ),
                running_mode=self._running_mode,
                output_category_mask=True,
                output_confidence_masks=True,
            )
            segmenter = vision.ImageSegmenter.create_from_options(fallback_options)
            self._acceleration = "cpu"
            return segmenter

    def _next_video_timestamp_ms(self) -> int:
        self._video_timestamp_ms += 1
        return self._video_timestamp_ms

    def apply(self, frame_rgb: np.ndarray, landmarks_px: np.ndarray) -> np.ndarray:
        if frame_rgb.ndim != 3 or frame_rgb.shape[2] != 3:
            return frame_rgb

        if not frame_rgb.flags["C_CONTIGUOUS"]:
            frame_rgb = np.ascontiguousarray(frame_rgb)

        height, width = frame_rgb.shape[:2]
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        with self._lock:
            if self._running_mode == vision.RunningMode.VIDEO:
                result = self._segmenter.segment_for_video(
                    mp_image,
                    self._next_video_timestamp_ms(),
                )
            else:
                result = self._segmenter.segment(mp_image)

        hair_mask, hair_confidence = _extract_hair_mask(result, height, width)
        hair_mask = _refine_mask(hair_mask)

        target_mask = hair_mask
        lower_face_protect: np.ndarray | None = None
        if landmarks_px.shape[0] > RIGHT_CHEEK:
            eyebrow_mask = _polygon_mask(LEFT_EYEBROW, landmarks_px, width, height)
            eyebrow_mask = cv2.bitwise_or(eyebrow_mask, _polygon_mask(RIGHT_EYEBROW, landmarks_px, width, height))
            eyebrow_guard = cv2.dilate(eyebrow_mask, np.ones((13, 13), np.uint8), 1)

            target_mask = cv2.bitwise_and(target_mask, cv2.bitwise_not(eyebrow_guard))
            lower_face_protect = _build_face_lower_protect_mask(landmarks_px, width, height)
            target_mask = np.where(lower_face_protect > 0.08, 0, target_mask).astype(np.uint8)
            neck_side_protect = _build_neck_side_protect_mask(landmarks_px, width, height)
            target_mask = np.where(neck_side_protect > 0.10, 0, target_mask).astype(np.uint8)
            target_mask = _keep_top_connected_hair(target_mask, int(landmarks_px[FOREHEAD][1]))
            forehead_color = _sample_skin_color(
                frame_rgb,
                nose=landmarks_px[NOSE_TIP],
                left_cheek=landmarks_px[LEFT_CHEEK],
                right_cheek=landmarks_px[RIGHT_CHEEK],
                left_temple=landmarks_px[LEFT_TEMPLE],
                right_temple=landmarks_px[RIGHT_TEMPLE],
                chin=landmarks_px[CHIN],
            )
            return _paint_segmented_hair_as_skin(frame_rgb, target_mask, forehead_color)

        return frame_rgb
