from __future__ import annotations

from pathlib import Path
from threading import Lock

import numpy as np

from app.face_tracking import ServerFaceTracker, TrackingResult
from app.hair_attenuation import HairAttenuator
from app.hair_segmentation import HairSegmenter as RuntimeHairSegmenter


class LazyFaceTracker:
    def __init__(self, model_path: Path, num_faces: int = 1, delegate: str = "cpu") -> None:
        self._model_path = model_path
        self._num_faces = max(1, int(num_faces))
        self._delegate = str(delegate or "cpu")
        self._lock = Lock()
        self._tracker: ServerFaceTracker | None = None

    def _instance(self) -> ServerFaceTracker:
        with self._lock:
            if self._tracker is None:
                self._tracker = ServerFaceTracker(
                    self._model_path,
                    num_faces=self._num_faces,
                    delegate=self._delegate,
                )
            return self._tracker

    def close(self) -> None:
        with self._lock:
            tracker = self._tracker
            self._tracker = None
        if tracker is not None:
            tracker.close()

    def extract_tracking_result_from_rgb(self, *args: object, **kwargs: object) -> TrackingResult | None:
        return self._instance().extract_tracking_result_from_rgb(*args, **kwargs)

    def extract_feature_from_rgb(self, *args: object, **kwargs: object):
        return self._instance().extract_feature_from_rgb(*args, **kwargs)


class LazyHairAttenuator:
    def __init__(
        self,
        *,
        segmentation_confidence_threshold: float,
        strength: float,
        desaturation: float,
        brightness_lift: float,
        blur_kernel_scale: float,
        max_work_dimension: int,
        bald_test_mode: bool,
    ) -> None:
        self._lock = Lock()
        self._attenuator: HairAttenuator | None = None
        self._segmentation_confidence_threshold = float(segmentation_confidence_threshold)
        self._strength = float(strength)
        self._desaturation = float(desaturation)
        self._brightness_lift = float(brightness_lift)
        self._blur_kernel_scale = float(blur_kernel_scale)
        self._max_work_dimension = int(max_work_dimension)
        self._bald_test_mode = bool(bald_test_mode)

    def _instance(self) -> HairAttenuator:
        with self._lock:
            if self._attenuator is None:
                self._attenuator = HairAttenuator(
                    segmentation_confidence_threshold=self._segmentation_confidence_threshold,
                    strength=self._strength,
                    desaturation=self._desaturation,
                    brightness_lift=self._brightness_lift,
                    blur_kernel_scale=self._blur_kernel_scale,
                    max_work_dimension=self._max_work_dimension,
                    bald_test_mode=self._bald_test_mode,
                )
            return self._attenuator

    def close(self) -> None:
        with self._lock:
            attenuator = self._attenuator
            self._attenuator = None
        if attenuator is not None:
            attenuator.close()

    def apply(
        self,
        frame_bgr: np.ndarray,
        landmarks_px: np.ndarray,
        *,
        user_row: dict[str, object] | None = None,
        hair_confidence_mask: np.ndarray | None = None,
    ) -> np.ndarray:
        return self._instance().apply(
            frame_bgr,
            landmarks_px,
            user_row=user_row,
            hair_confidence_mask=hair_confidence_mask,
        )

    def apply_with_metadata(
        self,
        frame_bgr: np.ndarray,
        landmarks_px: np.ndarray,
        *,
        user_row: dict[str, object] | None = None,
        hair_confidence_mask: np.ndarray | None = None,
    ) -> tuple[np.ndarray, dict[str, object]]:
        return self._instance().apply_with_metadata(
            frame_bgr,
            landmarks_px,
            user_row=user_row,
            hair_confidence_mask=hair_confidence_mask,
        )


class LazyHairSegmenter:
    def __init__(self, model_path: Path, *, delegate: str = "gpu") -> None:
        self._model_path = model_path
        self._delegate = str(delegate or "gpu")
        self._lock = Lock()
        self._segmenter: RuntimeHairSegmenter | None = None

    def _instance(self) -> RuntimeHairSegmenter:
        with self._lock:
            if self._segmenter is None:
                self._segmenter = RuntimeHairSegmenter(
                    self._model_path,
                    delegate=self._delegate,
                )
            return self._segmenter

    def close(self) -> None:
        with self._lock:
            segmenter = self._segmenter
            self._segmenter = None
        if segmenter is not None:
            segmenter.close()

    def segment_hair_confidence_from_rgb(
        self,
        frame_rgb: np.ndarray,
        *,
        timestamp_ms: int | None = None,
    ) -> np.ndarray | None:
        return self._instance().segment_hair_confidence_from_rgb(
            frame_rgb,
            timestamp_ms=timestamp_ms,
        )
