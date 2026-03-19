from __future__ import annotations

import logging
import os
from pathlib import Path
from threading import Lock
import time

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


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


class _BaldTimingWindow:
    def __init__(self) -> None:
        self.frame_count = 0
        self.total_ms = 0.0
        self.segment_ms = 0.0
        self.extract_mask_ms = 0.0
        self.refine_mask_ms = 0.0
        self.eyebrow_guard_ms = 0.0
        self.protect_mask_ms = 0.0
        self.connected_component_ms = 0.0
        self.sample_skin_ms = 0.0
        self.paint_total_ms = 0.0
        self.paint_mask_prepare_ms = 0.0
        self.paint_inpaint_ms = 0.0
        self.paint_fill_ms = 0.0
        self.no_landmark_path_count = 0
        self.max_total_ms = 0.0
        self.frame_width = 0
        self.frame_height = 0
        self.roi_width = 0
        self.roi_height = 0


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


def _compute_head_roi(landmarks_px: np.ndarray, width: int, height: int) -> tuple[int, int, int, int] | None:
    if landmarks_px.shape[0] <= RIGHT_CHEEK:
        return None

    left_temple = landmarks_px[LEFT_TEMPLE]
    right_temple = landmarks_px[RIGHT_TEMPLE]
    forehead = landmarks_px[FOREHEAD]
    chin = landmarks_px[CHIN]
    left_cheek = landmarks_px[LEFT_CHEEK]
    right_cheek = landmarks_px[RIGHT_CHEEK]

    face_width = max(abs(int(right_temple[0]) - int(left_temple[0])), 1)
    face_height = max(abs(int(chin[1]) - int(forehead[1])), 1)

    x1 = max(
        int(min(left_temple[0], left_cheek[0]) - face_width * 0.42),
        0,
    )
    x2 = min(
        int(max(right_temple[0], right_cheek[0]) + face_width * 0.42),
        width,
    )
    y_top_anchor = min(int(forehead[1]), int(left_temple[1]), int(right_temple[1]))
    y1 = max(int(y_top_anchor - face_height * 0.95), 0)
    y2 = min(int(chin[1] + face_height * 0.42), height)

    if x2 - x1 < 32 or y2 - y1 < 32:
        return None
    return x1, y1, x2, y2


def _shift_landmarks_to_roi(landmarks_px: np.ndarray, x0: int, y0: int) -> np.ndarray:
    shifted = landmarks_px.copy()
    shifted[:, 0] -= x0
    shifted[:, 1] -= y0
    return shifted


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
) -> tuple[np.ndarray, dict[str, float]]:
    timings = {
        "paint_total_ms": 0.0,
        "paint_mask_prepare_ms": 0.0,
        "paint_inpaint_ms": 0.0,
        "paint_fill_ms": 0.0,
    }
    paint_started_at = time.perf_counter()
    if not np.any(target_mask):
        return image_rgb, timings

    solid_target = target_mask.astype(np.uint8, copy=False)

    stage_started_at = time.perf_counter()
    cleaned = _inpaint_mask_crop(image_rgb, solid_target, radius=5).astype(np.float32)
    timings["paint_inpaint_ms"] = (time.perf_counter() - stage_started_at) * 1000.0

    stage_started_at = time.perf_counter()
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
    timings["paint_fill_ms"] = (time.perf_counter() - stage_started_at) * 1000.0
    timings["paint_total_ms"] = (time.perf_counter() - paint_started_at) * 1000.0
    return np.clip(output, 0, 255).astype(np.uint8), timings


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
        self._timing_log_enabled = _env_bool("INFERENCE_BALD_TIMING_LOG_ENABLED", False)
        self._timing_log_interval_ms = _env_int("INFERENCE_BALD_TIMING_LOG_INTERVAL_MS", 1000)
        self._last_timing_log_at_ms = 0.0
        self._timing_window = _BaldTimingWindow()
        self._segmenter = self._build_segmenter(
            resolved_model_path,
            delegate_preference=delegate_preference,
        )
        self._lock = Lock()
        self._timing_lock = Lock()

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
            output_confidence_masks=False,
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
                output_confidence_masks=False,
            )
            segmenter = vision.ImageSegmenter.create_from_options(fallback_options)
            self._acceleration = "cpu"
            return segmenter

    def _next_video_timestamp_ms(self) -> int:
        self._video_timestamp_ms += 1
        return self._video_timestamp_ms

    def _record_timing(
        self,
        *,
        width: int,
        height: int,
        roi_width: int,
        roi_height: int,
        total_ms: float,
        segment_ms: float,
        extract_mask_ms: float,
        refine_mask_ms: float,
        eyebrow_guard_ms: float,
        protect_mask_ms: float,
        connected_component_ms: float,
        sample_skin_ms: float,
        paint_total_ms: float,
        paint_mask_prepare_ms: float,
        paint_inpaint_ms: float,
        paint_fill_ms: float,
        no_landmark_path: bool,
    ) -> None:
        if not self._timing_log_enabled:
            return

        with self._timing_lock:
            window = self._timing_window
            window.frame_count += 1
            window.total_ms += total_ms
            window.segment_ms += segment_ms
            window.extract_mask_ms += extract_mask_ms
            window.refine_mask_ms += refine_mask_ms
            window.eyebrow_guard_ms += eyebrow_guard_ms
            window.protect_mask_ms += protect_mask_ms
            window.connected_component_ms += connected_component_ms
            window.sample_skin_ms += sample_skin_ms
            window.paint_total_ms += paint_total_ms
            window.paint_mask_prepare_ms += paint_mask_prepare_ms
            window.paint_inpaint_ms += paint_inpaint_ms
            window.paint_fill_ms += paint_fill_ms
            window.no_landmark_path_count += int(no_landmark_path)
            window.max_total_ms = max(window.max_total_ms, total_ms)
            window.frame_width = width
            window.frame_height = height
            window.roi_width = roi_width
            window.roi_height = roi_height

            now_ms = time.monotonic() * 1000.0
            interval_ms = max(float(self._timing_log_interval_ms), 1.0)
            elapsed_ms = now_ms - self._last_timing_log_at_ms
            if elapsed_ms < interval_ms:
                return

            self._last_timing_log_at_ms = now_ms
            count = max(window.frame_count, 1)
            seconds = max(elapsed_ms / 1000.0, 1e-3)
            logger.info(
                (
                    "bald timing: frames=%s fps=%.2f avg_total_ms=%.1f max_total_ms=%.1f "
                    "segment_ms=%.1f extract_mask_ms=%.1f refine_mask_ms=%.1f "
                    "eyebrow_guard_ms=%.1f protect_mask_ms=%.1f connected_component_ms=%.1f "
                    "sample_skin_ms=%.1f paint_total_ms=%.1f paint_mask_prepare_ms=%.1f "
                    "paint_inpaint_ms=%.1f paint_fill_ms=%.1f no_landmark_path=%s "
                    "frame_size=%sx%s roi_size=%sx%s delegate=%s running_mode=%s"
                ),
                window.frame_count,
                window.frame_count / seconds,
                window.total_ms / count,
                window.max_total_ms,
                window.segment_ms / count,
                window.extract_mask_ms / count,
                window.refine_mask_ms / count,
                window.eyebrow_guard_ms / count,
                window.protect_mask_ms / count,
                window.connected_component_ms / count,
                window.sample_skin_ms / count,
                window.paint_total_ms / count,
                window.paint_mask_prepare_ms / count,
                window.paint_inpaint_ms / count,
                window.paint_fill_ms / count,
                window.no_landmark_path_count,
                window.frame_width,
                window.frame_height,
                window.roi_width,
                window.roi_height,
                self._acceleration,
                self._running_mode.name.lower(),
            )
            self._timing_window = _BaldTimingWindow()

    def apply(self, frame_rgb: np.ndarray, landmarks_px: np.ndarray) -> np.ndarray:
        if frame_rgb.ndim != 3 or frame_rgb.shape[2] != 3:
            return frame_rgb

        if not frame_rgb.flags["C_CONTIGUOUS"]:
            frame_rgb = np.ascontiguousarray(frame_rgb)

        total_started_at = time.perf_counter()
        height, width = frame_rgb.shape[:2]
        roi = _compute_head_roi(landmarks_px, width, height)
        if roi is None:
            self._record_timing(
                width=width,
                height=height,
                roi_width=0,
                roi_height=0,
                total_ms=(time.perf_counter() - total_started_at) * 1000.0,
                segment_ms=0.0,
                extract_mask_ms=0.0,
                refine_mask_ms=0.0,
                eyebrow_guard_ms=0.0,
                protect_mask_ms=0.0,
                connected_component_ms=0.0,
                sample_skin_ms=0.0,
                paint_total_ms=0.0,
                paint_mask_prepare_ms=0.0,
                paint_inpaint_ms=0.0,
                paint_fill_ms=0.0,
                no_landmark_path=True,
            )
            return frame_rgb

        x0, y0, x1, y1 = roi
        roi_width = x1 - x0
        roi_height = y1 - y0
        roi_rgb = frame_rgb[y0:y1, x0:x1]
        roi_landmarks_px = _shift_landmarks_to_roi(landmarks_px, x0, y0)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=roi_rgb)
        stage_started_at = time.perf_counter()
        with self._lock:
            if self._running_mode == vision.RunningMode.VIDEO:
                result = self._segmenter.segment_for_video(
                    mp_image,
                    self._next_video_timestamp_ms(),
                )
            else:
                result = self._segmenter.segment(mp_image)
        segment_ms = (time.perf_counter() - stage_started_at) * 1000.0

        stage_started_at = time.perf_counter()
        hair_mask, hair_confidence = _extract_hair_mask(result, roi_height, roi_width)
        extract_mask_ms = (time.perf_counter() - stage_started_at) * 1000.0
        stage_started_at = time.perf_counter()
        hair_mask = _refine_mask(hair_mask)
        refine_mask_ms = (time.perf_counter() - stage_started_at) * 1000.0
        if not np.any(hair_mask):
            self._record_timing(
                width=width,
                height=height,
                roi_width=roi_width,
                roi_height=roi_height,
                total_ms=(time.perf_counter() - total_started_at) * 1000.0,
                segment_ms=segment_ms,
                extract_mask_ms=extract_mask_ms,
                refine_mask_ms=refine_mask_ms,
                eyebrow_guard_ms=0.0,
                protect_mask_ms=0.0,
                connected_component_ms=0.0,
                sample_skin_ms=0.0,
                paint_total_ms=0.0,
                paint_mask_prepare_ms=0.0,
                paint_inpaint_ms=0.0,
                paint_fill_ms=0.0,
                no_landmark_path=False,
            )
            return frame_rgb

        target_mask = hair_mask
        eyebrow_guard_ms = 0.0
        protect_mask_ms = 0.0
        connected_component_ms = 0.0
        sample_skin_ms = 0.0
        paint_timings = {
            "paint_total_ms": 0.0,
            "paint_mask_prepare_ms": 0.0,
            "paint_inpaint_ms": 0.0,
            "paint_fill_ms": 0.0,
        }
        no_landmark_path = False
        stage_started_at = time.perf_counter()
        eyebrow_mask = _polygon_mask(LEFT_EYEBROW, roi_landmarks_px, roi_width, roi_height)
        eyebrow_mask = cv2.bitwise_or(
            eyebrow_mask,
            _polygon_mask(RIGHT_EYEBROW, roi_landmarks_px, roi_width, roi_height),
        )
        eyebrow_guard = cv2.dilate(eyebrow_mask, np.ones((13, 13), np.uint8), 1)
        eyebrow_guard_ms = (time.perf_counter() - stage_started_at) * 1000.0

        stage_started_at = time.perf_counter()
        target_mask = cv2.bitwise_and(target_mask, cv2.bitwise_not(eyebrow_guard))
        lower_face_protect = _build_face_lower_protect_mask(roi_landmarks_px, roi_width, roi_height)
        target_mask = np.where(lower_face_protect > 0.08, 0, target_mask).astype(np.uint8)
        neck_side_protect = _build_neck_side_protect_mask(roi_landmarks_px, roi_width, roi_height)
        target_mask = np.where(neck_side_protect > 0.10, 0, target_mask).astype(np.uint8)
        protect_mask_ms = (time.perf_counter() - stage_started_at) * 1000.0
        if not np.any(target_mask):
            self._record_timing(
                width=width,
                height=height,
                roi_width=roi_width,
                roi_height=roi_height,
                total_ms=(time.perf_counter() - total_started_at) * 1000.0,
                segment_ms=segment_ms,
                extract_mask_ms=extract_mask_ms,
                refine_mask_ms=refine_mask_ms,
                eyebrow_guard_ms=eyebrow_guard_ms,
                protect_mask_ms=protect_mask_ms,
                connected_component_ms=0.0,
                sample_skin_ms=0.0,
                paint_total_ms=0.0,
                paint_mask_prepare_ms=0.0,
                paint_inpaint_ms=0.0,
                paint_fill_ms=0.0,
                no_landmark_path=no_landmark_path,
            )
            return frame_rgb

        stage_started_at = time.perf_counter()
        target_mask = _keep_top_connected_hair(target_mask, int(roi_landmarks_px[FOREHEAD][1]))
        connected_component_ms = (time.perf_counter() - stage_started_at) * 1000.0

        stage_started_at = time.perf_counter()
        forehead_color = _sample_skin_color(
            roi_rgb,
            nose=roi_landmarks_px[NOSE_TIP],
            left_cheek=roi_landmarks_px[LEFT_CHEEK],
            right_cheek=roi_landmarks_px[RIGHT_CHEEK],
            left_temple=roi_landmarks_px[LEFT_TEMPLE],
            right_temple=roi_landmarks_px[RIGHT_TEMPLE],
            chin=roi_landmarks_px[CHIN],
        )
        sample_skin_ms = (time.perf_counter() - stage_started_at) * 1000.0
        rendered_roi_rgb, paint_timings = _paint_segmented_hair_as_skin(roi_rgb, target_mask, forehead_color)
        output_rgb = frame_rgb.copy()
        output_rgb[y0:y1, x0:x1] = rendered_roi_rgb
        self._record_timing(
            width=width,
            height=height,
            roi_width=roi_width,
            roi_height=roi_height,
            total_ms=(time.perf_counter() - total_started_at) * 1000.0,
            segment_ms=segment_ms,
            extract_mask_ms=extract_mask_ms,
            refine_mask_ms=refine_mask_ms,
            eyebrow_guard_ms=eyebrow_guard_ms,
            protect_mask_ms=protect_mask_ms,
            connected_component_ms=connected_component_ms,
            sample_skin_ms=sample_skin_ms,
            paint_total_ms=paint_timings["paint_total_ms"],
            paint_mask_prepare_ms=paint_timings["paint_mask_prepare_ms"],
            paint_inpaint_ms=paint_timings["paint_inpaint_ms"],
            paint_fill_ms=paint_timings["paint_fill_ms"],
            no_landmark_path=no_landmark_path,
        )
        return output_rgb
