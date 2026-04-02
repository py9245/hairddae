from __future__ import annotations

import os
from pathlib import Path
from threading import Lock
import time
from typing import Any

import numpy as np

from app.config import Settings
from app.hairddae_runtime import HairOverlayRuntime


class HairddaeRuntimeManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = Lock()
        self._runtime_cache: dict[str, tuple[HairOverlayRuntime, ...]] = {}
        self._session_slot_ttl_sec = max(60, int(os.environ.get("LOCAL_DEMO_SESSION_TTL_SEC", "180")))
        self._session_slot_map: dict[str, dict[str, int]] = {}
        self._session_slot_last_seen: dict[str, dict[str, float]] = {}
        self._next_slot_by_dataset: dict[str, int] = {}

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

    @staticmethod
    def _normalize_session_id(session_id: str | None) -> str:
        normalized = str(session_id or "").strip()
        return normalized or "anonymous"

    def _prune_session_slot_assignments_locked(self, dataset_code: str, now_monotonic: float) -> None:
        last_seen_map = self._session_slot_last_seen.get(dataset_code)
        if not last_seen_map:
            return
        expired_session_ids = [
            session_id
            for session_id, last_seen in last_seen_map.items()
            if now_monotonic - last_seen > float(self._session_slot_ttl_sec)
        ]
        if not expired_session_ids:
            return
        slot_map = self._session_slot_map.get(dataset_code)
        for session_id in expired_session_ids:
            last_seen_map.pop(session_id, None)
            if slot_map is not None:
                slot_map.pop(session_id, None)

    def _session_slot_index(self, dataset_code: str, session_id: str | None, slot_count: int) -> int:
        if slot_count <= 1:
            return 0
        normalized_session_id = self._normalize_session_id(session_id)
        now_monotonic = time.monotonic()
        with self._lock:
            self._prune_session_slot_assignments_locked(dataset_code, now_monotonic)
            slot_map = self._session_slot_map.setdefault(dataset_code, {})
            last_seen_map = self._session_slot_last_seen.setdefault(dataset_code, {})
            slot_index = slot_map.get(normalized_session_id)
            if slot_index is None:
                slot_index = self._next_slot_by_dataset.get(dataset_code, 0) % slot_count
                slot_map[normalized_session_id] = slot_index
                self._next_slot_by_dataset[dataset_code] = (slot_index + 1) % slot_count
            last_seen_map[normalized_session_id] = now_monotonic
            return slot_index

    def _runtime_pool_for_dataset(self, dataset_code: str) -> tuple[HairOverlayRuntime, ...]:
        with self._lock:
            runtime_pool = self._runtime_cache.get(dataset_code)
            if runtime_pool is not None:
                return runtime_pool

            self._configure_runtime_env()
            asset_root = self._settings.static_root / dataset_code
            runtime_pool = tuple(
                HairOverlayRuntime(
                    asset_root=asset_root,
                    model_path=self._settings.face_landmarker_model_path,
                    jpeg_quality=self._settings.http_test_jpeg_quality,
                    renderer_name=self._settings.rtc_renderer_name,
                )
                for _ in range(self._settings.rtc_runtime_slots_per_dataset)
            )
            self._runtime_cache[dataset_code] = runtime_pool
            return runtime_pool

    def _runtime_for_dataset_session(self, dataset_code: str, session_id: str | None) -> HairOverlayRuntime:
        runtime_pool = self._runtime_pool_for_dataset(dataset_code)
        slot_index = self._session_slot_index(dataset_code, session_id, len(runtime_pool))
        return runtime_pool[slot_index]

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
        runtime = self._runtime_for_dataset_session(dataset_code, session_id)
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
        runtime = self._runtime_for_dataset_session(dataset_code, session_id)
        return runtime.reference_face_bbox(session_id)

    def health(self, dataset_code: str) -> dict[str, Any]:
        runtime_pool = self._runtime_pool_for_dataset(dataset_code)
        primary_health = dict(runtime_pool[0].health())
        slot_healths = [runtime.health() for runtime in runtime_pool]
        primary_health["runtime_slots"] = len(runtime_pool)
        primary_health["slot_active_session_counts"] = [
            int(slot_health.get("active_session_count") or 0) for slot_health in slot_healths
        ]
        primary_health["active_session_count"] = sum(primary_health["slot_active_session_counts"])
        primary_health["shared_inference_lock"] = len(runtime_pool) <= 1
        primary_health["session_slot_assignment"] = "round_robin_sticky"
        return primary_health

    def reset_session(self, dataset_code: str, session_id: str) -> None:
        with self._lock:
            runtime_pool = self._runtime_cache.get(dataset_code)
        if runtime_pool is None:
            return
        slot_index = self._session_slot_index(dataset_code, session_id, len(runtime_pool))
        runtime_pool[slot_index].reset_session(session_id)

    def close(self) -> None:
        with self._lock:
            runtime_pools = list(self._runtime_cache.values())
            self._runtime_cache.clear()
            self._session_slot_map.clear()
            self._session_slot_last_seen.clear()
            self._next_slot_by_dataset.clear()
        for runtime_pool in runtime_pools:
            for runtime in runtime_pool:
                runtime.close()
