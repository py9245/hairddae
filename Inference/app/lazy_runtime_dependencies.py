from __future__ import annotations

from pathlib import Path
from threading import Lock

import numpy as np

from app.bald import BaldPreprocessor
from app.face_tracking import ServerFaceTracker, TrackingResult


class LazyFaceTracker:
    def __init__(self, model_path: Path, num_faces: int = 1) -> None:
        self._model_path = model_path
        self._num_faces = max(1, int(num_faces))
        self._lock = Lock()
        self._tracker: ServerFaceTracker | None = None

    def _instance(self) -> ServerFaceTracker:
        with self._lock:
            if self._tracker is None:
                self._tracker = ServerFaceTracker(self._model_path, num_faces=self._num_faces)
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


class LazyBaldPreprocessor:
    def __init__(self, model_path: Path) -> None:
        self._model_path = model_path
        self._lock = Lock()
        self._processor: BaldPreprocessor | None = None

    def _instance(self) -> BaldPreprocessor:
        with self._lock:
            if self._processor is None:
                self._processor = BaldPreprocessor(self._model_path)
            return self._processor

    def close(self) -> None:
        with self._lock:
            processor = self._processor
            self._processor = None
        if processor is not None:
            processor.close()

    def apply(self, frame_rgb: np.ndarray, landmarks_px: np.ndarray) -> np.ndarray:
        return self._instance().apply(frame_rgb, landmarks_px)
