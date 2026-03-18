from __future__ import annotations

import os
from pathlib import Path
from threading import Lock
from typing import Any

import numpy as np

from app.config import Settings
from app.hairddae_runtime import HairOverlayRuntime


class HairddaeRuntimeManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = Lock()
        self._runtime_cache: dict[str, HairOverlayRuntime] = {}

    def _inference_root(self) -> Path:
        return Path(__file__).resolve().parents[1]

    def _face_parsing_repo_dir(self) -> Path:
        candidates = [
            self._inference_root() / "third_party" / "third_party" / "face-parsing.PyTorch",
            self._inference_root() / "third_party" / "face-parsing.PyTorch",
        ]
        for candidate in candidates:
            if candidate.is_dir():
                return candidate
        return candidates[0]

    def _face_parsing_weights_path(self) -> Path:
        return self._face_parsing_repo_dir() / "res" / "cp" / "79999_iter.pth"

    def _configure_runtime_env(self) -> None:
        repo_dir = self._face_parsing_repo_dir()
        weights_path = self._face_parsing_weights_path()
        if not repo_dir.is_dir():
            raise FileNotFoundError(f"missing face parsing repo: {repo_dir}")
        if not weights_path.is_file():
            raise FileNotFoundError(f"missing face parsing weights: {weights_path}")

        os.environ["LOCAL_DEMO_APPROVED_ONLY"] = "1"
        os.environ["LOCAL_DEMO_APPROVED_STRICT_ONLY"] = "0"
        os.environ["FACE_PARSING_REPO_DIR"] = str(repo_dir)
        os.environ["FACE_PARSING_WEIGHTS"] = str(weights_path)
        os.environ["FACE_LANDMARKER_TASK"] = str(self._settings.face_landmarker_model_path)

    def _runtime_for_dataset(self, dataset_code: str) -> HairOverlayRuntime:
        with self._lock:
            runtime = self._runtime_cache.get(dataset_code)
            if runtime is not None:
                return runtime

            self._configure_runtime_env()
            asset_root = self._settings.static_root / dataset_code
            runtime = HairOverlayRuntime(
                asset_root=asset_root,
                model_path=self._settings.face_landmarker_model_path,
                jpeg_quality=self._settings.http_test_jpeg_quality,
                renderer_name="mesh_v3",
            )
            self._runtime_cache[dataset_code] = runtime
            return runtime

    def process_frame(
        self,
        *,
        dataset_code: str,
        frame_bgr: np.ndarray,
        render_frame_bgr: np.ndarray | None = None,
        session_id: str,
    ) -> dict[str, Any]:
        runtime = self._runtime_for_dataset(dataset_code)
        return runtime.process_frame(
            frame_bgr,
            renderer_name="mesh_v3",
            render_frame_bgr=render_frame_bgr,
            session_id=session_id,
        )

    def health(self, dataset_code: str) -> dict[str, Any]:
        runtime = self._runtime_for_dataset(dataset_code)
        return runtime.health()

    def close(self) -> None:
        with self._lock:
            runtimes = list(self._runtime_cache.values())
            self._runtime_cache.clear()
        for runtime in runtimes:
            runtime.close()
