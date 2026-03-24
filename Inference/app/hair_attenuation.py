from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from app.face_tracking import FACE_LANDMARK_INDEX


def _point(landmarks_px: np.ndarray, name: str) -> np.ndarray:
    index = FACE_LANDMARK_INDEX[name]
    return landmarks_px[index].astype(np.float32)


def _clip_point(point: np.ndarray, width: int, height: int) -> tuple[int, int]:
    return (
        int(np.clip(round(float(point[0])), 0, max(width - 1, 0))),
        int(np.clip(round(float(point[1])), 0, max(height - 1, 0))),
    )


def _odd_kernel(value: float, minimum: int = 7) -> int:
    resolved = max(minimum, int(round(value)))
    if resolved % 2 == 0:
        resolved += 1
    return resolved


@dataclass(frozen=True)
class HairAttenuationProfile:
    segmentation_confidence_threshold: float = 0.32
    strength: float = 0.78
    desaturation: float = 0.24
    brightness_lift: float = 0.05
    blur_kernel_scale: float = 0.085
    max_work_dimension: int = 176
    bald_test_mode: bool = False


class HairAttenuator:
    UPPER_FILL_BGR = np.array([222.0, 214.0, 255.0], dtype=np.float32)

    def __init__(
        self,
        *,
        segmentation_confidence_threshold: float = 0.32,
        strength: float = 0.78,
        desaturation: float = 0.24,
        brightness_lift: float = 0.05,
        blur_kernel_scale: float = 0.085,
        max_work_dimension: int = 176,
        bald_test_mode: bool = False,
    ) -> None:
        self.profile = HairAttenuationProfile(
            segmentation_confidence_threshold=float(np.clip(segmentation_confidence_threshold, 0.05, 0.95)),
            strength=float(np.clip(strength, 0.0, 1.0)),
            desaturation=float(np.clip(desaturation, 0.0, 1.0)),
            brightness_lift=float(np.clip(brightness_lift, 0.0, 0.2)),
            blur_kernel_scale=max(0.01, float(blur_kernel_scale)),
            max_work_dimension=max(96, int(max_work_dimension)),
            bald_test_mode=bool(bald_test_mode),
        )

    def close(self) -> None:
        return None

    @staticmethod
    def _tone_metadata_from_roi(
        grayscale_work: np.ndarray,
        mask_work: np.ndarray,
    ) -> dict[str, Any]:
        if grayscale_work.ndim != 3 or grayscale_work.shape[2] != 3:
            return {}
        if mask_work.ndim != 2 or mask_work.size == 0:
            return {}

        tone_mask = np.where(mask_work >= 24, np.uint8(255), np.uint8(0))
        active_pixels = int(np.count_nonzero(tone_mask))
        if active_pixels < max(24, int(round(mask_work.size * 0.008))):
            return {}

        mean_luma = float(cv2.mean(grayscale_work[:, :, 0], mask=tone_mask)[0])
        if not np.isfinite(mean_luma) or mean_luma <= 1.0:
            return {}

        return {
            "mean_luma": round(mean_luma, 3),
            "coverage": round(active_pixels / float(mask_work.size), 6),
        }

    def _build_binary_mask(
        self,
        frame_shape: tuple[int, ...],
        landmarks_px: np.ndarray,
        *,
        user_row: dict[str, Any] | None = None,
    ) -> np.ndarray | None:
        if landmarks_px.ndim != 2 or landmarks_px.shape[1] < 2:
            return None

        max_index = max(FACE_LANDMARK_INDEX.values())
        if landmarks_px.shape[0] <= max_index:
            return None

        height, width = frame_shape[:2]
        forehead_top = _point(landmarks_px, "forehead_top")
        forehead_mid = _point(landmarks_px, "forehead_mid")
        left_temple = _point(landmarks_px, "left_temple")
        right_temple = _point(landmarks_px, "right_temple")
        left_ear_root = _point(landmarks_px, "left_ear_root")
        right_ear_root = _point(landmarks_px, "right_ear_root")
        left_side = _point(landmarks_px, "left_side")
        right_side = _point(landmarks_px, "right_side")
        lower_left = _point(landmarks_px, "lower_left")
        lower_right = _point(landmarks_px, "lower_right")
        chin_center = _point(landmarks_px, "chin_center")

        forehead_center = (forehead_top + forehead_mid) * 0.5
        face_center = (forehead_center + chin_center) * 0.5
        face_height = max(1.0, float(chin_center[1] - forehead_center[1]))
        temple_width = float(np.linalg.norm(right_temple - left_temple))
        side_width = float(np.linalg.norm(right_side - left_side))
        jaw_width = float(np.linalg.norm(lower_right - lower_left))
        face_width = max(1.0, temple_width, side_width * 0.96, jaw_width * 0.82)
        roll_deg = float(((user_row or {}).get("pose") or {}).get("roll_float", 0.0))

        crown_top = np.array(
            [
                forehead_center[0],
                forehead_center[1] - face_height * 0.52,
            ],
            dtype=np.float32,
        )
        crown_left = crown_top + np.array([-face_width * 0.42, face_height * 0.08], dtype=np.float32)
        crown_right = crown_top + np.array([face_width * 0.42, face_height * 0.08], dtype=np.float32)

        top_hull = np.array(
            [
                left_ear_root + np.array([-face_width * 0.14, -face_height * 0.10], dtype=np.float32),
                left_temple + np.array([-face_width * 0.14, -face_height * 0.11], dtype=np.float32),
                crown_left,
                crown_top,
                crown_right,
                right_temple + np.array([face_width * 0.14, -face_height * 0.11], dtype=np.float32),
                right_ear_root + np.array([face_width * 0.14, -face_height * 0.10], dtype=np.float32),
                right_side + np.array([face_width * 0.10, face_height * 0.16], dtype=np.float32),
                left_side + np.array([-face_width * 0.10, face_height * 0.16], dtype=np.float32),
            ],
            dtype=np.float32,
        )

        mask = np.zeros((height, width), dtype=np.uint8)
        cv2.fillPoly(
            mask,
            [np.array([_clip_point(point, width, height) for point in top_hull], dtype=np.int32)],
            255,
        )

        top_center = _clip_point(
            np.array(
                [
                    forehead_center[0],
                    forehead_center[1] - face_height * 0.02,
                ],
                dtype=np.float32,
            ),
            width,
            height,
        )
        top_axes = (
            max(1, int(round(face_width * 0.74))),
            max(1, int(round(face_height * 0.80))),
        )
        cv2.ellipse(mask, top_center, top_axes, roll_deg, 0, 360, 255, -1)

        side_axes = (
            max(1, int(round(face_width * 0.26))),
            max(1, int(round(face_height * 0.52))),
        )
        left_side_center = _clip_point(
            np.array(
                [
                    (left_ear_root[0] + left_side[0]) * 0.5 - face_width * 0.08,
                    (left_ear_root[1] + left_side[1]) * 0.5 + face_height * 0.14,
                ],
                dtype=np.float32,
            ),
            width,
            height,
        )
        right_side_center = _clip_point(
            np.array(
                [
                    (right_ear_root[0] + right_side[0]) * 0.5 + face_width * 0.08,
                    (right_ear_root[1] + right_side[1]) * 0.5 + face_height * 0.14,
                ],
                dtype=np.float32,
            ),
            width,
            height,
        )
        cv2.ellipse(mask, left_side_center, side_axes, roll_deg, 0, 360, 255, -1)
        cv2.ellipse(mask, right_side_center, side_axes, roll_deg, 0, 360, 255, -1)

        cutoff_y = int(
            np.clip(
                round(forehead_center[1] + face_height * 0.88),
                0,
                max(height - 1, 0),
            )
        )
        if cutoff_y < height:
            mask[cutoff_y:, :] = 0
        return mask

    @staticmethod
    def _normalize_confidence_mask(
        hair_confidence_mask: np.ndarray,
        width: int,
        height: int,
    ) -> np.ndarray | None:
        mask = np.asarray(hair_confidence_mask, dtype=np.float32)
        if mask.ndim == 3 and mask.shape[2] == 1:
            mask = mask[:, :, 0]
        if mask.ndim != 2:
            return None
        if mask.shape[1] != width or mask.shape[0] != height:
            mask = cv2.resize(mask, (width, height), interpolation=cv2.INTER_LINEAR)
        if mask.size == 0:
            return None
        return np.clip(mask, 0.0, 1.0)

    @staticmethod
    def _sample_patch_median(
        frame_bgr: np.ndarray,
        center_x: float,
        center_y: float,
        radius: int,
    ) -> np.ndarray | None:
        height, width = frame_bgr.shape[:2]
        if radius <= 0:
            return None
        x0 = max(0, int(round(center_x)) - radius)
        y0 = max(0, int(round(center_y)) - radius)
        x1 = min(width, int(round(center_x)) + radius + 1)
        y1 = min(height, int(round(center_y)) + radius + 1)
        if x1 - x0 < 3 or y1 - y0 < 3:
            return None
        patch = frame_bgr[y0:y1, x0:x1]
        if patch.size == 0:
            return None
        return np.median(patch.reshape(-1, 3), axis=0).astype(np.float32)

    @staticmethod
    def _estimate_skin_color_fallback(frame_bgr: np.ndarray) -> np.ndarray | None:
        height, width = frame_bgr.shape[:2]
        x0 = max(0, int(round(width * 0.34)))
        x1 = min(width, int(round(width * 0.66)))
        y0 = max(0, int(round(height * 0.22)))
        y1 = min(height, int(round(height * 0.46)))
        if x1 - x0 < 4 or y1 - y0 < 4:
            return None
        patch = frame_bgr[y0:y1, x0:x1]
        if patch.size == 0:
            return None
        return np.median(patch.reshape(-1, 3), axis=0).astype(np.float32)

    def _estimate_skin_color(
        self,
        frame_bgr: np.ndarray,
        landmarks_px: np.ndarray | None,
    ) -> np.ndarray | None:
        if landmarks_px is None or landmarks_px.ndim != 2 or landmarks_px.shape[1] < 2:
            return self._estimate_skin_color_fallback(frame_bgr)

        forehead_mid = _point(landmarks_px, "forehead_mid")
        left_temple = _point(landmarks_px, "left_temple")
        right_temple = _point(landmarks_px, "right_temple")
        chin_center = _point(landmarks_px, "chin_center")
        lower_left = _point(landmarks_px, "lower_left")
        lower_right = _point(landmarks_px, "lower_right")
        face_height = max(1.0, float(chin_center[1] - forehead_mid[1]))
        face_width = max(1.0, float(np.linalg.norm(lower_right - lower_left)))
        patch_radius = max(3, int(round(face_width * 0.055)))

        sample_points = [
            (float(forehead_mid[0]), float(forehead_mid[1] + face_height * 0.16)),
            (float(left_temple[0] + face_width * 0.10), float(left_temple[1] + face_height * 0.10)),
            (float(right_temple[0] - face_width * 0.10), float(right_temple[1] + face_height * 0.10)),
        ]

        samples = [
            sample
            for sample in (
                self._sample_patch_median(frame_bgr, point_x, point_y, patch_radius)
                for point_x, point_y in sample_points
            )
            if sample is not None
        ]
        if not samples:
            return None
        return np.median(np.stack(samples, axis=0), axis=0).astype(np.float32)

    @staticmethod
    def _resolve_scalp_color(skin_color: np.ndarray) -> np.ndarray:
        color = np.asarray(skin_color, dtype=np.float32).reshape(-1)
        if color.size < 3:
            return np.array([160.0, 180.0, 205.0], dtype=np.float32)
        swatch = np.clip(color[:3], 0.0, 255.0).astype(np.uint8).reshape(1, 1, 3)
        hsv = cv2.cvtColor(swatch, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] *= 0.92
        hsv[:, :, 2] = np.clip(hsv[:, :, 2] * 0.985 + 1.5, 0.0, 255.0)
        scalp = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR).reshape(3).astype(np.float32)
        return scalp

    @staticmethod
    def _resize_mask_float(
        mask: np.ndarray,
        width: int,
        height: int,
    ) -> np.ndarray:
        if mask.ndim != 2 or width <= 0 or height <= 0:
            return np.zeros((max(height, 0), max(width, 0)), dtype=np.float32)
        resolved = mask.astype(np.float32)
        if resolved.size == 0:
            return np.zeros((height, width), dtype=np.float32)
        if float(resolved.max()) > 1.0:
            resolved /= 255.0
        if resolved.shape != (height, width):
            resolved = cv2.resize(resolved, (width, height), interpolation=cv2.INTER_LINEAR)
        return np.clip(resolved, 0.0, 1.0)

    @staticmethod
    def _smoothstep(mask: np.ndarray) -> np.ndarray:
        resolved = np.clip(np.asarray(mask, dtype=np.float32), 0.0, 1.0)
        return resolved * resolved * (3.0 - 2.0 * resolved)

    def _build_interior_transition_mask(
        self,
        mask: np.ndarray,
        *,
        feather_px: int,
    ) -> np.ndarray:
        if mask.ndim != 2 or mask.size == 0:
            return np.zeros_like(mask, dtype=np.float32)
        active_mask = np.where(mask > 0, np.uint8(255), np.uint8(0))
        if int(np.count_nonzero(active_mask)) == 0:
            return np.zeros(active_mask.shape, dtype=np.float32)
        if feather_px <= 1:
            return np.where(active_mask > 0, np.float32(1.0), np.float32(0.0))
        distance = cv2.distanceTransform(active_mask, cv2.DIST_L2, 5)
        normalized = np.clip(distance / float(feather_px), 0.0, 1.0)
        smoothed = self._smoothstep(normalized)
        return np.where(active_mask > 0, smoothed, np.float32(0.0))

    def _estimate_lower_boundary_skin_color(
        self,
        frame_bgr: np.ndarray,
        hair_mask: np.ndarray,
        landmarks_px: np.ndarray | None,
        *,
        reference_skin_color: np.ndarray | None = None,
    ) -> np.ndarray | None:
        if hair_mask.ndim != 2 or hair_mask.shape[:2] != frame_bgr.shape[:2]:
            return None
        active = np.where(hair_mask > 0, np.uint8(255), np.uint8(0))
        if int(np.count_nonzero(active)) < 64:
            return None

        height, width = active.shape
        x, y, mask_width, mask_height = cv2.boundingRect(active)
        if mask_width <= 1 or mask_height <= 1:
            return None

        edge_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 5))
        eroded = cv2.erode(active, edge_kernel, iterations=1)
        lower_edge = cv2.subtract(active, eroded)
        if int(np.count_nonzero(lower_edge)) == 0:
            return None

        band_px = max(2, min(16, int(round(mask_height * 0.08))))
        below_band = np.zeros_like(active)
        for offset in range(1, band_px + 1):
            below_band[offset:, :] = np.maximum(below_band[offset:, :], lower_edge[:-offset, :])
        below_band = cv2.bitwise_and(below_band, cv2.bitwise_not(active))

        if landmarks_px is not None and landmarks_px.ndim == 2 and landmarks_px.shape[1] >= 2:
            forehead_mid = _point(landmarks_px, "forehead_mid")
            left_temple = _point(landmarks_px, "left_temple")
            right_temple = _point(landmarks_px, "right_temple")
            chin_center = _point(landmarks_px, "chin_center")
            lower_left = _point(landmarks_px, "lower_left")
            lower_right = _point(landmarks_px, "lower_right")
            face_height = max(1.0, float(chin_center[1] - forehead_mid[1]))
            face_width = max(1.0, float(np.linalg.norm(lower_right - lower_left)))
            forehead_band = np.zeros_like(active)
            x0 = int(np.clip(round(min(left_temple[0], right_temple[0]) - face_width * 0.08), 0, width - 1))
            x1 = int(np.clip(round(max(left_temple[0], right_temple[0]) + face_width * 0.08), 0, width))
            y0 = int(np.clip(round(forehead_mid[1] - face_height * 0.06), 0, height - 1))
            y1 = int(np.clip(round(forehead_mid[1] + face_height * 0.42), 0, height))
            if x1 > x0 and y1 > y0:
                forehead_band[y0:y1, x0:x1] = 255
                below_band = cv2.bitwise_and(below_band, forehead_band)

        if int(np.count_nonzero(below_band)) < 24:
            return None

        candidate_pixels = frame_bgr[below_band > 0]
        if candidate_pixels.size < 72:
            return None

        candidate_pixels = candidate_pixels.reshape(-1, 3).astype(np.uint8)
        candidate_ycrcb = cv2.cvtColor(candidate_pixels.reshape(-1, 1, 3), cv2.COLOR_BGR2YCrCb).reshape(-1, 3).astype(np.float32)
        candidate_luma = candidate_ycrcb[:, 0]
        keep_mask = candidate_luma >= 45.0

        if reference_skin_color is not None:
            reference = np.clip(np.asarray(reference_skin_color, dtype=np.float32).reshape(-1)[:3], 0.0, 255.0).astype(np.uint8)
            if reference.size == 3:
                reference_ycrcb = cv2.cvtColor(reference.reshape(1, 1, 3), cv2.COLOR_BGR2YCrCb).reshape(3).astype(np.float32)
                chroma_distance = np.abs(candidate_ycrcb[:, 1] - reference_ycrcb[1]) + np.abs(candidate_ycrcb[:, 2] - reference_ycrcb[2])
                keep_mask &= chroma_distance <= 42.0

        filtered = candidate_pixels[keep_mask]
        if filtered.shape[0] < 24:
            filtered = candidate_pixels
        if filtered.shape[0] < 24:
            return None
        return np.median(filtered.astype(np.float32), axis=0).astype(np.float32)

    @staticmethod
    def _estimate_color_from_mask(
        frame_bgr: np.ndarray,
        mask: np.ndarray,
    ) -> np.ndarray | None:
        if mask.ndim != 2 or mask.shape[:2] != frame_bgr.shape[:2]:
            return None
        pixels = frame_bgr[mask > 0]
        if pixels.size < 48:
            return None
        return np.median(pixels.reshape(-1, 3), axis=0).astype(np.float32)

    @staticmethod
    def _estimate_patch_color_fallback(
        frame_bgr: np.ndarray,
        *,
        x_ratio_min: float,
        x_ratio_max: float,
        y_ratio_min: float,
        y_ratio_max: float,
    ) -> np.ndarray | None:
        height, width = frame_bgr.shape[:2]
        x0 = max(0, int(round(width * x_ratio_min)))
        x1 = min(width, int(round(width * x_ratio_max)))
        y0 = max(0, int(round(height * y_ratio_min)))
        y1 = min(height, int(round(height * y_ratio_max)))
        if x1 - x0 < 4 or y1 - y0 < 4:
            return None
        patch = frame_bgr[y0:y1, x0:x1]
        if patch.size == 0:
            return None
        return np.median(patch.reshape(-1, 3), axis=0).astype(np.float32)

    def _estimate_clothes_color(
        self,
        frame_bgr: np.ndarray,
        landmarks_px: np.ndarray | None,
        *,
        user_row: dict[str, Any] | None = None,
    ) -> np.ndarray | None:
        if landmarks_px is None or landmarks_px.ndim != 2 or landmarks_px.shape[1] < 2:
            fallback_samples = [
                self._estimate_patch_color_fallback(
                    frame_bgr,
                    x_ratio_min=0.06,
                    x_ratio_max=0.34,
                    y_ratio_min=0.74,
                    y_ratio_max=0.94,
                ),
                self._estimate_patch_color_fallback(
                    frame_bgr,
                    x_ratio_min=0.66,
                    x_ratio_max=0.94,
                    y_ratio_min=0.74,
                    y_ratio_max=0.94,
                ),
                self._estimate_patch_color_fallback(
                    frame_bgr,
                    x_ratio_min=0.34,
                    x_ratio_max=0.66,
                    y_ratio_min=0.78,
                    y_ratio_max=0.98,
                ),
            ]
            samples = [sample for sample in fallback_samples if sample is not None]
            if not samples:
                return None
            return np.median(np.stack(samples, axis=0), axis=0).astype(np.float32)

        anchors = (user_row or {}).get("anchors") if isinstance(user_row, dict) else None

        def _anchor_point(name: str) -> np.ndarray | None:
            if not isinstance(anchors, dict):
                return None
            payload = anchors.get(name)
            if not isinstance(payload, dict):
                return None
            x = payload.get("x")
            y = payload.get("y")
            if x is None or y is None:
                return None
            return np.array([float(x), float(y)], dtype=np.float32)

        neck_left = _anchor_point("neck_left")
        neck_right = _anchor_point("neck_right")
        lower_left = _point(landmarks_px, "lower_left")
        lower_right = _point(landmarks_px, "lower_right")
        chin_center = _point(landmarks_px, "chin_center")
        forehead_mid = _point(landmarks_px, "forehead_mid")
        if neck_left is None or neck_right is None:
            face_height = max(1.0, float(chin_center[1] - forehead_mid[1]))
            neck_left = lower_left + np.array([0.0, face_height * 0.22], dtype=np.float32)
            neck_right = lower_right + np.array([0.0, face_height * 0.22], dtype=np.float32)

        face_height = max(1.0, float(chin_center[1] - forehead_mid[1]))
        face_width = max(1.0, float(np.linalg.norm(lower_right - lower_left)))
        patch_radius = max(4, int(round(face_width * 0.075)))
        neck_center = (neck_left + neck_right) * 0.5
        sample_points = [
            (
                float(neck_left[0] - face_width * 0.18),
                float(neck_left[1] + face_height * 0.38),
            ),
            (
                float(neck_center[0]),
                float(neck_center[1] + face_height * 0.54),
            ),
            (
                float(neck_right[0] + face_width * 0.18),
                float(neck_right[1] + face_height * 0.38),
            ),
        ]
        samples = [
            sample
            for sample in (
                self._sample_patch_median(frame_bgr, point_x, point_y, patch_radius)
                for point_x, point_y in sample_points
            )
            if sample is not None
        ]
        if not samples:
            return self._estimate_clothes_color(frame_bgr, None, user_row=None)
        return np.median(np.stack(samples, axis=0), axis=0).astype(np.float32)

    def _estimate_background_color(
        self,
        frame_bgr: np.ndarray,
        hair_mask: np.ndarray,
        *,
        protect_mask: np.ndarray | None = None,
    ) -> np.ndarray | None:
        if hair_mask.ndim != 2 or hair_mask.shape[:2] != frame_bgr.shape[:2]:
            return None
        active = np.where(hair_mask > 0, np.uint8(255), np.uint8(0))
        x, y, width, height = cv2.boundingRect(active)
        if width <= 1 or height <= 1:
            return None
        ring_kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (
                _odd_kernel(max(width, height) * 0.12, minimum=11),
                _odd_kernel(max(width, height) * 0.12, minimum=11),
            ),
        )
        ring = cv2.dilate(active, ring_kernel, iterations=1)
        ring = cv2.subtract(ring, active)
        if protect_mask is not None and protect_mask.shape == ring.shape:
            ring[protect_mask > 0] = 0
        color = self._estimate_color_from_mask(frame_bgr, ring)
        if color is not None:
            return color
        fallback_samples = [
            self._estimate_patch_color_fallback(
                frame_bgr,
                x_ratio_min=0.02,
                x_ratio_max=0.20,
                y_ratio_min=0.02,
                y_ratio_max=0.22,
            ),
            self._estimate_patch_color_fallback(
                frame_bgr,
                x_ratio_min=0.80,
                x_ratio_max=0.98,
                y_ratio_min=0.02,
                y_ratio_max=0.22,
            ),
            self._estimate_patch_color_fallback(
                frame_bgr,
                x_ratio_min=0.36,
                x_ratio_max=0.64,
                y_ratio_min=0.02,
                y_ratio_max=0.18,
            ),
        ]
        samples = [sample for sample in fallback_samples if sample is not None]
        if not samples:
            return None
        return np.median(np.stack(samples, axis=0), axis=0).astype(np.float32)

    @staticmethod
    def _largest_convex_hull_mask(mask: np.ndarray) -> np.ndarray:
        if mask.ndim != 2 or mask.size == 0:
            return np.zeros_like(mask, dtype=np.uint8)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return np.zeros_like(mask, dtype=np.uint8)
        contour = max(contours, key=cv2.contourArea)
        if float(cv2.contourArea(contour)) < 32.0:
            return np.zeros_like(mask, dtype=np.uint8)
        hull = cv2.convexHull(contour)
        output = np.zeros_like(mask, dtype=np.uint8)
        cv2.fillConvexPoly(output, hull, 255)
        return output

    @staticmethod
    def _build_upper_region_mask_fallback(frame_shape: tuple[int, ...]) -> np.ndarray:
        height, width = frame_shape[:2]
        split_y = int(round(height * 0.6))
        mask = np.zeros((height, width), dtype=np.uint8)
        mask[: max(0, split_y), :] = 255
        return mask

    def _build_upper_region_mask(
        self,
        frame_shape: tuple[int, ...],
        landmarks_px: np.ndarray,
        *,
        user_row: dict[str, Any] | None = None,
    ) -> np.ndarray | None:
        height, width = frame_shape[:2]
        anchors = (user_row or {}).get("anchors") if isinstance(user_row, dict) else None

        def _anchor_point(name: str) -> np.ndarray | None:
            if not isinstance(anchors, dict):
                return None
            payload = anchors.get(name)
            if not isinstance(payload, dict):
                return None
            x = payload.get("x")
            y = payload.get("y")
            if x is None or y is None:
                return None
            return np.array([float(x), float(y)], dtype=np.float32)

        neck_left = _anchor_point("neck_left")
        neck_right = _anchor_point("neck_right")
        if neck_left is None or neck_right is None:
            lower_left = _point(landmarks_px, "lower_left")
            lower_right = _point(landmarks_px, "lower_right")
            chin_center = _point(landmarks_px, "chin_center")
            forehead_mid = _point(landmarks_px, "forehead_mid")
            face_height = max(1.0, float(chin_center[1] - forehead_mid[1]))
            neck_left = lower_left + np.array([0.0, face_height * 0.22], dtype=np.float32)
            neck_right = lower_right + np.array([0.0, face_height * 0.22], dtype=np.float32)

        if float(abs(neck_right[0] - neck_left[0])) < 1.0:
            return None

        margin = max(2.0, float(abs(neck_right[1] - neck_left[1])) * 0.5 + 6.0)
        left_point = np.array([0.0, np.interp(0.0, [neck_left[0], neck_right[0]], [neck_left[1], neck_right[1]]) - margin], dtype=np.float32)
        right_point = np.array([float(width - 1), np.interp(float(width - 1), [neck_left[0], neck_right[0]], [neck_left[1], neck_right[1]]) - margin], dtype=np.float32)
        polygon = np.array(
            [
                [0.0, 0.0],
                [float(width - 1), 0.0],
                right_point,
                left_point,
            ],
            dtype=np.float32,
        )
        mask = np.zeros((height, width), dtype=np.uint8)
        cv2.fillConvexPoly(
            mask,
            np.array([_clip_point(point, width, height) for point in polygon], dtype=np.int32),
            255,
        )
        return mask

    def _build_forehead_fringe_mask(
        self,
        frame_shape: tuple[int, ...],
        landmarks_px: np.ndarray,
        *,
        user_row: dict[str, Any] | None = None,
    ) -> np.ndarray | None:
        if landmarks_px.ndim != 2 or landmarks_px.shape[1] < 2:
            return None
        height, width = frame_shape[:2]
        forehead_top = _point(landmarks_px, "forehead_top")
        forehead_mid = _point(landmarks_px, "forehead_mid")
        lower_left = _point(landmarks_px, "lower_left")
        lower_right = _point(landmarks_px, "lower_right")
        chin_center = _point(landmarks_px, "chin_center")
        forehead_center = (forehead_top + forehead_mid) * 0.5
        face_height = max(1.0, float(chin_center[1] - forehead_center[1]))
        face_width = max(1.0, float(np.linalg.norm(lower_right - lower_left)))
        roll_deg = float(((user_row or {}).get("pose") or {}).get("roll_float", 0.0))
        center = _clip_point(
            np.array(
                [
                    forehead_center[0],
                    forehead_center[1] + face_height * 0.10,
                ],
                dtype=np.float32,
            ),
            width,
            height,
        )
        axes = (
            max(1, int(round(face_width * 0.58))),
            max(1, int(round(face_height * 0.24))),
        )
        mask = np.zeros((height, width), dtype=np.uint8)
        cv2.ellipse(mask, center, axes, roll_deg, 0, 360, 255, -1)
        return mask

    def _build_segmentation_seed_mask(
        self,
        frame_shape: tuple[int, ...],
        landmarks_px: np.ndarray,
        *,
        user_row: dict[str, Any] | None = None,
    ) -> np.ndarray | None:
        if landmarks_px.ndim != 2 or landmarks_px.shape[1] < 2:
            return None

        height, width = frame_shape[:2]
        forehead_top = _point(landmarks_px, "forehead_top")
        forehead_mid = _point(landmarks_px, "forehead_mid")
        left_temple = _point(landmarks_px, "left_temple")
        right_temple = _point(landmarks_px, "right_temple")
        left_ear_root = _point(landmarks_px, "left_ear_root")
        right_ear_root = _point(landmarks_px, "right_ear_root")
        left_side = _point(landmarks_px, "left_side")
        right_side = _point(landmarks_px, "right_side")
        lower_left = _point(landmarks_px, "lower_left")
        lower_right = _point(landmarks_px, "lower_right")
        chin_center = _point(landmarks_px, "chin_center")

        forehead_center = (forehead_top + forehead_mid) * 0.5
        face_height = max(1.0, float(chin_center[1] - forehead_center[1]))
        face_width = max(1.0, float(np.linalg.norm(lower_right - lower_left)))

        anchors = (user_row or {}).get("anchors") if isinstance(user_row, dict) else None
        crown_anchor = None
        if isinstance(anchors, dict):
            payload = anchors.get("crown")
            if isinstance(payload, dict) and payload.get("x") is not None and payload.get("y") is not None:
                crown_anchor = np.array([float(payload["x"]), float(payload["y"])], dtype=np.float32)
        if crown_anchor is None:
            crown_anchor = np.array(
                [
                    forehead_center[0],
                    forehead_center[1] - face_height * 0.38,
                ],
                dtype=np.float32,
            )

        seed_mask = np.zeros((height, width), dtype=np.uint8)
        seed_radius = max(6, int(round(max(face_width, face_height) * 0.095)))
        side_radius = max(6, int(round(seed_radius * 1.15)))
        seed_points = [
            (forehead_top, seed_radius),
            (forehead_mid, seed_radius),
            (crown_anchor, seed_radius),
            (left_temple, seed_radius),
            (right_temple, seed_radius),
            (left_ear_root, side_radius),
            (right_ear_root, side_radius),
            (left_side, side_radius),
            (right_side, side_radius),
        ]
        for point, radius in seed_points:
            cv2.circle(seed_mask, _clip_point(point, width, height), radius, 255, -1)

        seed_mask = cv2.dilate(
            seed_mask,
            cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (_odd_kernel(seed_radius * 1.25, minimum=9), _odd_kernel(seed_radius * 1.25, minimum=9)),
            ),
            iterations=1,
        )
        return seed_mask

    def _refine_segmentation_confidence_mask(
        self,
        confidence_mask: np.ndarray,
        frame_shape: tuple[int, ...],
        landmarks_px: np.ndarray,
        *,
        user_row: dict[str, Any] | None = None,
    ) -> np.ndarray:
        strong_threshold = self.profile.segmentation_confidence_threshold
        weak_threshold = max(0.08, strong_threshold * 0.42)

        strong_mask = np.where(
            confidence_mask >= strong_threshold,
            np.uint8(255),
            np.uint8(0),
        )
        if int(np.count_nonzero(strong_mask)) == 0:
            return confidence_mask

        weak_mask = np.where(
            confidence_mask >= weak_threshold,
            np.uint8(255),
            np.uint8(0),
        )
        if int(np.count_nonzero(weak_mask)) == 0:
            return confidence_mask

        seed_mask = self._build_segmentation_seed_mask(
            frame_shape,
            landmarks_px,
            user_row=user_row,
        )
        if seed_mask is None or int(np.count_nonzero(seed_mask)) == 0:
            return confidence_mask

        label_count, labels, _, _ = cv2.connectedComponentsWithStats(weak_mask, connectivity=8)
        if label_count <= 1:
            return confidence_mask

        keep_mask = np.zeros(weak_mask.shape, dtype=np.uint8)
        for label_index in range(1, label_count):
            component_mask = labels == label_index
            if not bool(np.any(seed_mask[component_mask] > 0)):
                continue
            if not bool(np.any(strong_mask[component_mask] > 0)):
                continue
            if int(np.count_nonzero(component_mask)) < 48:
                continue
            keep_mask[component_mask] = 255

        if int(np.count_nonzero(keep_mask)) == 0:
            return confidence_mask
        return confidence_mask * (keep_mask.astype(np.float32) / 255.0)

    def apply_with_metadata(
        self,
        frame_bgr: np.ndarray,
        landmarks_px: np.ndarray | None,
        *,
        user_row: dict[str, Any] | None = None,
        hair_confidence_mask: np.ndarray | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        if frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
            return frame_bgr, {}

        mask_kind = "landmark"
        confidence_mask: np.ndarray | None = None
        if hair_confidence_mask is not None:
            confidence_mask = self._normalize_confidence_mask(
                hair_confidence_mask,
                frame_bgr.shape[1],
                frame_bgr.shape[0],
            )
            if confidence_mask is not None:
                confidence_mask = np.clip(confidence_mask, 0.0, 1.0)
                if landmarks_px is not None:
                    confidence_mask = self._refine_segmentation_confidence_mask(
                        confidence_mask,
                        frame_bgr.shape,
                        landmarks_px,
                        user_row=user_row,
                    )
                mask_kind = "segmentation_full"

        segmentation_alpha_threshold = max(0.08, self.profile.segmentation_confidence_threshold * 0.42)
        if confidence_mask is not None:
            binary_mask = np.where(
                confidence_mask >= segmentation_alpha_threshold,
                np.uint8(255),
                np.uint8(0),
            )
            close_kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (
                    min(9, _odd_kernel(max(frame_bgr.shape[:2]) * 0.008, minimum=5)),
                    min(9, _odd_kernel(max(frame_bgr.shape[:2]) * 0.008, minimum=5)),
                ),
            )
            binary_mask = cv2.morphologyEx(binary_mask, cv2.MORPH_CLOSE, close_kernel, iterations=1)
        else:
            if landmarks_px is None:
                return frame_bgr, {}
            binary_mask = self._build_binary_mask(frame_bgr.shape, landmarks_px, user_row=user_row)
            if binary_mask is None:
                return frame_bgr, {}

        upper_region_mask: np.ndarray | None = None
        x, y, width, height = cv2.boundingRect(binary_mask)
        if width <= 1 or height <= 1:
            return frame_bgr, {}

        output = frame_bgr.copy()
        roi = output[y : y + height, x : x + width]
        mask_roi = binary_mask[y : y + height, x : x + width]
        work_scale = min(
            1.0,
            float(self.profile.max_work_dimension) / float(max(width, height)),
        )
        if work_scale < 0.999:
            work_width = max(1, int(round(width * work_scale)))
            work_height = max(1, int(round(height * work_scale)))
            roi_work = cv2.resize(roi, (work_width, work_height), interpolation=cv2.INTER_AREA)
            mask_work = cv2.resize(mask_roi, (work_width, work_height), interpolation=cv2.INTER_AREA)
        else:
            roi_work = roi
            mask_work = mask_roi
            work_width = width
            work_height = height

        tone_source_gray = cv2.cvtColor(roi_work, cv2.COLOR_BGR2GRAY)
        tone_source_gray = cv2.cvtColor(tone_source_gray, cv2.COLOR_GRAY2BGR)

        if confidence_mask is not None:
            confidence_roi = confidence_mask[y : y + height, x : x + width]
            binary_roi = binary_mask[y : y + height, x : x + width]
            if work_scale < 0.999:
                confidence_work = cv2.resize(
                    confidence_roi,
                    (work_width, work_height),
                    interpolation=cv2.INTER_LINEAR,
                )
                binary_work = cv2.resize(
                    binary_roi,
                    (work_width, work_height),
                    interpolation=cv2.INTER_NEAREST,
                )
            else:
                confidence_work = confidence_roi
                binary_work = binary_roi
            confidence_work = cv2.GaussianBlur(
                confidence_work,
                (0, 0),
                sigmaX=max(1.2, work_width * 0.026),
                sigmaY=max(1.2, work_height * 0.026),
            )
            alpha_work = (
                np.clip(
                    (confidence_work - segmentation_alpha_threshold)
                    / max(1e-6, 1.0 - segmentation_alpha_threshold),
                    0.0,
                    1.0,
                )[..., None]
                * self.profile.strength
            )
            binary_work_mask = binary_work >= 96
            alpha_work = np.where(binary_work_mask[..., None], alpha_work, np.float32(0.0))
            if float(alpha_work.max()) <= 0.01:
                return frame_bgr, {}
            tone_metadata = self._tone_metadata_from_roi(
                tone_source_gray,
                np.clip(confidence_work * 255.0, 0.0, 255.0).astype(np.uint8),
            )
            hair_mask_full = np.array(binary_mask, copy=True)
            head_prior_mask = (
                self._build_binary_mask(frame_bgr.shape, landmarks_px, user_row=user_row)
                if landmarks_px is not None
                else None
            )
            upper_region_mask = (
                self._build_upper_region_mask(frame_bgr.shape, landmarks_px, user_row=user_row)
                if landmarks_px is not None
                else self._build_upper_region_mask_fallback(frame_bgr.shape)
            )
            fringe_mask_full = (
                self._build_forehead_fringe_mask(frame_bgr.shape, landmarks_px, user_row=user_row)
                if landmarks_px is not None
                else None
            )
            if fringe_mask_full is None:
                fringe_mask_full = np.zeros(frame_bgr.shape[:2], dtype=np.uint8)
            fringe_mask_full = cv2.bitwise_and(hair_mask_full, fringe_mask_full)

            outer_bulk_mask_full = np.zeros(frame_bgr.shape[:2], dtype=np.uint8)
            if head_prior_mask is not None:
                dilation_kernel = cv2.getStructuringElement(
                    cv2.MORPH_ELLIPSE,
                    (
                        _odd_kernel(max(width, height) * 0.08, minimum=9),
                        _odd_kernel(max(width, height) * 0.08, minimum=9),
                    ),
                )
                head_prior_soft = cv2.dilate(head_prior_mask, dilation_kernel, iterations=1)
                outer_bulk_mask_full = cv2.bitwise_and(
                    hair_mask_full,
                    cv2.bitwise_not(head_prior_soft),
                )

            covered_mask_full = cv2.bitwise_and(
                hair_mask_full,
                cv2.bitwise_not(cv2.bitwise_or(fringe_mask_full, outer_bulk_mask_full)),
            )

            fringe_roi = fringe_mask_full[y : y + height, x : x + width]
            covered_roi = covered_mask_full[y : y + height, x : x + width]
            outer_bulk_roi = outer_bulk_mask_full[y : y + height, x : x + width]
            if work_scale < 0.999:
                fringe_work = cv2.resize(fringe_roi, (work_width, work_height), interpolation=cv2.INTER_LINEAR) >= 96
                covered_work = cv2.resize(covered_roi, (work_width, work_height), interpolation=cv2.INTER_LINEAR) >= 96
                outer_bulk_work = cv2.resize(outer_bulk_roi, (work_width, work_height), interpolation=cv2.INTER_LINEAR) >= 96
            else:
                fringe_work = fringe_roi >= 96
                covered_work = covered_roi >= 96
                outer_bulk_work = outer_bulk_roi >= 96

            zone_sigma = max(0.8, float(max(work_width, work_height)) * 0.012)
            fringe_zone_work = self._resize_mask_float(fringe_roi, work_width, work_height)
            covered_zone_work = self._resize_mask_float(covered_roi, work_width, work_height)
            outer_bulk_zone_work = self._resize_mask_float(outer_bulk_roi, work_width, work_height)
            if float(fringe_zone_work.max()) > 0.0:
                fringe_zone_work = np.clip(
                    cv2.GaussianBlur(fringe_zone_work, (0, 0), sigmaX=zone_sigma, sigmaY=zone_sigma),
                    0.0,
                    1.0,
                )
            if float(covered_zone_work.max()) > 0.0:
                covered_zone_work = np.clip(
                    cv2.GaussianBlur(covered_zone_work, (0, 0), sigmaX=zone_sigma, sigmaY=zone_sigma),
                    0.0,
                    1.0,
                )
            if float(outer_bulk_zone_work.max()) > 0.0:
                outer_bulk_zone_work = np.clip(
                    cv2.GaussianBlur(outer_bulk_zone_work, (0, 0), sigmaX=zone_sigma, sigmaY=zone_sigma),
                    0.0,
                    1.0,
                )
            boundary_feather_px = max(4, min(10, int(round(max(work_width, work_height) * 0.045))))
            scalp_zone_work = np.maximum(fringe_zone_work, covered_zone_work)
            scalp_transition_work = self._build_interior_transition_mask(
                np.where(scalp_zone_work >= 0.08, np.uint8(255), np.uint8(0)),
                feather_px=boundary_feather_px,
            )
            outer_bulk_transition_work = self._build_interior_transition_mask(
                np.where(outer_bulk_zone_work >= 0.08, np.uint8(255), np.uint8(0)),
                feather_px=max(3, int(round(boundary_feather_px * 0.8))),
            )

            blur_kernel = _odd_kernel(max(work_width, work_height) * self.profile.blur_kernel_scale, minimum=5)
            blurred_work = cv2.GaussianBlur(roi_work, (blur_kernel, blur_kernel), 0)
            blurred_hsv = cv2.cvtColor(blurred_work, cv2.COLOR_BGR2HSV).astype(np.float32)
            blurred_hsv[:, :, 1] *= max(0.38, 1.0 - (self.profile.desaturation * 0.72))
            if self.profile.brightness_lift > 0.0:
                blurred_hsv[:, :, 2] = np.clip(
                    blurred_hsv[:, :, 2] * (1.0 - self.profile.brightness_lift * 0.34)
                    + (255.0 * self.profile.brightness_lift * 0.42),
                    0.0,
                    255.0,
                )
            covered_soft_work = cv2.cvtColor(blurred_hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
            weakened_work = blurred_work.copy()
            scalp_matte_work: np.ndarray | None = None
            scalp_color: np.ndarray | None = None

            skin_color = self._estimate_skin_color(frame_bgr, landmarks_px)
            boundary_skin_color = self._estimate_lower_boundary_skin_color(
                frame_bgr,
                hair_mask_full,
                landmarks_px,
                reference_skin_color=skin_color,
            )
            scalp_source_color = boundary_skin_color if boundary_skin_color is not None else skin_color
            if scalp_source_color is not None:
                scalp_color = self._resolve_scalp_color(scalp_source_color)
                scalp_matte_work = np.empty_like(roi_work, dtype=np.uint8)
                scalp_matte_work[:] = np.clip(scalp_color, 0.0, 255.0).astype(np.uint8)
            if scalp_matte_work is not None and float(scalp_zone_work.max()) > 0.0:
                blurred_float = blurred_work.astype(np.float32)
                scalp_float = scalp_matte_work.astype(np.float32)
                scalp_mix = np.clip(
                    scalp_zone_work * (0.18 + 0.82 * scalp_transition_work),
                    0.0,
                    1.0,
                )
                scalp_target = (
                    blurred_float * (1.0 - scalp_mix[..., None])
                    + scalp_float * scalp_mix[..., None]
                )
                weakened_work = np.where(
                    scalp_zone_work[..., None] > 1e-3,
                    scalp_target,
                    weakened_work.astype(np.float32),
                )
                weakened_work = np.clip(weakened_work, 0.0, 255.0).astype(np.uint8)
                scalp_alpha_floor = (
                    np.float32(self.profile.strength)
                    * scalp_zone_work
                    * (0.42 + 0.46 * scalp_transition_work)
                )
                alpha_work = np.where(
                    scalp_zone_work[..., None] > 1e-3,
                    np.maximum(alpha_work, scalp_alpha_floor[..., None].astype(np.float32)),
                    alpha_work,
                )

            background_color = self._estimate_background_color(
                frame_bgr,
                outer_bulk_mask_full,
            )
            if scalp_matte_work is None and np.any(covered_work):
                covered_work_rgb = covered_soft_work.astype(np.float32)
                weakened_work = weakened_work.astype(np.float32)
                weakened_work[covered_work] = covered_work_rgb[covered_work]
                weakened_work = np.clip(weakened_work, 0, 255).astype(np.uint8)
                alpha_work = np.where(
                    covered_work[..., None],
                    np.maximum(alpha_work, np.float32(self.profile.strength * 0.82)),
                    alpha_work,
                )
            if background_color is not None and np.any(outer_bulk_work):
                bg_fill = np.empty_like(roi_work, dtype=np.float32)
                bg_fill[:] = background_color
                outer_bulk_target = bg_fill * 0.82 + blurred_work.astype(np.float32) * 0.18
                outer_bulk_mix = np.clip(
                    outer_bulk_zone_work * (0.74 + 0.26 * outer_bulk_transition_work),
                    0.0,
                    1.0,
                )
                weakened_work = np.where(
                    outer_bulk_zone_work[..., None] > 1e-3,
                    weakened_work.astype(np.float32) * (1.0 - outer_bulk_mix[..., None])
                    + outer_bulk_target * outer_bulk_mix[..., None],
                    weakened_work.astype(np.float32),
                )
                weakened_work = np.clip(weakened_work, 0, 255).astype(np.uint8)
                outer_alpha_floor = (
                    outer_bulk_zone_work
                    * np.float32(max(self.profile.strength, 0.95))
                    * (0.84 + 0.12 * outer_bulk_transition_work)
                )
                alpha_work = np.where(
                    outer_bulk_zone_work[..., None] > 1e-3,
                    np.maximum(alpha_work, outer_alpha_floor[..., None].astype(np.float32)),
                    alpha_work,
                )

            tone_metadata["suppression_mode"] = "segmentation_zones"
            tone_metadata["covered_mode"] = (
                "scalp_matte_only"
                if scalp_matte_work is not None
                else "soft_blur"
            )
            tone_metadata["boundary_feather_px"] = boundary_feather_px
            hair_pixel_count = max(1, int(np.count_nonzero(hair_mask_full)))
            tone_metadata["fringe_ratio"] = round(float(np.count_nonzero(fringe_mask_full)) / float(hair_pixel_count), 6)
            tone_metadata["outer_bulk_ratio"] = round(float(np.count_nonzero(outer_bulk_mask_full)) / float(hair_pixel_count), 6)
            tone_metadata["hair_binary_mask"] = hair_mask_full
            tone_metadata["outer_bulk_mask"] = outer_bulk_mask_full
            if upper_region_mask is not None:
                tone_metadata["upper_region_mask"] = upper_region_mask
            if background_color is not None:
                tone_metadata["background_color"] = np.asarray(background_color, dtype=np.float32)
            if scalp_color is not None:
                tone_metadata["scalp_color"] = np.asarray(scalp_color, dtype=np.float32)
            if self.profile.bald_test_mode:
                matte_work = blurred_work.astype(np.float32)
                skin_color = self._estimate_skin_color(frame_bgr, landmarks_px)
                if skin_color is None:
                    skin_color = self._estimate_skin_color_fallback(frame_bgr)
                if skin_color is not None:
                    scalp_kernel = _odd_kernel(max(work_width, work_height) * (self.profile.blur_kernel_scale * 1.8), minimum=9)
                    scalp_lowfreq = cv2.GaussianBlur(roi_work, (scalp_kernel, scalp_kernel), 0)
                    scalp_hsv = cv2.cvtColor(scalp_lowfreq, cv2.COLOR_BGR2HSV).astype(np.float32)
                    scalp_hsv[:, :, 1] *= 0.06
                    scalp_hsv[:, :, 2] = np.clip(
                        scalp_hsv[:, :, 2] * 0.96 + 255.0 * 0.08,
                        0.0,
                        255.0,
                    )
                    ambient_scalp = cv2.cvtColor(scalp_hsv.astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32)
                    skin_fill = np.empty_like(matte_work, dtype=np.float32)
                    skin_fill[:] = skin_color
                    local_luma = cv2.cvtColor(scalp_lowfreq, cv2.COLOR_BGR2GRAY).astype(np.float32)
                    active_region = confidence_work >= segmentation_alpha_threshold
                    if bool(np.any(active_region)):
                        mean_luma = float(local_luma[active_region].mean())
                    else:
                        mean_luma = float(local_luma.mean())
                    mean_luma = max(mean_luma, 1.0)
                    shade = np.clip(local_luma / mean_luma, 0.94, 1.18)[..., None]
                    skin_shaded = np.clip(skin_fill * shade, 0.0, 255.0)
                    matte_work = ambient_scalp * 0.04 + skin_shaded * 0.96
                    matte_work = np.clip(matte_work * 1.03 + 4.0, 0.0, 255.0)
                    weakened_work = np.clip(matte_work, 0.0, 255.0).astype(np.uint8)
                active_mask_u8 = np.where(
                    binary_work_mask,
                    np.uint8(255),
                    np.uint8(0),
                )
                if int(np.count_nonzero(active_mask_u8)) > 0:
                    distance = cv2.distanceTransform(active_mask_u8, cv2.DIST_L2, 5)
                    distance_norm = distance / max(1.0, float(distance.max()))
                    scalp_alpha = np.where(
                        active_mask_u8 > 0,
                        np.clip(0.84 + distance_norm * 0.15, 0.0, 0.995),
                        0.0,
                    ).astype(np.float32)
                else:
                    scalp_alpha = binary_work_mask.astype(np.float32)
                scalp_alpha = np.where(binary_work_mask, scalp_alpha, np.float32(0.0))
                alpha_work = np.maximum(alpha_work, (scalp_alpha[..., None] * 0.985).astype(np.float32))
                alpha_work = np.where(binary_work_mask[..., None], alpha_work, np.float32(0.0))
                tone_metadata["suppression_mode"] = "bald_test_segmentation_only"
                tone_metadata["covered_mode"] = "scalp_matte"
        else:
            mask_work = cv2.GaussianBlur(
                mask_work,
                (0, 0),
                sigmaX=max(2.0, work_width * 0.08),
                sigmaY=max(2.0, work_height * 0.10),
            )
            alpha_work = (mask_work.astype(np.float32) / 255.0)[..., None] * self.profile.strength
            if float(alpha_work.max()) <= 0.01:
                return frame_bgr, {}

            blur_kernel = _odd_kernel(max(work_width, work_height) * self.profile.blur_kernel_scale, minimum=5)
            blurred_work = cv2.GaussianBlur(roi_work, (blur_kernel, blur_kernel), 0)
            grayscale_work = cv2.cvtColor(blurred_work, cv2.COLOR_BGR2GRAY)
            grayscale_work = cv2.cvtColor(grayscale_work, cv2.COLOR_GRAY2BGR)
            tone_metadata = self._tone_metadata_from_roi(grayscale_work, mask_work)
            weakened_work = cv2.addWeighted(
                blurred_work,
                1.0 - self.profile.desaturation,
                grayscale_work,
                self.profile.desaturation,
                0.0,
            )
            if self.profile.brightness_lift > 0.0:
                weakened_work = cv2.addWeighted(
                    weakened_work,
                    1.0 - self.profile.brightness_lift,
                    np.full_like(weakened_work, 255),
                    self.profile.brightness_lift,
                    0.0,
                )

        metadata: dict[str, Any] = dict(tone_metadata)
        metadata["mask_kind"] = mask_kind

        if work_scale < 0.999:
            weakened = cv2.resize(weakened_work, (width, height), interpolation=cv2.INTER_LINEAR)
            if confidence_mask is not None:
                alpha = (
                    cv2.resize(alpha_work[:, :, 0], (width, height), interpolation=cv2.INTER_LINEAR)
                )[..., None]
                alpha = np.where(mask_roi[..., None] >= 96, alpha, np.float32(0.0))
            else:
                alpha = (
                    cv2.resize(mask_work, (width, height), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0
                )[..., None] * self.profile.strength
        else:
            weakened = weakened_work
            alpha = alpha_work
            if confidence_mask is not None:
                alpha = np.where(mask_roi[..., None] >= 96, alpha, np.float32(0.0))

        blended = (
            roi.astype(np.float32) * (1.0 - alpha)
            + weakened.astype(np.float32) * alpha
        )
        output[y : y + height, x : x + width] = np.clip(blended, 0, 255).astype(np.uint8)
        return output, metadata

    def apply(
        self,
        frame_bgr: np.ndarray,
        landmarks_px: np.ndarray | None,
        *,
        user_row: dict[str, Any] | None = None,
        hair_confidence_mask: np.ndarray | None = None,
    ) -> np.ndarray:
        output, _ = self.apply_with_metadata(
            frame_bgr,
            landmarks_px,
            user_row=user_row,
            hair_confidence_mask=hair_confidence_mask,
        )
        return output
