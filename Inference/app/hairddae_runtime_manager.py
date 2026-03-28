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
        os.environ["LOCAL_DEMO_USER_MASK_MAX_REUSE_FRAMES"] = str(
            self._settings.rtc_user_parsing_max_reuse_frames
        )
        os.environ["LOCAL_DEMO_USER_MASK_LATENCY_MAX_REUSE_FRAMES"] = str(
            self._settings.rtc_user_parsing_latency_max_reuse_frames
        )
        os.environ["LOCAL_DEMO_USER_MASK_REUSE_POSE_DELTA_MAX"] = str(
            self._settings.rtc_user_parsing_pose_delta_threshold_deg
        )
        os.environ["LOCAL_DEMO_USER_MASK_REUSE_CENTER_DELTA_MAX"] = str(
            self._settings.rtc_user_parsing_center_delta_threshold_norm
        )
        os.environ["LOCAL_DEMO_USER_MASK_REUSE_SIZE_DELTA_MAX"] = str(
            self._settings.rtc_user_parsing_size_delta_threshold_norm
        )
        os.environ["LOCAL_DEMO_USER_MASK_REUSE_BBOX_IOU_MIN"] = str(
            self._settings.rtc_user_parsing_bbox_iou_threshold
        )
        os.environ["LOCAL_DEMO_DISABLE_USER_PARSING_IN_LATENCY_MODE"] = (
            "1" if self._settings.rtc_disable_user_parsing_in_latency_mode else "0"
        )

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
                renderer_name=self._settings.rtc_renderer_name,
            )
            self._runtime_cache[dataset_code] = runtime
            return runtime

    def process_frame(
        self,
        *,
        dataset_code: str,
        frame_bgr: np.ndarray,
        render_frame_bgr: np.ndarray | None = None,
        source_frame_bgr: np.ndarray | None = None,
        tracked_user_row: dict[str, Any] | None = None,
        prefer_latency: bool = False,
        session_id: str,
        representative_asset_id: str | None = None,
        encode_output: bool = True,
    ) -> dict[str, Any]:
        runtime = self._runtime_for_dataset(dataset_code)
        renderer_name = (
            self._settings.rtc_latency_renderer_name
            if prefer_latency and self._settings.rtc_latency_renderer_name
            else self._settings.rtc_renderer_name
        )
        return runtime.process_frame(
            frame_bgr,
            renderer_name=renderer_name,
            render_frame_bgr=render_frame_bgr,
            source_frame_bgr=source_frame_bgr,
            tracked_user_row=tracked_user_row,
            prefer_latency=prefer_latency,
            session_id=session_id,
            representative_asset_id=representative_asset_id,
            encode_output=encode_output,
        )

    def reference_face_bbox(self, dataset_code: str, session_id: str) -> dict[str, Any] | None:
        runtime = self._runtime_for_dataset(dataset_code)
        return runtime.reference_face_bbox(session_id)

    def health(self, dataset_code: str) -> dict[str, Any]:
        runtime = self._runtime_for_dataset(dataset_code)
        return runtime.health()

    def reset_session(self, dataset_code: str, session_id: str) -> None:
        with self._lock:
            runtime = self._runtime_cache.get(dataset_code)
        if runtime is None:
            return
        runtime.reset_session(session_id)

    def close(self) -> None:
        with self._lock:
            runtimes = list(self._runtime_cache.values())
            self._runtime_cache.clear()
        for runtime in runtimes:
            runtime.close()
