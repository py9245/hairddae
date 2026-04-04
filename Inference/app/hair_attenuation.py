from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
import time
from typing import Any

import cv2
import numpy as np

from cv2_cuda_utils import (
    opencv_add_weighted,
    opencv_bitwise_and,
    opencv_bitwise_not,
    opencv_bitwise_or,
    opencv_cvt_color,
    opencv_dilate,
    opencv_erode,
    opencv_gaussian_blur,
    opencv_resize,
)
from app.face_tracking import FACE_LANDMARK_INDEX

LEFT_EYE_CONTOUR_INDICES = (
    33,
    246,
    161,
    160,
    159,
    158,
    157,
    173,
    133,
    155,
    154,
    153,
    145,
    144,
    163,
    7,
)
RIGHT_EYE_CONTOUR_INDICES = (
    263,
    466,
    388,
    387,
    386,
    385,
    384,
    398,
    362,
    382,
    381,
    380,
    374,
    373,
    390,
    249,
)


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
    preserve_eyes_enabled: bool = False
    disable_fringe_suppression: bool = False
    disable_covered_suppression: bool = False
    disable_outer_bulk_suppression: bool = False
    luma_preserving_scalp_enabled: bool = True


@dataclass(frozen=True)
class HairColorAnalysisPlane:
    frame_bgr: np.ndarray
    frame_ycrcb: np.ndarray
    frame_hsv: np.ndarray
    landmarks_px: np.ndarray | None
    hair_mask: np.ndarray | None
    outer_bulk_mask: np.ndarray | None
    fringe_mask: np.ndarray | None
    scale: float


@dataclass
class HairColorEstimateCacheEntry:
    session_id: str | None
    frame_shape: tuple[int, int]
    bbox_center: tuple[float, float]
    bbox_size: tuple[float, float]
    pose: tuple[float, float, float]
    forehead_luma: float | None
    skin_color: np.ndarray | None
    boundary_skin_color: np.ndarray | None
    background_color: np.ndarray | None
    scalp_color: np.ndarray | None
    remaining_reuse_frames: int


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
        preserve_eyes_enabled: bool = False,
        disable_fringe_suppression: bool = False,
        disable_covered_suppression: bool = False,
        disable_outer_bulk_suppression: bool = False,
        luma_preserving_scalp_enabled: bool = True,
    ) -> None:
        self.profile = HairAttenuationProfile(
            segmentation_confidence_threshold=float(np.clip(segmentation_confidence_threshold, 0.05, 0.95)),
            strength=float(np.clip(strength, 0.0, 1.0)),
            desaturation=float(np.clip(desaturation, 0.0, 1.0)),
            brightness_lift=float(np.clip(brightness_lift, 0.0, 0.2)),
            blur_kernel_scale=max(0.01, float(blur_kernel_scale)),
            max_work_dimension=max(96, int(max_work_dimension)),
            bald_test_mode=bool(bald_test_mode),
            preserve_eyes_enabled=bool(preserve_eyes_enabled),
            disable_fringe_suppression=bool(disable_fringe_suppression),
            disable_covered_suppression=bool(disable_covered_suppression),
            disable_outer_bulk_suppression=bool(disable_outer_bulk_suppression),
            luma_preserving_scalp_enabled=bool(luma_preserving_scalp_enabled),
        )
        self._color_cache_lock = Lock()
        self._color_cache: HairColorEstimateCacheEntry | None = None

    def close(self) -> None:
        with self._color_cache_lock:
            self._color_cache = None
        return None

    @staticmethod
    def _copy_optional_color(color: np.ndarray | None) -> np.ndarray | None:
        if color is None:
            return None
        return np.array(color, dtype=np.float32, copy=True)

    @staticmethod
    def _cache_session_id(user_row: dict[str, Any] | None) -> str | None:
        session_id = (user_row or {}).get("_apply_session_id")
        if session_id in (None, ""):
            return None
        return str(session_id)

    @staticmethod
    def _cache_face_bbox(user_row: dict[str, Any] | None) -> tuple[float, float, float, float] | None:
        face_bbox = (user_row or {}).get("face_bbox")
        if not isinstance(face_bbox, dict):
            return None
        try:
            x = float(face_bbox["x"])
            y = float(face_bbox["y"])
            w = float(face_bbox["w"])
            h = float(face_bbox["h"])
        except Exception:
            return None
        if w <= 0.0 or h <= 0.0:
            return None
        return x, y, w, h

    @staticmethod
    def _cache_pose(user_row: dict[str, Any] | None) -> tuple[float, float, float]:
        pose = (user_row or {}).get("pose")
        if not isinstance(pose, dict):
            return 0.0, 0.0, 0.0
        return (
            float(pose.get("yaw_float", pose.get("yaw_1deg", 0.0)) or 0.0),
            float(pose.get("pitch_float", pose.get("pitch_1deg", 0.0)) or 0.0),
            float(pose.get("roll_float", pose.get("roll_1deg", 0.0)) or 0.0),
        )

    @staticmethod
    def _cache_forehead_luma(
        analysis_plane: HairColorAnalysisPlane,
        *,
        user_row: dict[str, Any] | None,
    ) -> float | None:
        bbox = HairAttenuator._cache_face_bbox(user_row)
        if bbox is None:
            return None
        x, y, w, h = bbox
        height, width = analysis_plane.frame_ycrcb.shape[:2]
        scale = float(analysis_plane.scale)
        x0 = max(0, int(round((x + w * 0.22) * scale)))
        x1 = min(width, int(round((x + w * 0.78) * scale)))
        y0 = max(0, int(round(y * scale)))
        y1 = min(height, int(round((y + h * 0.34) * scale)))
        if x1 - x0 < 2 or y1 - y0 < 2:
            return None
        patch = analysis_plane.frame_ycrcb[y0:y1, x0:x1, 0]
        if patch.size == 0:
            return None
        return float(np.mean(patch))

    def _load_cached_color_estimates(
        self,
        *,
        user_row: dict[str, Any] | None,
        frame_shape: tuple[int, int],
        analysis_plane: HairColorAnalysisPlane,
    ) -> tuple[np.ndarray | None, np.ndarray | None, np.ndarray | None, np.ndarray | None] | None:
        bbox = self._cache_face_bbox(user_row)
        if bbox is None:
            return None
        session_id = self._cache_session_id(user_row)
        pose = self._cache_pose(user_row)
        forehead_luma = self._cache_forehead_luma(analysis_plane, user_row=user_row)
        center_x = bbox[0] + bbox[2] * 0.5
        center_y = bbox[1] + bbox[3] * 0.5
        with self._color_cache_lock:
            entry = self._color_cache
            if entry is None or entry.remaining_reuse_frames <= 0:
                return None
            if entry.session_id != session_id or entry.frame_shape != frame_shape:
                return None
            center_dx_norm = abs(center_x - entry.bbox_center[0]) / max(1.0, entry.bbox_size[0])
            center_dy_norm = abs(center_y - entry.bbox_center[1]) / max(1.0, entry.bbox_size[1])
            size_dw_norm = abs(bbox[2] - entry.bbox_size[0]) / max(1.0, entry.bbox_size[0])
            size_dh_norm = abs(bbox[3] - entry.bbox_size[1]) / max(1.0, entry.bbox_size[1])
            pose_gap = max(abs(pose[i] - entry.pose[i]) for i in range(3))
            if center_dx_norm > 0.04 or center_dy_norm > 0.04:
                return None
            if size_dw_norm > 0.05 or size_dh_norm > 0.05:
                return None
            if pose_gap > 4.0:
                return None
            if forehead_luma is not None and entry.forehead_luma is not None and abs(forehead_luma - entry.forehead_luma) > 6.0:
                return None
            entry.remaining_reuse_frames -= 1
            return (
                self._copy_optional_color(entry.skin_color),
                self._copy_optional_color(entry.boundary_skin_color),
                self._copy_optional_color(entry.background_color),
                self._copy_optional_color(entry.scalp_color),
            )

    def _store_cached_color_estimates(
        self,
        *,
        user_row: dict[str, Any] | None,
        frame_shape: tuple[int, int],
        analysis_plane: HairColorAnalysisPlane,
        skin_color: np.ndarray | None,
        boundary_skin_color: np.ndarray | None,
        background_color: np.ndarray | None,
        scalp_color: np.ndarray | None,
    ) -> None:
        bbox = self._cache_face_bbox(user_row)
        if bbox is None:
            return
        center_x = bbox[0] + bbox[2] * 0.5
        center_y = bbox[1] + bbox[3] * 0.5
        entry = HairColorEstimateCacheEntry(
            session_id=self._cache_session_id(user_row),
            frame_shape=frame_shape,
            bbox_center=(center_x, center_y),
            bbox_size=(bbox[2], bbox[3]),
            pose=self._cache_pose(user_row),
            forehead_luma=self._cache_forehead_luma(analysis_plane, user_row=user_row),
            skin_color=self._copy_optional_color(skin_color),
            boundary_skin_color=self._copy_optional_color(boundary_skin_color),
            background_color=self._copy_optional_color(background_color),
            scalp_color=self._copy_optional_color(scalp_color),
            remaining_reuse_frames=3,
        )
        with self._color_cache_lock:
            self._color_cache = entry

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
            mask = opencv_resize(mask, (width, height), interpolation=cv2.INTER_LINEAR, min_pixels=8_192)
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
    def _reference_skin_channels(
        reference_skin_color: np.ndarray | None,
    ) -> tuple[np.ndarray | None, np.ndarray | None]:
        if reference_skin_color is None:
            return None, None
        reference = np.clip(
            np.asarray(reference_skin_color, dtype=np.float32).reshape(-1)[:3],
            0.0,
            255.0,
        ).astype(np.uint8)
        if reference.size != 3:
            return None, None
        reference_ycrcb = opencv_cvt_color(reference.reshape(1, 1, 3), cv2.COLOR_BGR2YCrCb, min_pixels=0).reshape(3).astype(np.float32)
        reference_hsv = opencv_cvt_color(reference.reshape(1, 1, 3), cv2.COLOR_BGR2HSV, min_pixels=0).reshape(3).astype(np.float32)
        return reference_ycrcb, reference_hsv

    @staticmethod
    def _rescale_landmarks(
        landmarks_px: np.ndarray | None,
        scale: float,
    ) -> np.ndarray | None:
        if landmarks_px is None:
            return None
        return np.rint(landmarks_px.astype(np.float32) * float(scale)).astype(np.int32)

    @staticmethod
    def _translate_landmarks(
        landmarks_px: np.ndarray | None,
        *,
        offset_x: int,
        offset_y: int,
    ) -> np.ndarray | None:
        if landmarks_px is None:
            return None
        shifted = landmarks_px.astype(np.float32).copy()
        shifted[:, 0] -= float(offset_x)
        shifted[:, 1] -= float(offset_y)
        return np.rint(shifted).astype(np.int32)

    def _build_color_analysis_plane(
        self,
        frame_bgr: np.ndarray,
        *,
        landmarks_px: np.ndarray | None,
        hair_mask: np.ndarray | None,
        outer_bulk_mask: np.ndarray | None,
        fringe_mask: np.ndarray | None,
    ) -> HairColorAnalysisPlane:
        height, width = frame_bgr.shape[:2]
        analysis_max_dimension = min(128, max(96, self.profile.max_work_dimension))
        scale = min(1.0, float(analysis_max_dimension) / float(max(height, width)))
        if scale < 0.999:
            analysis_width = max(1, int(round(width * scale)))
            analysis_height = max(1, int(round(height * scale)))
            analysis_frame = opencv_resize(frame_bgr, (analysis_width, analysis_height), interpolation=cv2.INTER_AREA, min_pixels=0)
            analysis_hair_mask = (
                opencv_resize(hair_mask, (analysis_width, analysis_height), interpolation=cv2.INTER_NEAREST, min_pixels=0)
                if hair_mask is not None
                else None
            )
            analysis_outer_bulk_mask = (
                opencv_resize(outer_bulk_mask, (analysis_width, analysis_height), interpolation=cv2.INTER_NEAREST, min_pixels=0)
                if outer_bulk_mask is not None
                else None
            )
            analysis_fringe_mask = (
                opencv_resize(fringe_mask, (analysis_width, analysis_height), interpolation=cv2.INTER_NEAREST, min_pixels=0)
                if fringe_mask is not None
                else None
            )
            analysis_landmarks = self._rescale_landmarks(landmarks_px, scale)
        else:
            analysis_frame = frame_bgr
            analysis_hair_mask = hair_mask
            analysis_outer_bulk_mask = outer_bulk_mask
            analysis_fringe_mask = fringe_mask
            analysis_landmarks = landmarks_px
        return HairColorAnalysisPlane(
            frame_bgr=analysis_frame,
            frame_ycrcb=opencv_cvt_color(analysis_frame, cv2.COLOR_BGR2YCrCb, min_pixels=0),
            frame_hsv=opencv_cvt_color(analysis_frame, cv2.COLOR_BGR2HSV, min_pixels=0),
            landmarks_px=analysis_landmarks,
            hair_mask=analysis_hair_mask,
            outer_bulk_mask=analysis_outer_bulk_mask,
            fringe_mask=analysis_fringe_mask,
            scale=float(scale),
        )

    @staticmethod
    def _build_skin_candidate_mask(
        pixels_bgr: np.ndarray,
        *,
        reference_skin_color: np.ndarray | None = None,
        min_luma: float = 42.0,
        chroma_distance_limit: float = 34.0,
        pixels_ycrcb: np.ndarray | None = None,
        pixels_hsv: np.ndarray | None = None,
        reference_skin_ycrcb: np.ndarray | None = None,
        reference_skin_hsv: np.ndarray | None = None,
    ) -> np.ndarray:
        pixels = np.asarray(pixels_bgr, dtype=np.uint8)
        if pixels.ndim < 2 or pixels.shape[-1] != 3:
            return np.zeros(pixels.shape[:-1], dtype=bool)

        original_shape = pixels.shape[:-1]
        flat = pixels.reshape(-1, 3)
        if flat.size == 0:
            return np.zeros(original_shape, dtype=bool)

        if pixels_ycrcb is not None and np.asarray(pixels_ycrcb).shape == pixels.shape:
            ycrcb = np.asarray(pixels_ycrcb, dtype=np.float32).reshape(-1, 3)
        else:
            flat_image = flat.reshape(-1, 1, 3)
            ycrcb = opencv_cvt_color(flat_image, cv2.COLOR_BGR2YCrCb, min_pixels=0).reshape(-1, 3).astype(np.float32)
        if pixels_hsv is not None and np.asarray(pixels_hsv).shape == pixels.shape:
            hsv = np.asarray(pixels_hsv, dtype=np.float32).reshape(-1, 3)
        else:
            flat_image = flat.reshape(-1, 1, 3)
            hsv = opencv_cvt_color(flat_image, cv2.COLOR_BGR2HSV, min_pixels=0).reshape(-1, 3).astype(np.float32)

        y_channel = ycrcb[:, 0]
        cr_channel = ycrcb[:, 1]
        cb_channel = ycrcb[:, 2]
        hue_channel = hsv[:, 0]
        sat_channel = hsv[:, 1]
        val_channel = hsv[:, 2]

        keep_mask = (
            (y_channel >= min_luma)
            & (val_channel >= max(48.0, min_luma + 4.0))
            & (cr_channel >= 126.0)
            & (cr_channel <= 180.0)
            & (cb_channel >= 76.0)
            & (cb_channel <= 136.0)
            & (sat_channel >= 16.0)
            & (sat_channel <= 170.0)
        )

        hue_keep = (hue_channel <= 25.0) | (hue_channel >= 170.0) | (sat_channel <= 42.0)
        keep_mask &= hue_keep

        if reference_skin_color is not None:
            if reference_skin_ycrcb is None or reference_skin_hsv is None:
                reference_skin_ycrcb, reference_skin_hsv = HairAttenuator._reference_skin_channels(reference_skin_color)
            if reference_skin_ycrcb is not None and reference_skin_hsv is not None:
                chroma_distance = np.abs(cr_channel - reference_skin_ycrcb[1]) + np.abs(cb_channel - reference_skin_ycrcb[2])
                keep_mask &= chroma_distance <= chroma_distance_limit
                keep_mask &= y_channel >= max(min_luma, float(reference_skin_ycrcb[0]) - 12.0)
                keep_mask &= val_channel >= max(52.0, float(reference_skin_hsv[2]) - 18.0)

        return keep_mask.reshape(original_shape)

    @staticmethod
    def _sample_patch_skin_median(
        frame_bgr: np.ndarray,
        center_x: float,
        center_y: float,
        radius: int,
        *,
        reference_skin_color: np.ndarray | None = None,
        frame_ycrcb: np.ndarray | None = None,
        frame_hsv: np.ndarray | None = None,
        reference_skin_ycrcb: np.ndarray | None = None,
        reference_skin_hsv: np.ndarray | None = None,
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
        patch_ycrcb = frame_ycrcb[y0:y1, x0:x1] if frame_ycrcb is not None else None
        patch_hsv = frame_hsv[y0:y1, x0:x1] if frame_hsv is not None else None

        keep_mask = HairAttenuator._build_skin_candidate_mask(
            patch,
            reference_skin_color=reference_skin_color,
            min_luma=42.0,
            chroma_distance_limit=34.0,
            pixels_ycrcb=patch_ycrcb,
            pixels_hsv=patch_hsv,
            reference_skin_ycrcb=reference_skin_ycrcb,
            reference_skin_hsv=reference_skin_hsv,
        )

        filtered = patch[keep_mask]
        if filtered.size < 24:
            patch_pixels = patch.reshape(-1, 3)
            patch_pixels_ycrcb = patch_ycrcb.reshape(-1, 1, 3) if patch_ycrcb is not None else None
            patch_pixels_hsv = patch_hsv.reshape(-1, 1, 3) if patch_hsv is not None else None
            flat_keep_mask = HairAttenuator._build_skin_candidate_mask(
                patch_pixels.reshape(-1, 1, 3),
                reference_skin_color=reference_skin_color,
                min_luma=40.0,
                chroma_distance_limit=40.0,
                pixels_ycrcb=patch_pixels_ycrcb,
                pixels_hsv=patch_pixels_hsv,
                reference_skin_ycrcb=reference_skin_ycrcb,
                reference_skin_hsv=reference_skin_hsv,
            ).reshape(-1)
            filtered = patch_pixels[flat_keep_mask]
        if filtered.size < 24:
            return np.median(patch.reshape(-1, 3), axis=0).astype(np.float32)
        return np.median(filtered.reshape(-1, 3), axis=0).astype(np.float32)

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
        *,
        frame_ycrcb: np.ndarray | None = None,
        frame_hsv: np.ndarray | None = None,
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
        patch_radius = max(3, int(round(face_width * 0.045)))

        sample_points = [
            (float(forehead_mid[0]), float(forehead_mid[1] + face_height * 0.14)),
            (float(forehead_mid[0] - face_width * 0.11), float(forehead_mid[1] + face_height * 0.18)),
            (float(forehead_mid[0] + face_width * 0.11), float(forehead_mid[1] + face_height * 0.18)),
            (float(left_temple[0] + face_width * 0.12), float(left_temple[1] + face_height * 0.14)),
            (float(right_temple[0] - face_width * 0.12), float(right_temple[1] + face_height * 0.14)),
            (float(lower_left[0] + face_width * 0.10), float(forehead_mid[1] + face_height * 0.44)),
            (float(lower_right[0] - face_width * 0.10), float(forehead_mid[1] + face_height * 0.44)),
        ]

        reference_skin_color = self._estimate_skin_color_fallback(frame_bgr)
        reference_skin_ycrcb, reference_skin_hsv = self._reference_skin_channels(reference_skin_color)
        samples = [
            sample
            for sample in (
                self._sample_patch_skin_median(
                    frame_bgr,
                    point_x,
                    point_y,
                    patch_radius,
                    reference_skin_color=reference_skin_color,
                    frame_ycrcb=frame_ycrcb,
                    frame_hsv=frame_hsv,
                    reference_skin_ycrcb=reference_skin_ycrcb,
                    reference_skin_hsv=reference_skin_hsv,
                )
                for point_x, point_y in sample_points
            )
            if sample is not None
        ]
        if not samples:
            return reference_skin_color
        return np.median(np.stack(samples, axis=0), axis=0).astype(np.float32)

    @staticmethod
    def _resolve_scalp_color(skin_color: np.ndarray) -> np.ndarray:
        color = np.asarray(skin_color, dtype=np.float32).reshape(-1)
        if color.size < 3:
            return np.array([160.0, 180.0, 205.0], dtype=np.float32)
        return np.clip(color[:3], 0.0, 255.0).astype(np.float32)

    @staticmethod
    def _blend_scalp_reference_color(
        skin_color: np.ndarray | None,
        boundary_skin_color: np.ndarray | None,
    ) -> np.ndarray | None:
        if skin_color is None and boundary_skin_color is None:
            return None
        if skin_color is None:
            return np.clip(np.asarray(boundary_skin_color, dtype=np.float32).reshape(-1)[:3], 0.0, 255.0).astype(np.float32)
        if boundary_skin_color is None:
            return np.clip(np.asarray(skin_color, dtype=np.float32).reshape(-1)[:3], 0.0, 255.0).astype(np.float32)

        skin = np.clip(np.asarray(skin_color, dtype=np.float32).reshape(-1)[:3], 0.0, 255.0).astype(np.float32)
        boundary = np.clip(np.asarray(boundary_skin_color, dtype=np.float32).reshape(-1)[:3], 0.0, 255.0).astype(np.float32)

        skin_ycrcb = opencv_cvt_color(skin.reshape(1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2YCrCb, min_pixels=0).reshape(3).astype(np.float32)
        boundary_ycrcb = opencv_cvt_color(boundary.reshape(1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2YCrCb, min_pixels=0).reshape(3).astype(np.float32)
        luma_gap = float(boundary_ycrcb[0] - skin_ycrcb[0])
        chroma_gap = float(abs(boundary_ycrcb[1] - skin_ycrcb[1]) + abs(boundary_ycrcb[2] - skin_ycrcb[2]))

        # Prefer the cleaned boundary samples, but fall back toward face skin if
        # the boundary samples still look too shadowed or chromatically off.
        boundary_weight = 0.62
        if luma_gap < -18.0:
            boundary_weight = 0.28
        elif luma_gap < -10.0:
            boundary_weight = 0.42
        elif luma_gap < -4.0:
            boundary_weight = 0.52
        if chroma_gap > 18.0:
            boundary_weight *= 0.65
        elif chroma_gap > 10.0:
            boundary_weight *= 0.82

        blended = skin * (1.0 - boundary_weight) + boundary * boundary_weight
        return np.clip(blended, 0.0, 255.0).astype(np.float32)

    @staticmethod
    def _compose_luma_preserving_scalp_matte(
        lowfreq_bgr: np.ndarray,
        scalp_color: np.ndarray,
        *,
        active_region: np.ndarray | None = None,
    ) -> np.ndarray:
        scalp_color_float = np.clip(
            np.asarray(scalp_color, dtype=np.float32).reshape(-1)[:3],
            0.0,
            255.0,
        ).astype(np.float32)
        scalp_fill = np.empty_like(lowfreq_bgr, dtype=np.float32)
        scalp_fill[:] = scalp_color_float

        local_luma = opencv_cvt_color(
            lowfreq_bgr,
            cv2.COLOR_BGR2GRAY,
            min_pixels=8_192,
        ).astype(np.float32)
        if active_region is not None and bool(np.any(active_region)):
            mean_luma = float(local_luma[active_region].mean())
        else:
            mean_luma = float(local_luma.mean())
        mean_luma = max(mean_luma, 1.0)

        shade = np.clip(local_luma / mean_luma, 0.96, 1.08)[..., None]
        scalp_shaded = np.clip(scalp_fill * shade, 0.0, 255.0)
        return scalp_shaded.astype(np.uint8)

    def _estimate_lower_boundary_skin_color(
        self,
        frame_bgr: np.ndarray,
        hair_mask: np.ndarray,
        landmarks_px: np.ndarray | None,
        *,
        reference_skin_color: np.ndarray | None = None,
        frame_ycrcb: np.ndarray | None = None,
        frame_hsv: np.ndarray | None = None,
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
        eroded = opencv_erode(active, edge_kernel, iterations=1, min_pixels=24_000)
        lower_edge = cv2.subtract(active, eroded)
        if int(np.count_nonzero(lower_edge)) == 0:
            return None

        band_px = max(2, min(16, int(round(mask_height * 0.08))))
        below_band = np.zeros_like(active)
        for offset in range(1, band_px + 1):
            below_band[offset:, :] = np.maximum(below_band[offset:, :], lower_edge[:-offset, :])
        below_band = opencv_bitwise_and(below_band, opencv_bitwise_not(active))

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
            y1 = int(np.clip(round(forehead_mid[1] + face_height * 0.26), 0, height))
            if x1 > x0 and y1 > y0:
                forehead_band[y0:y1, x0:x1] = 255
                below_band = opencv_bitwise_and(below_band, forehead_band)

        if int(np.count_nonzero(below_band)) < 24:
            return None

        candidate_pixels = frame_bgr[below_band > 0]
        if candidate_pixels.size < 72:
            return None

        candidate_pixels = candidate_pixels.reshape(-1, 3).astype(np.uint8)
        candidate_ycrcb = frame_ycrcb[below_band > 0].reshape(-1, 3) if frame_ycrcb is not None else None
        candidate_hsv = frame_hsv[below_band > 0].reshape(-1, 3) if frame_hsv is not None else None
        reference_skin_ycrcb, reference_skin_hsv = self._reference_skin_channels(reference_skin_color)
        keep_mask = HairAttenuator._build_skin_candidate_mask(
            candidate_pixels.reshape(-1, 1, 3),
            reference_skin_color=reference_skin_color,
            min_luma=50.0,
            chroma_distance_limit=30.0,
            pixels_ycrcb=candidate_ycrcb.reshape(-1, 1, 3) if candidate_ycrcb is not None else None,
            pixels_hsv=candidate_hsv.reshape(-1, 1, 3) if candidate_hsv is not None else None,
            reference_skin_ycrcb=reference_skin_ycrcb,
            reference_skin_hsv=reference_skin_hsv,
        ).reshape(-1)

        filtered = candidate_pixels[keep_mask]
        if filtered.shape[0] < 24:
            relaxed_keep = HairAttenuator._build_skin_candidate_mask(
                candidate_pixels.reshape(-1, 1, 3),
                reference_skin_color=reference_skin_color,
                min_luma=44.0,
                chroma_distance_limit=40.0,
                pixels_ycrcb=candidate_ycrcb.reshape(-1, 1, 3) if candidate_ycrcb is not None else None,
                pixels_hsv=candidate_hsv.reshape(-1, 1, 3) if candidate_hsv is not None else None,
                reference_skin_ycrcb=reference_skin_ycrcb,
                reference_skin_hsv=reference_skin_hsv,
            ).reshape(-1)
            filtered = candidate_pixels[relaxed_keep]
        if filtered.shape[0] < 24:
            filtered = candidate_pixels
        if filtered.shape[0] < 24:
            return None

        filtered_ycrcb = opencv_cvt_color(
            filtered.reshape(-1, 1, 3),
            cv2.COLOR_BGR2YCrCb,
            min_pixels=0,
        ).reshape(-1, 3).astype(np.float32)
        median_ycrcb = np.median(filtered_ycrcb, axis=0).astype(np.float32)
        deviation = (
            np.abs(filtered_ycrcb[:, 1] - median_ycrcb[1])
            + np.abs(filtered_ycrcb[:, 2] - median_ycrcb[2])
            + np.abs(filtered_ycrcb[:, 0] - median_ycrcb[0]) * 0.25
        )
        deviation_limit = max(10.0, float(np.percentile(deviation, 72.0)))
        robust_filtered = filtered[deviation <= deviation_limit]
        if robust_filtered.shape[0] >= 16:
            filtered = robust_filtered

        return np.median(filtered.astype(np.float32), axis=0).astype(np.float32)

    def _sample_patch_skin_median_with_valid_mask(
        self,
        frame_bgr: np.ndarray,
        valid_mask: np.ndarray,
        center_x: float,
        center_y: float,
        radius: int,
        *,
        reference_skin_color: np.ndarray | None = None,
        frame_ycrcb: np.ndarray | None = None,
        frame_hsv: np.ndarray | None = None,
        reference_skin_ycrcb: np.ndarray | None = None,
        reference_skin_hsv: np.ndarray | None = None,
    ) -> np.ndarray | None:
        height, width = frame_bgr.shape[:2]
        if radius <= 0 or valid_mask.shape[:2] != frame_bgr.shape[:2]:
            return None
        x0 = max(0, int(round(center_x)) - radius)
        y0 = max(0, int(round(center_y)) - radius)
        x1 = min(width, int(round(center_x)) + radius + 1)
        y1 = min(height, int(round(center_y)) + radius + 1)
        if x1 - x0 < 3 or y1 - y0 < 3:
            return None

        patch = frame_bgr[y0:y1, x0:x1]
        patch_valid = valid_mask[y0:y1, x0:x1] > 0
        if patch.size == 0 or int(np.count_nonzero(patch_valid)) < 12:
            return None
        patch_ycrcb = frame_ycrcb[y0:y1, x0:x1] if frame_ycrcb is not None else None
        patch_hsv = frame_hsv[y0:y1, x0:x1] if frame_hsv is not None else None

        skin_candidates = self._build_skin_candidate_mask(
            patch,
            reference_skin_color=reference_skin_color,
            min_luma=46.0,
            chroma_distance_limit=28.0,
            pixels_ycrcb=patch_ycrcb,
            pixels_hsv=patch_hsv,
            reference_skin_ycrcb=reference_skin_ycrcb,
            reference_skin_hsv=reference_skin_hsv,
        )
        filtered = patch[np.logical_and(patch_valid, skin_candidates)]
        if filtered.size < 24:
            relaxed_candidates = self._build_skin_candidate_mask(
                patch,
                reference_skin_color=reference_skin_color,
                min_luma=42.0,
                chroma_distance_limit=36.0,
                pixels_ycrcb=patch_ycrcb,
                pixels_hsv=patch_hsv,
                reference_skin_ycrcb=reference_skin_ycrcb,
                reference_skin_hsv=reference_skin_hsv,
            )
            filtered = patch[np.logical_and(patch_valid, relaxed_candidates)]
        if filtered.size < 24:
            filtered = patch[patch_valid]
        if filtered.size < 24:
            return None
        return np.median(filtered.reshape(-1, 3), axis=0).astype(np.float32)

    def _build_local_boundary_skin_field(
        self,
        frame_bgr: np.ndarray,
        hair_mask_full: np.ndarray,
        fringe_mask_full: np.ndarray,
        landmarks_px: np.ndarray | None,
        *,
        reference_skin_color: np.ndarray | None,
        active_x: np.ndarray,
        smoothed_boundary: np.ndarray,
        frame_ycrcb: np.ndarray | None = None,
        frame_hsv: np.ndarray | None = None,
    ) -> tuple[np.ndarray, np.ndarray] | None:
        if active_x.size == 0:
            return None

        height, width = frame_bgr.shape[:2]
        valid_mask = np.where(hair_mask_full > 0, np.uint8(0), np.uint8(255))
        if landmarks_px is not None and landmarks_px.ndim == 2 and landmarks_px.shape[1] >= 2:
            forehead_mid = _point(landmarks_px, "forehead_mid")
            left_temple = _point(landmarks_px, "left_temple")
            right_temple = _point(landmarks_px, "right_temple")
            chin_center = _point(landmarks_px, "chin_center")
            lower_left = _point(landmarks_px, "lower_left")
            lower_right = _point(landmarks_px, "lower_right")
            face_height = max(1.0, float(chin_center[1] - forehead_mid[1]))
            face_width = max(1.0, float(np.linalg.norm(lower_right - lower_left)))
            forehead_band = np.zeros((height, width), dtype=np.uint8)
            x0 = int(np.clip(round(min(left_temple[0], right_temple[0]) - face_width * 0.08), 0, width - 1))
            x1 = int(np.clip(round(max(left_temple[0], right_temple[0]) + face_width * 0.08), 0, width))
            y0 = int(np.clip(round(forehead_mid[1] - face_height * 0.06), 0, height - 1))
            y1 = int(np.clip(round(forehead_mid[1] + face_height * 0.26), 0, height))
            if x1 > x0 and y1 > y0:
                forehead_band[y0:y1, x0:x1] = 255
                valid_mask = opencv_bitwise_and(valid_mask, forehead_band)
            patch_radius = max(3, int(round(face_width * 0.038)))
            vertical_offset = max(2, int(round(face_height * 0.028)))
        else:
            patch_radius = 4
            vertical_offset = 3

        reference_skin_ycrcb, reference_skin_hsv = self._reference_skin_channels(reference_skin_color)
        sample_stride = max(3, int(round(active_x.size / 18.0)))
        sample_cols: list[int] = []
        sample_colors: list[np.ndarray] = []
        boundary_is_sample_aligned = smoothed_boundary.shape[0] == active_x.shape[0]
        for sample_index in range(0, active_x.size, sample_stride):
            col = int(active_x[sample_index])
            if boundary_is_sample_aligned:
                boundary_y = float(smoothed_boundary[sample_index])
            else:
                if col < 0 or col >= smoothed_boundary.shape[0]:
                    continue
                boundary_y = float(smoothed_boundary[col])
            if boundary_y < 0.0:
                continue
            sample = self._sample_patch_skin_median_with_valid_mask(
                frame_bgr,
                valid_mask,
                center_x=float(col),
                center_y=float(boundary_y + vertical_offset),
                radius=patch_radius,
                reference_skin_color=reference_skin_color,
                frame_ycrcb=frame_ycrcb,
                frame_hsv=frame_hsv,
                reference_skin_ycrcb=reference_skin_ycrcb,
                reference_skin_hsv=reference_skin_hsv,
            )
            if sample is None:
                continue
            sample_cols.append(col)
            sample_colors.append(sample.astype(np.float32))

        if not sample_cols:
            return None

        sample_cols_np = np.asarray(sample_cols, dtype=np.int32)
        sample_colors_np = np.stack(sample_colors, axis=0).astype(np.float32)
        local_field = np.empty((active_x.size, 3), dtype=np.float32)
        for channel in range(3):
            local_field[:, channel] = np.interp(
                active_x.astype(np.float32),
                sample_cols_np.astype(np.float32),
                sample_colors_np[:, channel].astype(np.float32),
            )
        return active_x.astype(np.int32), np.clip(local_field, 0.0, 255.0).astype(np.float32)

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
        ring = opencv_dilate(active, ring_kernel, iterations=1, min_pixels=24_000)
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
        left_temple = _point(landmarks_px, "left_temple")
        right_temple = _point(landmarks_px, "right_temple")
        left_ear_root = _point(landmarks_px, "left_ear_root")
        right_ear_root = _point(landmarks_px, "right_ear_root")
        lower_left = _point(landmarks_px, "lower_left")
        lower_right = _point(landmarks_px, "lower_right")
        chin_center = _point(landmarks_px, "chin_center")
        forehead_center = (forehead_top + forehead_mid) * 0.5
        face_height = max(1.0, float(chin_center[1] - forehead_center[1]))
        face_width = max(1.0, float(np.linalg.norm(lower_right - lower_left)))
        roll_deg = float(((user_row or {}).get("pose") or {}).get("roll_float", 0.0))

        mask = np.zeros((height, width), dtype=np.uint8)

        center = _clip_point(
            np.array(
                [
                    forehead_center[0],
                    forehead_center[1] + face_height * 0.08,
                ],
                dtype=np.float32,
            ),
            width,
            height,
        )
        axes = (
            max(1, int(round(face_width * 0.84))),
            max(1, int(round(face_height * 0.42))),
        )
        cv2.ellipse(mask, center, axes, roll_deg, 0, 360, 255, -1)

        # Extend only the central lower fringe so short front bangs stay in the
        # fringe region without widening the temple-side cleanup zone.
        lower_bang_center = _clip_point(
            np.array(
                [
                    forehead_mid[0],
                    forehead_mid[1] + face_height * 0.26,
                ],
                dtype=np.float32,
            ),
            width,
            height,
        )
        lower_bang_axes = (
            max(1, int(round(face_width * 0.34))),
            max(1, int(round(face_height * 0.20))),
        )
        cv2.ellipse(mask, lower_bang_center, lower_bang_axes, roll_deg, 0, 360, 255, -1)

        wing_axes = (
            max(1, int(round(face_width * 0.27))),
            max(1, int(round(face_height * 0.32))),
        )
        left_wing_center = _clip_point(
            np.array(
                [
                    left_temple[0] * 0.78 + left_ear_root[0] * 0.22 - face_width * 0.02,
                    left_temple[1] * 0.78 + left_ear_root[1] * 0.22 - face_height * 0.06,
                ],
                dtype=np.float32,
            ),
            width,
            height,
        )
        right_wing_center = _clip_point(
            np.array(
                [
                    right_temple[0] * 0.78 + right_ear_root[0] * 0.22 + face_width * 0.02,
                    right_temple[1] * 0.78 + right_ear_root[1] * 0.22 - face_height * 0.06,
                ],
                dtype=np.float32,
            ),
            width,
            height,
        )
        cv2.ellipse(mask, left_wing_center, wing_axes, roll_deg, 0, 360, 255, -1)
        cv2.ellipse(mask, right_wing_center, wing_axes, roll_deg, 0, 360, 255, -1)

        left_connector = np.array(
            [
                [
                    center[0] - axes[0] * 0.84,
                    center[1] - axes[1] * 0.56,
                ],
                [
                    left_wing_center[0] + wing_axes[0] * 0.60,
                    left_wing_center[1] - wing_axes[1] * 0.62,
                ],
                [
                    left_wing_center[0] + wing_axes[0] * 0.60,
                    left_wing_center[1] + wing_axes[1] * 0.52,
                ],
                [
                    center[0] - axes[0] * 0.84,
                    center[1] + axes[1] * 0.42,
                ],
            ],
            dtype=np.float32,
        )
        right_connector = np.array(
            [
                [
                    center[0] + axes[0] * 0.84,
                    center[1] - axes[1] * 0.56,
                ],
                [
                    right_wing_center[0] - wing_axes[0] * 0.60,
                    right_wing_center[1] - wing_axes[1] * 0.62,
                ],
                [
                    right_wing_center[0] - wing_axes[0] * 0.60,
                    right_wing_center[1] + wing_axes[1] * 0.52,
                ],
                [
                    center[0] + axes[0] * 0.84,
                    center[1] + axes[1] * 0.42,
                ],
            ],
            dtype=np.float32,
        )
        cv2.fillConvexPoly(
            mask,
            np.array([_clip_point(point, width, height) for point in left_connector], dtype=np.int32),
            255,
        )
        cv2.fillConvexPoly(
            mask,
            np.array([_clip_point(point, width, height) for point in right_connector], dtype=np.int32),
            255,
        )
        return mask

    def _build_eye_preserve_mask(
        self,
        frame_shape: tuple[int, ...],
        landmarks_px: np.ndarray,
        *,
        user_row: dict[str, Any] | None = None,
    ) -> np.ndarray | None:
        if landmarks_px.ndim != 2 or landmarks_px.shape[1] < 2:
            return None
        required_index = max(max(LEFT_EYE_CONTOUR_INDICES), max(RIGHT_EYE_CONTOUR_INDICES))
        if landmarks_px.shape[0] <= required_index:
            return None

        height, width = frame_shape[:2]
        lower_left = _point(landmarks_px, "lower_left")
        lower_right = _point(landmarks_px, "lower_right")
        face_width = max(1.0, float(np.linalg.norm(lower_right - lower_left)))
        mask = np.zeros((height, width), dtype=np.uint8)

        for contour_indices in (LEFT_EYE_CONTOUR_INDICES, RIGHT_EYE_CONTOUR_INDICES):
            contour = np.array(
                [_clip_point(landmarks_px[index].astype(np.float32), width, height) for index in contour_indices],
                dtype=np.int32,
            )
            if contour.shape[0] < 3:
                continue
            hull = cv2.convexHull(contour)
            cv2.fillConvexPoly(mask, hull, 255)

        if int(np.count_nonzero(mask)) == 0:
            return None

        dilation_px = max(1, int(round(face_width * 0.008)))
        dilation_kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (_odd_kernel(dilation_px * 2 + 1, minimum=3), _odd_kernel(dilation_px * 2 + 1, minimum=3)),
        )
        return opencv_dilate(mask, dilation_kernel, iterations=1, min_pixels=24_000)

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

        seed_mask = opencv_dilate(
            seed_mask,
            cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (_odd_kernel(seed_radius * 1.25, minimum=9), _odd_kernel(seed_radius * 1.25, minimum=9)),
            ),
            iterations=1,
            min_pixels=24_000,
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

        refine_max_dimension = 192
        refine_scale = min(1.0, float(refine_max_dimension) / float(max(frame_shape[:2])))
        if refine_scale < 0.999:
            refine_width = max(1, int(round(frame_shape[1] * refine_scale)))
            refine_height = max(1, int(round(frame_shape[0] * refine_scale)))
            strong_mask_refine = opencv_resize(
                strong_mask,
                (refine_width, refine_height),
                interpolation=cv2.INTER_NEAREST,
                min_pixels=0,
            )
            weak_mask_refine = opencv_resize(
                weak_mask,
                (refine_width, refine_height),
                interpolation=cv2.INTER_NEAREST,
                min_pixels=0,
            )
            seed_mask_refine = opencv_resize(
                seed_mask,
                (refine_width, refine_height),
                interpolation=cv2.INTER_NEAREST,
                min_pixels=0,
            )
        else:
            strong_mask_refine = strong_mask
            weak_mask_refine = weak_mask
            seed_mask_refine = seed_mask

        label_count, labels, _, _ = cv2.connectedComponentsWithStats(weak_mask_refine, connectivity=8)
        if label_count <= 1:
            return confidence_mask

        keep_mask = np.zeros(weak_mask_refine.shape, dtype=np.uint8)
        min_component_area = max(8, int(round(48.0 * refine_scale * refine_scale)))
        for label_index in range(1, label_count):
            component_mask = labels == label_index
            if not bool(np.any(seed_mask_refine[component_mask] > 0)):
                continue
            if not bool(np.any(strong_mask_refine[component_mask] > 0)):
                continue
            if int(np.count_nonzero(component_mask)) < min_component_area:
                continue
            keep_mask[component_mask] = 255

        if int(np.count_nonzero(keep_mask)) == 0:
            return confidence_mask
        if refine_scale < 0.999:
            keep_mask = opencv_resize(
                keep_mask,
                (frame_shape[1], frame_shape[0]),
                interpolation=cv2.INTER_NEAREST,
                min_pixels=0,
            )
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

        attenuation_started_at = time.perf_counter()
        detail_ms: dict[str, float] = {}
        mask_kind = "landmark"
        confidence_mask: np.ndarray | None = None
        mask_prepare_started_at = time.perf_counter()
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
        detail_ms["mask_prepare_ms"] = round((time.perf_counter() - mask_prepare_started_at) * 1000.0, 3)

        segmentation_alpha_threshold = max(0.08, self.profile.segmentation_confidence_threshold * 0.42)
        mask_build_started_at = time.perf_counter()
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
        detail_ms["mask_build_ms"] = round((time.perf_counter() - mask_build_started_at) * 1000.0, 3)

        upper_region_mask: np.ndarray | None = None
        roi_setup_started_at = time.perf_counter()
        x, y, width, height = cv2.boundingRect(binary_mask)
        if width <= 1 or height <= 1:
            return frame_bgr, {}

        roi = frame_bgr[y : y + height, x : x + width]
        mask_roi = binary_mask[y : y + height, x : x + width]
        work_scale = min(
            1.0,
            float(self.profile.max_work_dimension) / float(max(width, height)),
        )
        if work_scale < 0.999:
            work_width = max(1, int(round(width * work_scale)))
            work_height = max(1, int(round(height * work_scale)))
            roi_work = opencv_resize(roi, (work_width, work_height), interpolation=cv2.INTER_AREA)
            mask_work = opencv_resize(mask_roi, (work_width, work_height), interpolation=cv2.INTER_AREA)
        else:
            roi_work = roi
            mask_work = mask_roi
            work_width = width
            work_height = height

        detail_ms["roi_setup_ms"] = round((time.perf_counter() - roi_setup_started_at) * 1000.0, 3)
        hair_mask_full: np.ndarray | None = None
        fringe_mask_full: np.ndarray | None = None
        scalp_color: np.ndarray | None = None

        if confidence_mask is not None:
            confidence_alpha_started_at = time.perf_counter()
            confidence_roi = confidence_mask[y : y + height, x : x + width]
            binary_roi = binary_mask[y : y + height, x : x + width]
            if work_scale < 0.999:
                confidence_work = opencv_resize(
                    confidence_roi,
                    (work_width, work_height),
                    interpolation=cv2.INTER_LINEAR,
                )
                binary_work = opencv_resize(
                    binary_roi,
                    (work_width, work_height),
                    interpolation=cv2.INTER_NEAREST,
                )
            else:
                confidence_work = confidence_roi
                binary_work = binary_roi
            confidence_work = opencv_gaussian_blur(
                confidence_work,
                (0, 0),
                sigma_x=max(1.2, work_width * 0.026),
                sigma_y=max(1.2, work_height * 0.026),
                min_pixels=24_000,
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
            detail_ms["confidence_alpha_ms"] = round((time.perf_counter() - confidence_alpha_started_at) * 1000.0, 3)

            zone_mask_started_at = time.perf_counter()
            tone_source_gray = opencv_cvt_color(roi_work, cv2.COLOR_BGR2GRAY, min_pixels=8_192)
            tone_source_gray = opencv_cvt_color(tone_source_gray, cv2.COLOR_GRAY2BGR, min_pixels=8_192)
            tone_metadata = self._tone_metadata_from_roi(
                tone_source_gray,
                np.clip(confidence_work * 255.0, 0.0, 255.0).astype(np.uint8),
            )
            hair_mask_full = np.array(binary_mask, copy=True)
            fringe_mask_full = (
                self._build_forehead_fringe_mask(frame_bgr.shape, landmarks_px, user_row=user_row)
                if landmarks_px is not None
                else None
            )
            if fringe_mask_full is None:
                fringe_mask_full = np.zeros(frame_bgr.shape[:2], dtype=np.uint8)
            fringe_mask_full = opencv_bitwise_and(hair_mask_full, fringe_mask_full)

            # Treat every segmented hair pixel outside fringe as background-cleanup
            # territory. This removes the previous head-prior split and makes the
            # background zone follow the actual segmentation result directly.
            outer_bulk_mask_full = opencv_bitwise_and(
                hair_mask_full,
                opencv_bitwise_not(fringe_mask_full),
            )
            covered_mask_full = np.zeros_like(hair_mask_full, dtype=np.uint8)

            fringe_roi = fringe_mask_full[y : y + height, x : x + width]
            outer_bulk_roi = outer_bulk_mask_full[y : y + height, x : x + width]
            if work_scale < 0.999:
                fringe_work = opencv_resize(fringe_roi, (work_width, work_height), interpolation=cv2.INTER_LINEAR, min_pixels=8_192) >= 96
                covered_work = np.zeros((work_height, work_width), dtype=bool)
                outer_bulk_work = (
                    np.zeros((work_height, work_width), dtype=bool)
                    if self.profile.disable_outer_bulk_suppression
                    else opencv_resize(outer_bulk_roi, (work_width, work_height), interpolation=cv2.INTER_LINEAR, min_pixels=8_192) >= 96
                )
            else:
                fringe_work = fringe_roi >= 96
                covered_work = np.zeros_like(fringe_work, dtype=bool)
                outer_bulk_work = np.zeros_like(fringe_work, dtype=bool) if self.profile.disable_outer_bulk_suppression else outer_bulk_roi >= 96

            if self.profile.disable_fringe_suppression and np.any(fringe_work):
                alpha_work = np.where(fringe_work[..., None], np.float32(0.0), alpha_work)
                fringe_work = np.zeros_like(fringe_work, dtype=bool)
            detail_ms["zone_mask_ms"] = round((time.perf_counter() - zone_mask_started_at) * 1000.0, 3)

            base_blur_started_at = time.perf_counter()
            blur_kernel = _odd_kernel(max(work_width, work_height) * self.profile.blur_kernel_scale, minimum=5)
            blurred_work = opencv_gaussian_blur(
                roi_work,
                (blur_kernel, blur_kernel),
                sigma_x=0.0,
                sigma_y=0.0,
                min_pixels=24_000,
            )
            detail_ms["base_blur_ms"] = round((time.perf_counter() - base_blur_started_at) * 1000.0, 3)

            color_estimation_started_at = time.perf_counter()
            covered_soft_work: np.ndarray | None = None
            if np.any(covered_work):
                blurred_hsv = opencv_cvt_color(blurred_work, cv2.COLOR_BGR2HSV, min_pixels=8_192).astype(np.float32)
                blurred_hsv[:, :, 1] *= max(0.38, 1.0 - (self.profile.desaturation * 0.72))
                if self.profile.brightness_lift > 0.0:
                    blurred_hsv[:, :, 2] = np.clip(
                        blurred_hsv[:, :, 2] * (1.0 - self.profile.brightness_lift * 0.34)
                        + (255.0 * self.profile.brightness_lift * 0.42),
                        0.0,
                        255.0,
                    )
                covered_soft_work = opencv_cvt_color(blurred_hsv.astype(np.uint8), cv2.COLOR_HSV2BGR, min_pixels=8_192)
            weakened_work = blurred_work.copy()
            scalp_matte_work: np.ndarray | None = None
            analysis_plane = self._build_color_analysis_plane(
                frame_bgr,
                landmarks_px=landmarks_px,
                hair_mask=hair_mask_full,
                outer_bulk_mask=outer_bulk_mask_full,
                fringe_mask=fringe_mask_full,
            )
            cached_color_estimates = self._load_cached_color_estimates(
                user_row=user_row,
                frame_shape=frame_bgr.shape[:2],
                analysis_plane=analysis_plane,
            )
            if cached_color_estimates is not None:
                skin_color, boundary_skin_color, background_color, scalp_color = cached_color_estimates
            else:
                skin_color = self._estimate_skin_color(
                    analysis_plane.frame_bgr,
                    analysis_plane.landmarks_px,
                    frame_ycrcb=analysis_plane.frame_ycrcb,
                    frame_hsv=analysis_plane.frame_hsv,
                )
                boundary_skin_color = self._estimate_lower_boundary_skin_color(
                    analysis_plane.frame_bgr,
                    analysis_plane.hair_mask if analysis_plane.hair_mask is not None else hair_mask_full,
                    analysis_plane.landmarks_px,
                    reference_skin_color=skin_color,
                    frame_ycrcb=analysis_plane.frame_ycrcb,
                    frame_hsv=analysis_plane.frame_hsv,
                )
                scalp_source_color = self._blend_scalp_reference_color(
                    skin_color,
                    boundary_skin_color,
                )
                if scalp_source_color is not None:
                    scalp_color = self._resolve_scalp_color(scalp_source_color)
                else:
                    scalp_color = None
                background_color = (
                    self._estimate_background_color(
                        analysis_plane.frame_bgr,
                        analysis_plane.outer_bulk_mask if analysis_plane.outer_bulk_mask is not None else outer_bulk_mask_full,
                    )
                    if int(np.count_nonzero(outer_bulk_mask_full)) > 0 and analysis_plane.outer_bulk_mask is not None
                    else None
                )
                self._store_cached_color_estimates(
                    user_row=user_row,
                    frame_shape=frame_bgr.shape[:2],
                    analysis_plane=analysis_plane,
                    skin_color=skin_color,
                    boundary_skin_color=boundary_skin_color,
                    background_color=background_color,
                    scalp_color=scalp_color,
                )
            if scalp_color is not None:
                if self.profile.luma_preserving_scalp_enabled:
                    active_scalp_region = fringe_work if np.any(fringe_work) else binary_work_mask
                    scalp_matte_work = self._compose_luma_preserving_scalp_matte(
                        blurred_work,
                        scalp_color,
                        active_region=active_scalp_region,
                    )
                else:
                    scalp_matte_work = np.empty_like(roi_work, dtype=np.uint8)
                    scalp_matte_work[:] = np.clip(scalp_color, 0.0, 255.0).astype(np.uint8)
            if scalp_matte_work is not None and np.any(fringe_work):
                weakened_work[fringe_work] = scalp_matte_work[fringe_work]
                fringe_alpha = np.where(
                    fringe_work,
                    np.float32(min(0.92, max(self.profile.strength * 0.92, 0.76))),
                    np.float32(0.0),
                )
                fringe_alpha = opencv_gaussian_blur(
                    fringe_alpha,
                    (0, 0),
                    sigma_x=max(0.8, work_width * 0.012),
                    sigma_y=max(0.8, work_height * 0.012),
                    min_pixels=24_000,
                )
                fringe_alpha = np.where(fringe_work, np.clip(fringe_alpha, 0.0, 0.92), np.float32(0.0))
                alpha_work = np.where(
                    fringe_work[..., None],
                    np.maximum(alpha_work, fringe_alpha[..., None]),
                    alpha_work,
                )
            detail_ms["color_estimation_ms"] = round((time.perf_counter() - color_estimation_started_at) * 1000.0, 3)

            suppression_apply_started_at = time.perf_counter()
            if np.any(covered_work):
                covered_work_rgb = (
                    scalp_matte_work.astype(np.float32)
                    if scalp_matte_work is not None
                    else covered_soft_work.astype(np.float32)
                )
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
                weakened_work = weakened_work.astype(np.float32)
                weakened_work[outer_bulk_work] = (
                    bg_fill[outer_bulk_work] * 0.82 + blurred_work.astype(np.float32)[outer_bulk_work] * 0.18
                )
                weakened_work = np.clip(weakened_work, 0, 255).astype(np.uint8)
                alpha_work = np.where(
                    outer_bulk_work[..., None],
                    np.float32(max(self.profile.strength, 0.95)),
                    alpha_work,
                )
            detail_ms["suppression_apply_ms"] = round((time.perf_counter() - suppression_apply_started_at) * 1000.0, 3)

            tone_metadata["suppression_mode"] = "segmentation_zones"
            if self.profile.disable_fringe_suppression:
                tone_metadata["fringe_mode"] = "disabled"
            tone_metadata["covered_mode"] = (
                "disabled"
                if self.profile.disable_covered_suppression
                else (
                    "scalp_matte_only"
                    if scalp_matte_work is not None
                    else "soft_blur"
                )
            )
            if self.profile.disable_outer_bulk_suppression:
                tone_metadata["outer_bulk_mode"] = "disabled"
            hair_pixel_count = max(1, int(np.count_nonzero(hair_mask_full)))
            tone_metadata["fringe_ratio"] = round(float(np.count_nonzero(fringe_mask_full)) / float(hair_pixel_count), 6)
            tone_metadata["outer_bulk_ratio"] = round(float(np.count_nonzero(outer_bulk_mask_full)) / float(hair_pixel_count), 6)
            tone_metadata["hair_binary_mask"] = hair_mask_full
            tone_metadata["fringe_mask"] = fringe_mask_full
            tone_metadata["outer_bulk_mask"] = outer_bulk_mask_full
            if background_color is not None:
                tone_metadata["background_color"] = np.asarray(background_color, dtype=np.float32)
            if scalp_color is not None:
                tone_metadata["scalp_color"] = np.asarray(scalp_color, dtype=np.float32)
            if self.profile.bald_test_mode:
                bald_mode_started_at = time.perf_counter()
                matte_work = blurred_work.astype(np.float32)
                skin_color = self._estimate_skin_color(frame_bgr, landmarks_px)
                if skin_color is None:
                    skin_color = self._estimate_skin_color_fallback(frame_bgr)
                if skin_color is not None:
                    scalp_kernel = _odd_kernel(max(work_width, work_height) * (self.profile.blur_kernel_scale * 1.8), minimum=9)
                    scalp_lowfreq = opencv_gaussian_blur(
                        roi_work,
                        (scalp_kernel, scalp_kernel),
                        sigma_x=0.0,
                        sigma_y=0.0,
                        min_pixels=24_000,
                    )
                    scalp_hsv = opencv_cvt_color(scalp_lowfreq, cv2.COLOR_BGR2HSV, min_pixels=8_192).astype(np.float32)
                    scalp_hsv[:, :, 1] *= 0.06
                    scalp_hsv[:, :, 2] = np.clip(
                        scalp_hsv[:, :, 2] * 0.96 + 255.0 * 0.08,
                        0.0,
                        255.0,
                    )
                    ambient_scalp = opencv_cvt_color(scalp_hsv.astype(np.uint8), cv2.COLOR_HSV2BGR, min_pixels=8_192).astype(np.float32)
                    skin_fill = np.empty_like(matte_work, dtype=np.float32)
                    skin_fill[:] = skin_color
                    local_luma = opencv_cvt_color(scalp_lowfreq, cv2.COLOR_BGR2GRAY, min_pixels=8_192).astype(np.float32)
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
                detail_ms["bald_mode_ms"] = round((time.perf_counter() - bald_mode_started_at) * 1000.0, 3)
        else:
            landmark_path_started_at = time.perf_counter()
            mask_work = opencv_gaussian_blur(
                mask_work,
                (0, 0),
                sigma_x=max(2.0, work_width * 0.08),
                sigma_y=max(2.0, work_height * 0.10),
                min_pixels=24_000,
            )
            alpha_work = (mask_work.astype(np.float32) / 255.0)[..., None] * self.profile.strength
            if float(alpha_work.max()) <= 0.01:
                return frame_bgr, {}

            blur_kernel = _odd_kernel(max(work_width, work_height) * self.profile.blur_kernel_scale, minimum=5)
            blurred_work = opencv_gaussian_blur(
                roi_work,
                (blur_kernel, blur_kernel),
                sigma_x=0.0,
                sigma_y=0.0,
                min_pixels=24_000,
            )
            grayscale_work = opencv_cvt_color(blurred_work, cv2.COLOR_BGR2GRAY, min_pixels=8_192)
            grayscale_work = opencv_cvt_color(grayscale_work, cv2.COLOR_GRAY2BGR, min_pixels=8_192)
            tone_metadata = self._tone_metadata_from_roi(grayscale_work, mask_work)
            weakened_work = opencv_add_weighted(
                blurred_work,
                1.0 - self.profile.desaturation,
                grayscale_work,
                self.profile.desaturation,
                0.0,
            )
            if self.profile.brightness_lift > 0.0:
                weakened_work = opencv_add_weighted(
                    weakened_work,
                    1.0 - self.profile.brightness_lift,
                    np.full_like(weakened_work, 255),
                    self.profile.brightness_lift,
                    0.0,
                )
            detail_ms["landmark_path_ms"] = round((time.perf_counter() - landmark_path_started_at) * 1000.0, 3)

        metadata: dict[str, Any] = dict(tone_metadata)
        metadata["mask_kind"] = mask_kind

        upscale_alpha_started_at = time.perf_counter()
        if work_scale < 0.999:
            weakened = opencv_resize(weakened_work, (width, height), interpolation=cv2.INTER_LINEAR)
            if confidence_mask is not None:
                alpha = (
                    opencv_resize(alpha_work[:, :, 0], (width, height), interpolation=cv2.INTER_LINEAR)
                )[..., None]
                alpha = np.where(mask_roi[..., None] >= 96, alpha, np.float32(0.0))
            else:
                alpha = (
                    opencv_resize(mask_work, (width, height), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0
                )[..., None] * self.profile.strength
        else:
            weakened = weakened_work
            alpha = alpha_work
            if confidence_mask is not None:
                alpha = np.where(mask_roi[..., None] >= 96, alpha, np.float32(0.0))
        detail_ms["upscale_alpha_ms"] = round((time.perf_counter() - upscale_alpha_started_at) * 1000.0, 3)

        roi_blend_started_at = time.perf_counter()
        output = frame_bgr.copy()
        blended = (
            roi.astype(np.float32) * (1.0 - alpha)
            + weakened.astype(np.float32) * alpha
        )
        output[y : y + height, x : x + width] = np.clip(blended, 0, 255).astype(np.uint8)
        detail_ms["roi_blend_ms"] = round((time.perf_counter() - roi_blend_started_at) * 1000.0, 3)

        lower_hairline_started_at = time.perf_counter()
        if hair_mask_full is not None and fringe_mask_full is not None and scalp_color is not None:
            fringe_bool = fringe_mask_full > 0
            active_cols_mask = np.any(fringe_bool, axis=0)
            if int(np.count_nonzero(active_cols_mask)) > 0:
                outer_px = max(5, min(12, int(round(height * 0.054))))
                active_x_raw = np.flatnonzero(active_cols_mask)
                reversed_fringe = fringe_bool[::-1, :]
                bottom_from_end = reversed_fringe.argmax(axis=0)
                lower_boundary = np.where(
                    active_cols_mask,
                    fringe_bool.shape[0] - 1 - bottom_from_end,
                    -1,
                ).astype(np.int32)
                lower_boundary_float = lower_boundary.astype(np.float32)
                valid_boundary_mask = (lower_boundary >= 0).astype(np.float32)
                boundary_values = np.where(lower_boundary >= 0, lower_boundary_float, 0.0)
                smoothing_kernel = np.ones(5, dtype=np.float32)
                smoothed_boundary = np.where(
                    np.convolve(valid_boundary_mask, smoothing_kernel, mode="same") > 0.0,
                    np.convolve(boundary_values, smoothing_kernel, mode="same")
                    / np.maximum(np.convolve(valid_boundary_mask, smoothing_kernel, mode="same"), 1e-6),
                    -1.0,
                ).astype(np.float32)
                valid_boundary_cols = active_x_raw[smoothed_boundary[active_x_raw] >= 0]
                if valid_boundary_cols.size < 2:
                    active_x = active_x_raw
                else:
                    active_x = np.arange(int(active_x_raw[0]), int(active_x_raw[-1]) + 1, dtype=np.int32)
                    smoothed_boundary[active_x] = np.interp(
                        active_x.astype(np.float32),
                        valid_boundary_cols.astype(np.float32),
                        smoothed_boundary[valid_boundary_cols].astype(np.float32),
                    )
                boundary_values = smoothed_boundary[active_x]
                if boundary_values.size > 0:
                    boundary_min = float(np.min(boundary_values))
                    boundary_max = float(np.max(boundary_values))
                    crop_x0 = max(0, int(active_x[0]) - 2)
                    crop_x1 = min(frame_bgr.shape[1], int(active_x[-1]) + 3)
                    crop_y0 = max(0, int(np.floor(boundary_min)) - 2)
                    crop_y1 = min(frame_bgr.shape[0], int(np.ceil(boundary_max + outer_px)) + 2)
                    if crop_x1 > crop_x0 and crop_y1 > crop_y0:
                        crop_frame = frame_bgr[crop_y0:crop_y1, crop_x0:crop_x1]
                        crop_output = output[crop_y0:crop_y1, crop_x0:crop_x1]
                        crop_hair_mask = hair_mask_full[crop_y0:crop_y1, crop_x0:crop_x1]
                        crop_fringe_mask = fringe_mask_full[crop_y0:crop_y1, crop_x0:crop_x1]
                        crop_landmarks = self._translate_landmarks(landmarks_px, offset_x=crop_x0, offset_y=crop_y0)
                        crop_ycrcb = opencv_cvt_color(crop_frame, cv2.COLOR_BGR2YCrCb, min_pixels=0)
                        crop_hsv = opencv_cvt_color(crop_frame, cv2.COLOR_BGR2HSV, min_pixels=0)
                        crop_active_x = active_x - crop_x0
                        crop_boundary = smoothed_boundary[active_x] - float(crop_y0)
                        if self.profile.luma_preserving_scalp_enabled:
                            boundary_reference_color = (
                                boundary_skin_color
                                if boundary_skin_color is not None
                                else skin_color
                            )
                            if boundary_reference_color is None:
                                boundary_reference_color = scalp_color
                        else:
                            boundary_reference_color = scalp_color
                        local_boundary_field = self._build_local_boundary_skin_field(
                            crop_frame,
                            crop_hair_mask,
                            crop_fringe_mask,
                            crop_landmarks,
                            reference_skin_color=boundary_reference_color,
                            active_x=crop_active_x,
                            smoothed_boundary=crop_boundary,
                            frame_ycrcb=crop_ycrcb,
                            frame_hsv=crop_hsv,
                        )
                        scalp_color_float = np.clip(scalp_color, 0.0, 255.0).astype(np.float32)
                        field_by_col = np.tile(scalp_color_float[None, :], (crop_frame.shape[1], 1))
                        if local_boundary_field is not None:
                            field_cols, field_colors = local_boundary_field
                            field_by_col[field_cols] = field_colors

                        inverse_hair_mask = opencv_bitwise_not(crop_hair_mask)
                        label_count, labels = cv2.connectedComponents(inverse_hair_mask, connectivity=8)
                        external_background_mask = np.zeros_like(crop_hair_mask, dtype=np.uint8)
                        if label_count > 1:
                            border_labels = np.unique(
                                np.concatenate(
                                    [
                                        labels[0, :],
                                        labels[-1, :],
                                        labels[:, 0],
                                        labels[:, -1],
                                    ]
                                )
                            )
                            for label_index in border_labels:
                                if int(label_index) <= 0:
                                    continue
                                external_background_mask[labels == int(label_index)] = 255

                        boundary_by_col = np.full(crop_frame.shape[1], -1.0, dtype=np.float32)
                        boundary_by_col[crop_active_x] = crop_boundary.astype(np.float32)
                        row_grid = np.arange(crop_frame.shape[0], dtype=np.float32)[:, None]
                        outer_ring_mask = np.logical_and(
                            row_grid > boundary_by_col[None, :],
                            row_grid <= (boundary_by_col + float(outer_px))[None, :],
                        )
                        outer_ring_mask &= crop_fringe_mask <= 0
                        outer_ring_mask &= external_background_mask > 0
                        if int(np.count_nonzero(outer_ring_mask)) > 0:
                            ring_rows, ring_cols = np.nonzero(outer_ring_mask)
                            transition_output = crop_output.astype(np.float32)
                            base_output_float = transition_output.copy()
                            ring_boundary = boundary_by_col[ring_cols].astype(np.float32)
                            ring_t = np.clip(
                                ((ring_rows.astype(np.float32) - ring_boundary) / max(1.0, float(outer_px)))[:, None],
                                0.0,
                                1.0,
                            )
                            ring_t = np.power(ring_t, 1.85)
                            ring_colors = field_by_col[ring_cols]
                            transition_output[ring_rows, ring_cols, :] = (
                                ring_colors * (1.0 - ring_t)
                                + base_output_float[ring_rows, ring_cols, :] * ring_t
                            )
                            output[crop_y0:crop_y1, crop_x0:crop_x1] = np.clip(transition_output, 0.0, 255.0).astype(np.uint8)
        detail_ms["lower_hairline_blend_ms"] = round((time.perf_counter() - lower_hairline_started_at) * 1000.0, 3)

        eye_restore_started_at = time.perf_counter()
        if self.profile.preserve_eyes_enabled and landmarks_px is not None:
            eye_mask_full = self._build_eye_preserve_mask(frame_bgr.shape, landmarks_px, user_row=user_row)
            if eye_mask_full is not None and int(np.count_nonzero(eye_mask_full)) >= 8:
                eye_x, eye_y, eye_w, eye_h = cv2.boundingRect(eye_mask_full)
                if eye_w > 1 and eye_h > 1:
                    eye_roi_mask = eye_mask_full[eye_y : eye_y + eye_h, eye_x : eye_x + eye_w].astype(np.float32) / 255.0
                    eye_alpha = opencv_gaussian_blur(
                        eye_roi_mask,
                        (0, 0),
                        sigma_x=max(0.6, eye_w * 0.01),
                        sigma_y=max(0.6, eye_h * 0.01),
                        min_pixels=0,
                    )
                    eye_alpha = np.where(eye_roi_mask > 0.0, eye_alpha, 0.0)
                    eye_alpha = np.clip(eye_alpha, 0.0, 1.0)
                    if float(eye_alpha.max()) > 0.01:
                        restored_eye_roi = output[eye_y : eye_y + eye_h, eye_x : eye_x + eye_w].astype(np.float32)
                        source_eye_roi = frame_bgr[eye_y : eye_y + eye_h, eye_x : eye_x + eye_w].astype(np.float32)
                        restored_eye_roi = (
                            restored_eye_roi * (1.0 - eye_alpha[..., None])
                            + source_eye_roi * eye_alpha[..., None]
                        )
                        output[eye_y : eye_y + eye_h, eye_x : eye_x + eye_w] = np.clip(
                            restored_eye_roi,
                            0.0,
                            255.0,
                        ).astype(np.uint8)
        detail_ms["eye_restore_ms"] = round((time.perf_counter() - eye_restore_started_at) * 1000.0, 3)
        detail_ms["total_ms"] = round((time.perf_counter() - attenuation_started_at) * 1000.0, 3)
        metadata["attenuation_detail_ms"] = detail_ms
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
