from __future__ import annotations

import logging
from pathlib import Path
from threading import Lock
import time

import numpy as np

logger = logging.getLogger("uvicorn.error")


class BodySegmenter:
    def __init__(
        self,
        weights_path: Path,
        *,
        threshold: float = 0.35,
        precision: str = "fp16",
    ) -> None:
        self._weights_path = Path(weights_path).expanduser().resolve()
        self._threshold = float(np.clip(threshold, 0.05, 0.95))
        self._precision = "fp16" if str(precision or "fp16").strip().lower() == "fp16" else "fp32"
        self._lock = Lock()
        self._torch = None
        self._model = None
        self._device = "cpu"
        self._dtype = None
        self._mean = None
        self._std = None
        self._person_index = 15

    def _ensure_instance(self) -> None:
        with self._lock:
            if self._model is not None:
                return

            import torch
            from torchvision.models.segmentation import (
                LRASPP_MobileNet_V3_Large_Weights,
                lraspp_mobilenet_v3_large,
            )

            # This runtime currently ships a torch wheel / cuDNN combination that
            # can abort on first model execution. Keep body segmentation on the
            # safer CUDA path instead of letting worker startup crash.
            torch.backends.cudnn.enabled = False

            self._torch = torch
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            self._dtype = torch.float16 if self._device == "cuda" and self._precision == "fp16" else torch.float32

            weights = LRASPP_MobileNet_V3_Large_Weights.COCO_WITH_VOC_LABELS_V1
            categories = list(weights.meta.get("categories", []))
            if "person" in categories:
                self._person_index = int(categories.index("person"))

            model = lraspp_mobilenet_v3_large(weights=None, weights_backbone=None)
            state_dict = torch.load(str(self._weights_path), map_location="cpu")
            model.load_state_dict(state_dict)
            model = model.eval().to(self._device)
            if self._dtype == torch.float16:
                model = model.half()
            self._model = model
            self._mean = torch.tensor([0.485, 0.456, 0.406], dtype=self._dtype, device=self._device).view(3, 1, 1)
            self._std = torch.tensor([0.229, 0.224, 0.225], dtype=self._dtype, device=self._device).view(3, 1, 1)

    def close(self) -> None:
        with self._lock:
            torch = self._torch
            device = self._device
            self._model = None
            self._mean = None
            self._std = None
        if torch is not None and device == "cuda":
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass

    def warm_up(self) -> float:
        blank_rgb = np.zeros((256, 256, 3), dtype=np.uint8)
        started_at = time.perf_counter()
        _ = self.segment_person_mask_from_rgb(blank_rgb)
        return round((time.perf_counter() - started_at) * 1000.0, 3)

    def segment_person_mask_from_rgb(self, frame_rgb: np.ndarray) -> np.ndarray | None:
        if frame_rgb.ndim != 3 or frame_rgb.shape[2] != 3 or frame_rgb.dtype != np.uint8:
            return None

        self._ensure_instance()
        if self._torch is None or self._model is None or self._mean is None or self._std is None:
            return None

        torch = self._torch
        with self._lock:
            tensor = torch.from_numpy(np.ascontiguousarray(frame_rgb)).to(
                device=self._device,
                dtype=self._dtype,
                non_blocking=True,
            )
            tensor = tensor.permute(2, 0, 1).contiguous()
            tensor = tensor.div(255.0)
            tensor = ((tensor - self._mean) / self._std).unsqueeze(0)
            with torch.inference_mode():
                logits = self._model(tensor)["out"]
                if self._device == "cuda":
                    torch.cuda.synchronize()
            probabilities = torch.softmax(logits.float(), dim=1)[0, self._person_index]
            mask = probabilities.ge(self._threshold).to(torch.uint8).mul_(255)
            return mask.detach().cpu().numpy()
