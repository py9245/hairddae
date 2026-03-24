from __future__ import annotations

import logging
from pathlib import Path
from threading import Lock

import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


logger = logging.getLogger("uvicorn.error")


class HairSegmenter:
    def __init__(self, model_path: Path, *, delegate: str = "gpu") -> None:
        self._model_path = Path(model_path).expanduser().resolve()
        self._delegate = str(delegate or "gpu").strip().lower()
        self._lock = Lock()
        self._segmenter: vision.ImageSegmenter | None = None
        self._last_timestamp_ms = 0

    @staticmethod
    def _resolve_delegate(value: str) -> python.BaseOptions.Delegate:
        if value == "gpu":
            return python.BaseOptions.Delegate.GPU
        return python.BaseOptions.Delegate.CPU

    def _create_segmenter(self) -> vision.ImageSegmenter:
        delegates = [self._delegate]
        if self._delegate == "gpu":
            delegates.append("cpu")

        last_error: Exception | None = None
        for delegate_name in delegates:
            try:
                options = vision.ImageSegmenterOptions(
                    base_options=python.BaseOptions(
                        model_asset_path=str(self._model_path),
                        delegate=self._resolve_delegate(delegate_name),
                    ),
                    running_mode=vision.RunningMode.VIDEO,
                    output_confidence_masks=True,
                    output_category_mask=False,
                )
                segmenter = vision.ImageSegmenter.create_from_options(options)
                if delegate_name != self._delegate:
                    logger.warning(
                        "hair segmenter fallback delegate activated: requested=%s actual=%s",
                        self._delegate,
                        delegate_name,
                    )
                return segmenter
            except Exception as exc:  # pragma: no cover - runtime dependent
                last_error = exc
                logger.warning(
                    "hair segmenter init failed: delegate=%s reason=%s",
                    delegate_name,
                    exc,
                )

        raise RuntimeError("failed to initialize MediaPipe HairSegmenter") from last_error

    def _instance(self) -> vision.ImageSegmenter:
        if self._segmenter is None:
            self._segmenter = self._create_segmenter()
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
        if frame_rgb.ndim != 3 or frame_rgb.shape[2] != 3:
            return None

        if timestamp_ms is None:
            timestamp_ms = self._last_timestamp_ms + 1

        with self._lock:
            segmenter = self._instance()
            resolved_timestamp_ms = max(int(timestamp_ms), self._last_timestamp_ms + 1)
            self._last_timestamp_ms = resolved_timestamp_ms
            mp_image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=np.ascontiguousarray(frame_rgb),
            )
            result = segmenter.segment_for_video(mp_image, resolved_timestamp_ms)

        if result is None or not result.confidence_masks or len(result.confidence_masks) < 2:
            return None

        mask = np.asarray(result.confidence_masks[1].numpy_view(), dtype=np.float32)
        if mask.ndim == 3 and mask.shape[2] == 1:
            mask = mask[:, :, 0]
        if mask.ndim != 2:
            return None
        return np.clip(mask, 0.0, 1.0)
