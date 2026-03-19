from __future__ import annotations

import os
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np


TOOLS_DIR = Path(__file__).resolve().parents[1] / "hairddae_tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from face_feature_utils import build_landmarker, extract_feature_from_frame_bgr
from local_demo_paths import default_face_landmarker_model_path, generated_root, read_json
from realtime_face_parsing import RuntimeFaceParsing
from run_hair_overlay_poc import (
    AVAILABLE_RENDERERS,
    DEFAULT_RENDERER,
    asset_crop_edge_risk,
    asset_rank_score,
    compose_overlay_blend_frame,
    normalize_renderer_name,
    pose_distance,
    select_best_assets,
)


@dataclass
class RuntimeSessionState:
    session_id: str
    active_renderer_name: str
    smoothed_user_row: dict[str, Any] | None = None
    selected_asset: dict[str, Any] | None = None
    blend_assets: list[tuple[dict[str, Any], float]] = field(default_factory=list)
    frames_since_switch: int = 0
    transition: dict[str, Any] | None = None
    missing_face_count: int = 0
    invalid_face_count: int = 0
    user_mask_bundle: dict[str, Any] | None = None
    stable_user_mask_bundle: dict[str, Any] | None = None
    stable_user_mask_row: dict[str, Any] | None = None
    user_mask_reuse_age: int = 0
    last_seen_monotonic: float = 0.0
    last_selection_trace: dict[str, Any] | None = None


def jpeg_params(jpeg_quality: int) -> list[int]:
    return [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality]


def lerp(prev_value: float, current_value: float, alpha: float) -> float:
    return prev_value + (current_value - prev_value) * alpha


def blend_point(prev_point: dict[str, Any], current_point: dict[str, Any], alpha: float) -> dict[str, float]:
    return {
        "x": round(lerp(float(prev_point["x"]), float(current_point["x"]), alpha), 3),
        "y": round(lerp(float(prev_point["y"]), float(current_point["y"]), alpha), 3),
        "confidence": round(lerp(float(prev_point.get("confidence", 1.0)), float(current_point.get("confidence", 1.0)), alpha), 4),
    }


class HairOverlayRuntime:
    def __init__(
        self,
        asset_root: str | Path | None = None,
        model_path: str | Path | None = None,
        jpeg_quality: int = 88,
        renderer_name: str = DEFAULT_RENDERER,
    ) -> None:
        self.asset_root = Path(asset_root or (generated_root() / "asset_factory_v0")).resolve()
        self.model_path = Path(model_path).expanduser() if model_path else default_face_landmarker_model_path()
        self.jpeg_quality = jpeg_quality
        self.approved_only_mode = str(os.environ.get("LOCAL_DEMO_APPROVED_ONLY", "")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.approved_strict_only_mode = str(os.environ.get("LOCAL_DEMO_APPROVED_STRICT_ONLY", "")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.session_ttl_sec = max(60, int(os.environ.get("LOCAL_DEMO_SESSION_TTL_SEC", "180")))
        self.session_limit = max(4, int(os.environ.get("LOCAL_DEMO_SESSION_LIMIT", "128")))
        self.user_mask_max_reuse_frames = max(0, int(os.environ.get("LOCAL_DEMO_USER_MASK_MAX_REUSE_FRAMES", "1")))
        self.user_mask_latency_max_reuse_frames = max(
            self.user_mask_max_reuse_frames,
            int(os.environ.get("LOCAL_DEMO_USER_MASK_LATENCY_MAX_REUSE_FRAMES", "2")),
        )
        self.user_mask_reuse_pose_delta_max = float(
            os.environ.get("LOCAL_DEMO_USER_MASK_REUSE_POSE_DELTA_MAX", "1.2")
        )
        self.user_mask_reuse_center_delta_max = float(
            os.environ.get("LOCAL_DEMO_USER_MASK_REUSE_CENTER_DELTA_MAX", "0.018")
        )
        self.user_mask_reuse_size_delta_max = float(
            os.environ.get("LOCAL_DEMO_USER_MASK_REUSE_SIZE_DELTA_MAX", "0.018")
        )
        self.user_mask_reuse_bbox_iou_min = float(
            os.environ.get("LOCAL_DEMO_USER_MASK_REUSE_BBOX_IOU_MIN", "0.86")
        )
        self._lock = threading.Lock()
        self._landmarker = build_landmarker(self.model_path, num_faces=3)
        self._user_parser: RuntimeFaceParsing | None = None
        self._current_session: RuntimeSessionState | None = None
        self._sessions: dict[str, RuntimeSessionState] = {}
        self.user_parsing_ready = False
        self.user_parsing_error: str | None = None
        self.available_renderers = [name for name in AVAILABLE_RENDERERS if name != "mesh_v4"]
        self._ensure_user_parser()
        if self.user_parsing_ready:
            self.available_renderers = list(AVAILABLE_RENDERERS)
        requested_renderer = normalize_renderer_name(renderer_name)
        if requested_renderer in self.available_renderers:
            self.default_renderer_name = requested_renderer
        elif requested_renderer == "mesh_v4" and "mesh_v3" in self.available_renderers:
            self.default_renderer_name = "mesh_v3"
        else:
            self.default_renderer_name = DEFAULT_RENDERER
        self._load_assets()

    def _init_user_parser(self) -> None:
        try:
            self._user_parser = RuntimeFaceParsing()
            self.user_parsing_ready = bool(self._user_parser.ready)
            self.user_parsing_error = None
        except Exception as exc:
            self._user_parser = None
            self.user_parsing_ready = False
            self.user_parsing_error = str(exc)

    def _ensure_user_parser(self) -> None:
        if self._user_parser is not None or self.user_parsing_ready:
            return
        self._init_user_parser()
        if self.user_parsing_ready and "mesh_v4" not in self.available_renderers:
            self.available_renderers = list(AVAILABLE_RENDERERS)

    def _require_session(self) -> RuntimeSessionState:
        if self._current_session is None:
            raise RuntimeError("Runtime session context is not initialized")
        return self._current_session

    def _reset_session_state(self, session: RuntimeSessionState) -> None:
        session.smoothed_user_row = None
        session.selected_asset = None
        session.blend_assets = []
        session.frames_since_switch = 0
        session.transition = None
        session.missing_face_count = 0
        session.invalid_face_count = 0
        session.user_mask_bundle = None
        session.stable_user_mask_bundle = None
        session.stable_user_mask_row = None
        session.user_mask_reuse_age = 0
        session.last_selection_trace = None

    @staticmethod
    def _sanitize_session_id(session_id: str | None) -> str:
        raw_value = str(session_id or "").strip()
        if not raw_value:
            return "anonymous"
        sanitized = re.sub(r"[^a-zA-Z0-9_-]+", "_", raw_value)[:64].strip("_")
        return sanitized or "anonymous"

    def _prune_expired_sessions(self, now_monotonic: float | None = None) -> None:
        now_value = time.monotonic() if now_monotonic is None else now_monotonic
        expired_session_ids = [
            session_id
            for session_id, session in self._sessions.items()
            if now_value - session.last_seen_monotonic > float(self.session_ttl_sec)
        ]
        for session_id in expired_session_ids:
            self._sessions.pop(session_id, None)

    def _get_or_create_session(self, session_id: str | None) -> RuntimeSessionState:
        normalized_session_id = self._sanitize_session_id(session_id)
        now_monotonic = time.monotonic()
        self._prune_expired_sessions(now_monotonic)
        session = self._sessions.get(normalized_session_id)
        if session is None:
            if len(self._sessions) >= self.session_limit:
                oldest_session_id = min(
                    self._sessions.items(),
                    key=lambda item: item[1].last_seen_monotonic,
                )[0]
                self._sessions.pop(oldest_session_id, None)
            session = RuntimeSessionState(
                session_id=normalized_session_id,
                active_renderer_name=self.default_renderer_name,
                last_seen_monotonic=now_monotonic,
            )
            self._sessions[normalized_session_id] = session
        session.last_seen_monotonic = now_monotonic
        return session

    def reference_face_bbox(self, session_id: str | None) -> dict[str, Any] | None:
        with self._lock:
            session = self._get_or_create_session(session_id)
            user_row = session.smoothed_user_row
            if not user_row:
                return None
            face_bbox = user_row.get("face_bbox")
            return face_bbox if isinstance(face_bbox, dict) else None

    @property
    def _smoothed_user_row(self) -> dict[str, Any] | None:
        return self._require_session().smoothed_user_row

    @_smoothed_user_row.setter
    def _smoothed_user_row(self, value: dict[str, Any] | None) -> None:
        self._require_session().smoothed_user_row = value

    @property
    def _selected_asset(self) -> dict[str, Any] | None:
        return self._require_session().selected_asset

    @_selected_asset.setter
    def _selected_asset(self, value: dict[str, Any] | None) -> None:
        self._require_session().selected_asset = value

    @property
    def _blend_assets(self) -> list[tuple[dict[str, Any], float]]:
        return self._require_session().blend_assets

    @_blend_assets.setter
    def _blend_assets(self, value: list[tuple[dict[str, Any], float]]) -> None:
        self._require_session().blend_assets = value

    @property
    def _frames_since_switch(self) -> int:
        return self._require_session().frames_since_switch

    @_frames_since_switch.setter
    def _frames_since_switch(self, value: int) -> None:
        self._require_session().frames_since_switch = value

    @property
    def _transition(self) -> dict[str, Any] | None:
        return self._require_session().transition

    @_transition.setter
    def _transition(self, value: dict[str, Any] | None) -> None:
        self._require_session().transition = value

    @property
    def _missing_face_count(self) -> int:
        return self._require_session().missing_face_count

    @_missing_face_count.setter
    def _missing_face_count(self, value: int) -> None:
        self._require_session().missing_face_count = value

    @property
    def _invalid_face_count(self) -> int:
        return self._require_session().invalid_face_count

    @_invalid_face_count.setter
    def _invalid_face_count(self, value: int) -> None:
        self._require_session().invalid_face_count = value

    @property
    def _user_mask_bundle(self) -> dict[str, Any] | None:
        return self._require_session().user_mask_bundle

    @_user_mask_bundle.setter
    def _user_mask_bundle(self, value: dict[str, Any] | None) -> None:
        self._require_session().user_mask_bundle = value

    @property
    def _stable_user_mask_bundle(self) -> dict[str, Any] | None:
        return self._require_session().stable_user_mask_bundle

    @_stable_user_mask_bundle.setter
    def _stable_user_mask_bundle(self, value: dict[str, Any] | None) -> None:
        self._require_session().stable_user_mask_bundle = value

    @property
    def _stable_user_mask_row(self) -> dict[str, Any] | None:
        return self._require_session().stable_user_mask_row

    @_stable_user_mask_row.setter
    def _stable_user_mask_row(self, value: dict[str, Any] | None) -> None:
        self._require_session().stable_user_mask_row = value

    @property
    def _user_mask_reuse_age(self) -> int:
        return self._require_session().user_mask_reuse_age

    @_user_mask_reuse_age.setter
    def _user_mask_reuse_age(self, value: int) -> None:
        self._require_session().user_mask_reuse_age = value

    @property
    def _active_renderer_name(self) -> str:
        return self._require_session().active_renderer_name

    @_active_renderer_name.setter
    def _active_renderer_name(self, value: str) -> None:
        self._require_session().active_renderer_name = value

    @property
    def _last_selection_trace(self) -> dict[str, Any] | None:
        return self._require_session().last_selection_trace

    @_last_selection_trace.setter
    def _last_selection_trace(self, value: dict[str, Any] | None) -> None:
        self._require_session().last_selection_trace = value

    @staticmethod
    def _asset_preference_key(asset_row: dict[str, Any]) -> tuple[Any, ...]:
        return (
            0 if asset_row.get("approved") else 1,
            -float(asset_row.get("quality_score") or 0.0),
            float(asset_row.get("naturalness_risk_v1") or 0.0),
            len(asset_row.get("naturalness_failure_tags_v1") or []),
            len(asset_row.get("critical_failure_tags") or []),
            len(asset_row.get("failure_tags") or []),
            -float(asset_row.get("hair_mean_confidence") or 0.0),
            asset_row["asset_id"],
        )

    @staticmethod
    def _crop_risk_bucket(risk_score: float) -> int:
        if risk_score <= 0.18:
            return 0
        if risk_score <= 0.30:
            return 1
        if risk_score <= 0.45:
            return 2
        return 3

    def _asset_crop_risk(self, asset_row: dict[str, Any]) -> float:
        cached_risk = asset_row.get("_crop_edge_risk")
        if cached_risk is not None:
            return float(cached_risk)
        metadata_path = str(asset_row.get("metadata_path") or "")
        if not metadata_path:
            asset_row["_crop_edge_risk"] = 0.0
            return 0.0
        try:
            risk_score = float(asset_crop_edge_risk(str(self.asset_root), metadata_path))
        except Exception:
            risk_score = 0.0
        asset_row["_crop_edge_risk"] = round(risk_score, 6)
        return float(asset_row["_crop_edge_risk"])

    def _choose_pose_representative(self, pose_rows: list[dict[str, Any]]) -> dict[str, Any]:
        ranked_rows = sorted(pose_rows, key=self._asset_preference_key)
        if len(ranked_rows) <= 1:
            return ranked_rows[0]

        top_rows = ranked_rows[: min(len(ranked_rows), 4)]
        top_row = top_rows[0]
        top_risk = self._asset_crop_risk(top_row)
        top_bucket = self._crop_risk_bucket(top_risk)
        if top_bucket <= 1:
            return top_row

        safer_candidates: list[tuple[int, float, int, float, dict[str, Any]]] = []
        for index, row in enumerate(top_rows[1:], start=1):
            risk_score = self._asset_crop_risk(row)
            risk_bucket = self._crop_risk_bucket(risk_score)
            if risk_bucket >= top_bucket:
                continue
            if risk_score > top_risk - 0.08:
                continue
            safer_candidates.append(
                (
                    risk_bucket,
                    risk_score,
                    index,
                    -float(row.get("quality_score") or 0.0),
                    row,
                )
            )

        if not safer_candidates:
            return top_row

        safer_candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3], item[4]["asset_id"]))
        return safer_candidates[0][4]

    def _pose_representatives(self, asset_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_pose_key: dict[str, list[dict[str, Any]]] = {}
        for row in asset_rows:
            by_pose_key.setdefault(row["pose_key"], []).append(row)
        representatives = [
            self._choose_pose_representative(pose_rows)
            for pose_rows in by_pose_key.values()
        ]
        return sorted(
            representatives,
            key=lambda row: (row["pitch_1deg"], row["yaw_1deg"], row["roll_1deg"], row["asset_id"]),
        )

    @staticmethod
    def _is_extreme_downward_face_overlap_asset(asset_row: dict[str, Any]) -> bool:
        pitch_value = int(asset_row.get("pitch_1deg") or 0)
        naturalness_risk = float(asset_row.get("naturalness_risk_v1") or 0.0)
        face_overlap_ratio = float(asset_row.get("face_overlap_ratio") or 0.0)
        naturalness_tags = set(asset_row.get("naturalness_failure_tags_v1") or [])
        quality_status = str(asset_row.get("quality_status") or "")
        if pitch_value < 16:
            return False
        if "face_skin_overlap_risk" in naturalness_tags or "downward_face_cover_risk" in naturalness_tags:
            return True
        if pitch_value >= 24:
            if quality_status != "approved":
                return True
            return naturalness_risk >= 0.05 or face_overlap_ratio >= 0.01
        if pitch_value >= 20:
            if quality_status != "approved" and (naturalness_risk >= 0.04 or face_overlap_ratio >= 0.008):
                return True
            return naturalness_risk >= 0.055 or face_overlap_ratio >= 0.012
        if quality_status != "approved" and (naturalness_risk >= 0.05 or face_overlap_ratio >= 0.01):
            return True
        return False

    @staticmethod
    def _asset_trace_summary(asset_row: dict[str, Any] | None, score: float | None = None) -> dict[str, Any] | None:
        if asset_row is None:
            return None
        return {
            "asset_id": str(asset_row.get("asset_id") or ""),
            "pose_key": str(asset_row.get("pose_key") or ""),
            "quality_status": str(asset_row.get("quality_status") or ""),
            "approved": bool(asset_row.get("approved")),
            "approved_runtime": bool(asset_row.get("approved_runtime")),
            "approved_strict": bool(asset_row.get("approved_strict")),
            "quality_score": round(float(asset_row.get("quality_score") or 0.0), 6),
            "naturalness_risk_v1": round(float(asset_row.get("naturalness_risk_v1") or 0.0), 6),
            "face_overlap_ratio": round(float(asset_row.get("face_overlap_ratio") or 0.0), 6),
            "failure_tags": list(asset_row.get("failure_tags") or []),
            "naturalness_failure_tags_v1": list(asset_row.get("naturalness_failure_tags_v1") or []),
            "score": None if score is None else round(float(score), 6),
        }

    def _build_selection_trace(
        self,
        user_row: dict[str, Any],
        ranked_assets: list[tuple[dict[str, Any], float]],
        selected_asset: dict[str, Any] | None,
        selected_score: float | None,
        selection_mode: str,
        current_asset: dict[str, Any] | None = None,
        current_score: float | None = None,
        blend_assets: list[tuple[dict[str, Any], float]] | None = None,
    ) -> dict[str, Any]:
        top_candidates: list[dict[str, Any]] = []
        for rank, (asset_row, score) in enumerate(ranked_assets[:5], start=1):
            candidate_summary = self._asset_trace_summary(asset_row, score)
            if candidate_summary is None:
                continue
            candidate_summary["rank"] = rank
            candidate_summary["pose_distance"] = round(pose_distance(user_row["pose"], asset_row), 6)
            top_candidates.append(candidate_summary)

        return {
            "decision": selection_mode,
            "selected": self._asset_trace_summary(selected_asset, selected_score),
            "current": self._asset_trace_summary(current_asset, current_score),
            "top_candidates": top_candidates,
            "blend_asset_ids": [str(asset_row["asset_id"]) for asset_row, _ in (blend_assets or [])],
        }

    def _load_assets(self) -> None:
        asset_index_path = self.asset_root / "manifests" / "asset_index_v0.json"
        asset_blacklist_path = self.asset_root / "manifests" / "runtime_asset_blacklist.json"
        if not asset_index_path.is_file():
            raise FileNotFoundError(
                f"Missing asset index: {asset_index_path}. Run build_local_demo_assets.py first."
            )
        payload = read_json(asset_index_path)
        all_assets = payload.get("items", [])
        blacklisted_asset_ids: set[str] = set()
        if asset_blacklist_path.is_file():
            blacklist_payload = read_json(asset_blacklist_path)
            blacklisted_asset_ids = {
                str(asset_id).strip()
                for asset_id in blacklist_payload.get("asset_ids", [])
                if str(asset_id).strip()
            }
        if blacklisted_asset_ids:
            all_assets = [
                row
                for row in all_assets
                if str(row.get("asset_id") or "") not in blacklisted_asset_ids
            ]
        approved_assets = [row for row in all_assets if row.get("approved")]
        approved_runtime_assets = [row for row in all_assets if row.get("approved_runtime")]
        approved_strict_assets = [row for row in all_assets if row.get("approved_strict")]
        if self.approved_strict_only_mode:
            runtime_source = approved_strict_assets
        elif self.approved_only_mode:
            runtime_source = approved_runtime_assets or approved_assets
        else:
            # Keep broad pose coverage, but do not allow explicitly rejected assets
            # (crop/anchor failure or critical naturalness failure) to reach runtime.
            runtime_source = [
                row
                for row in all_assets
                if str(row.get("quality_status") or "") != "rejected"
                and not bool(row.get("has_critical_failures"))
                and not bool(row.get("has_critical_naturalness_failures"))
                and not self._is_extreme_downward_face_overlap_asset(row)
            ]
        if not runtime_source:
            runtime_source = all_assets
        self.assets = self._pose_representatives(runtime_source)
        if not self.assets:
            raise RuntimeError(f"No assets available in {asset_index_path}")
        self.asset_count = len(all_assets)
        self.approved_asset_count = len(approved_assets)
        self.approved_runtime_asset_count = len(approved_runtime_assets)
        self.approved_strict_asset_count = len(approved_strict_assets)
        self.blacklisted_asset_count = len(blacklisted_asset_ids)
        self.runtime_asset_count = len(self.assets)
        self.unique_pose_count = len({row["pose_key"] for row in runtime_source})
        pitch_values = [int(row["pitch_1deg"]) for row in self.assets]
        self.pitch_range = {
            "min": min(pitch_values),
            "max": max(pitch_values),
            "high_pitch_pose_count": sum(1 for value in pitch_values if value >= 20),
        }
        self._sessions.clear()

    def reload_assets(self) -> None:
        with self._lock:
            self._load_assets()

    def health(self) -> dict[str, Any]:
        with self._lock:
            self._prune_expired_sessions()
            active_session_count = len(self._sessions)
        return {
            "ready": True,
            "asset_root": str(self.asset_root),
            "model_path": str(self.model_path),
            "asset_count": self.asset_count,
            "approved_asset_count": self.approved_asset_count,
            "approved_runtime_asset_count": self.approved_runtime_asset_count,
            "approved_strict_asset_count": self.approved_strict_asset_count,
            "blacklisted_asset_count": self.blacklisted_asset_count,
            "runtime_asset_count": self.runtime_asset_count,
            "unique_pose_count": self.unique_pose_count,
            "pitch_range": self.pitch_range,
            "jpeg_quality": self.jpeg_quality,
            "default_renderer": self.default_renderer_name,
            "active_renderer": self.default_renderer_name,
            "available_renderers": self.available_renderers,
            "user_parsing_ready": self.user_parsing_ready,
            "user_parsing_error": self.user_parsing_error,
            "active_session_count": active_session_count,
            "session_ttl_sec": self.session_ttl_sec,
            "session_isolation_mode": "per_session",
            "shared_inference_lock": True,
            "approved_only_mode": self.approved_only_mode,
            "approved_strict_only_mode": self.approved_strict_only_mode,
        }

    def _set_active_renderer(self, renderer_name: str | None) -> str:
        resolved_renderer = normalize_renderer_name(renderer_name or self.default_renderer_name)
        if resolved_renderer == "mesh_v4":
            self._ensure_user_parser()
        if resolved_renderer == "mesh_v4" and not self.user_parsing_ready:
            resolved_renderer = "mesh_v3"
        if resolved_renderer != self._active_renderer_name:
            self._transition = None
            self._blend_assets = []
            self._frames_since_switch = 0
            self._active_renderer_name = resolved_renderer
        return resolved_renderer

    @staticmethod
    def _renderer_requires_user_parsing(renderer_name: str, user_row: dict[str, Any] | None = None) -> bool:
        normalized = normalize_renderer_name(renderer_name)
        if normalized == "mesh_v4":
            return True
        if normalized != "mesh_v3" or user_row is None:
            return False
        pose = user_row.get("pose", {}) if isinstance(user_row, dict) else {}
        yaw_value = abs(float(pose.get("yaw_1deg", 0.0)))
        pitch_value = abs(float(pose.get("pitch_1deg", 0.0)))
        return yaw_value >= 10.0 or pitch_value >= 6.0

    @staticmethod
    def _bbox_iou(lhs_bbox: dict[str, Any] | None, rhs_bbox: dict[str, Any] | None) -> float:
        if not lhs_bbox or not rhs_bbox:
            return 0.0
        lhs_x0 = float(lhs_bbox.get("x", 0.0))
        lhs_y0 = float(lhs_bbox.get("y", 0.0))
        lhs_x1 = lhs_x0 + float(lhs_bbox.get("w", 0.0))
        lhs_y1 = lhs_y0 + float(lhs_bbox.get("h", 0.0))
        rhs_x0 = float(rhs_bbox.get("x", 0.0))
        rhs_y0 = float(rhs_bbox.get("y", 0.0))
        rhs_x1 = rhs_x0 + float(rhs_bbox.get("w", 0.0))
        rhs_y1 = rhs_y0 + float(rhs_bbox.get("h", 0.0))
        inter_x0 = max(lhs_x0, rhs_x0)
        inter_y0 = max(lhs_y0, rhs_y0)
        inter_x1 = min(lhs_x1, rhs_x1)
        inter_y1 = min(lhs_y1, rhs_y1)
        inter_w = max(0.0, inter_x1 - inter_x0)
        inter_h = max(0.0, inter_y1 - inter_y0)
        inter_area = inter_w * inter_h
        lhs_area = max(0.0, lhs_x1 - lhs_x0) * max(0.0, lhs_y1 - lhs_y0)
        rhs_area = max(0.0, rhs_x1 - rhs_x0) * max(0.0, rhs_y1 - rhs_y0)
        denominator = lhs_area + rhs_area - inter_area
        if denominator <= 0.0:
            return 0.0
        return inter_area / denominator

    @staticmethod
    def _mask_ratio(mask_layer: Any) -> float:
        if mask_layer is None:
            return 0.0
        mask_array = np.asarray(mask_layer)
        if mask_array.size <= 0:
            return 0.0
        if mask_array.dtype.kind == "f":
            return float(np.mean(np.clip(mask_array.astype(np.float32), 0.0, 1.0)))
        return float(np.count_nonzero(mask_array)) / float(mask_array.shape[0] * mask_array.shape[1])

    @staticmethod
    def _blend_mask_layer(previous_layer: Any, current_layer: Any, current_alpha: float) -> Any:
        if previous_layer is None:
            return current_layer
        if current_layer is None:
            return previous_layer
        previous_array = np.asarray(previous_layer)
        current_array = np.asarray(current_layer)
        if previous_array.shape != current_array.shape:
            return current_layer
        if previous_array.dtype.kind == "f" or current_array.dtype.kind == "f":
            previous_float = previous_array.astype(np.float32)
            current_float = current_array.astype(np.float32)
            return (previous_float * (1.0 - current_alpha) + current_float * current_alpha).astype(np.float32)
        blended = cv2.addWeighted(
            previous_array.astype(np.float32),
            1.0 - current_alpha,
            current_array.astype(np.float32),
            current_alpha,
            0.0,
        )
        return np.clip(blended, 0.0, 255.0).astype(np.uint8)

    def _recompute_user_mask_metrics(self, mask_bundle: dict[str, Any]) -> None:
        metrics = {
            "hair_area_ratio": round(self._mask_ratio(mask_bundle.get("hair_mask")), 6),
            "face_area_ratio": round(self._mask_ratio(mask_bundle.get("face_mask")), 6),
            "blur_area_ratio": round(self._mask_ratio(mask_bundle.get("blur_mask")), 6),
            "forehead_area_ratio": round(self._mask_ratio(mask_bundle.get("forehead_mask")), 6),
            "ear_left_area_ratio": round(self._mask_ratio(mask_bundle.get("ear_left_mask")), 6),
            "ear_right_area_ratio": round(self._mask_ratio(mask_bundle.get("ear_right_mask")), 6),
            "neck_area_ratio": round(self._mask_ratio(mask_bundle.get("neck_shoulder_mask")), 6),
            "protect_face_area_ratio": round(self._mask_ratio(mask_bundle.get("protect_face_mask")), 6),
            "head_area_ratio": round(self._mask_ratio(mask_bundle.get("head_silhouette_mask")), 6),
        }
        mask_bundle["metrics"] = metrics

    def _build_runtime_fit_context(
        self,
        user_row: dict[str, Any],
        user_mask_bundle: dict[str, Any] | None,
    ) -> dict[str, Any]:
        pose = user_row.get("pose", {})
        context = {
            "enabled": bool(user_mask_bundle),
            "yaw_1deg": int(pose.get("yaw_1deg", 0) or 0),
            "pitch_1deg": int(pose.get("pitch_1deg", 0) or 0),
            "hair_area_ratio": 0.0,
            "head_area_ratio": 0.0,
            "forehead_area_ratio": 0.0,
            "ear_left_area_ratio": 0.0,
            "ear_right_area_ratio": 0.0,
            "neck_area_ratio": 0.0,
            "protect_face_area_ratio": 0.0,
            "blur_area_ratio": 0.0,
        }
        if not user_mask_bundle:
            return context
        metrics = user_mask_bundle.get("metrics") or {}
        for key in (
            "hair_area_ratio",
            "head_area_ratio",
            "forehead_area_ratio",
            "ear_left_area_ratio",
            "ear_right_area_ratio",
            "neck_area_ratio",
            "protect_face_area_ratio",
            "blur_area_ratio",
        ):
            context[key] = round(float(metrics.get(key) or 0.0), 6)
        return context

    def _attach_runtime_fit_context(
        self,
        user_row: dict[str, Any],
        user_mask_bundle: dict[str, Any] | None,
    ) -> dict[str, Any]:
        user_row["_runtime_fit_context"] = self._build_runtime_fit_context(user_row, user_mask_bundle)
        return user_row

    def _stabilize_user_mask_bundle(
        self,
        mask_bundle: dict[str, Any],
        user_row: dict[str, Any],
    ) -> tuple[dict[str, Any], str]:
        previous_bundle = self._stable_user_mask_bundle
        previous_row = self._stable_user_mask_row
        if previous_bundle is None or previous_row is None:
            self._recompute_user_mask_metrics(mask_bundle)
            self._stable_user_mask_bundle = mask_bundle
            self._stable_user_mask_row = user_row
            self._user_mask_bundle = mask_bundle
            self._user_mask_reuse_age = 0
            return mask_bundle, "ok"

        motion = user_row.get("_motion", {})
        fast_motion = bool(motion.get("fast"))
        moderate_motion = bool(motion.get("moderate"))
        bbox_iou = self._bbox_iou(previous_row.get("face_bbox"), user_row.get("face_bbox"))
        current_metrics = mask_bundle.get("metrics") or {}
        previous_metrics = previous_bundle.get("metrics") or {}
        current_hair_ratio = float(current_metrics.get("hair_area_ratio") or 0.0)
        previous_hair_ratio = float(previous_metrics.get("hair_area_ratio") or 0.0)
        current_blur_ratio = float(current_metrics.get("blur_area_ratio") or 0.0)
        previous_blur_ratio = float(previous_metrics.get("blur_area_ratio") or 0.0)
        hair_ratio_scale = (
            current_hair_ratio / max(previous_hair_ratio, 1e-6)
            if current_hair_ratio > 1e-6 and previous_hair_ratio > 1e-6
            else 1.0
        )
        blur_ratio_scale = (
            current_blur_ratio / max(previous_blur_ratio, 1e-6)
            if current_blur_ratio > 1e-6 and previous_blur_ratio > 1e-6
            else 1.0
        )
        suspicious_jump = (
            not fast_motion
            and bbox_iou >= 0.55
            and (
                hair_ratio_scale < 0.68
                or hair_ratio_scale > 1.48
                or blur_ratio_scale < 0.66
                or blur_ratio_scale > 1.52
            )
        )
        if suspicious_jump:
            self._user_mask_bundle = previous_bundle
            self._user_mask_reuse_age = min(
                self._user_mask_reuse_age + 1,
                max(self.user_mask_latency_max_reuse_frames, self.user_mask_max_reuse_frames),
            )
            return previous_bundle, "hold_previous_mask"

        if fast_motion or bbox_iou < 0.30:
            stabilized_bundle = mask_bundle
            status = "ok"
        else:
            current_alpha = 0.88 if moderate_motion else 0.68
            stabilized_bundle: dict[str, Any] = {}
            blend_keys = {
                "hair_confidence",
                "hair_mask",
                "face_mask",
                "forehead_mask",
                "ear_left_mask",
                "ear_right_mask",
                "neck_shoulder_mask",
                "protect_face_mask",
                "suppress_prior_mask",
                "alpha_mask",
                "blur_mask",
            }
            for key, value in mask_bundle.items():
                if key in blend_keys:
                    stabilized_bundle[key] = self._blend_mask_layer(previous_bundle.get(key), value, current_alpha)
                else:
                    stabilized_bundle[key] = value
            self._recompute_user_mask_metrics(stabilized_bundle)
            status = "smoothed_mask"

        self._stable_user_mask_bundle = stabilized_bundle
        self._stable_user_mask_row = user_row
        self._user_mask_bundle = stabilized_bundle
        self._user_mask_reuse_age = 0
        return stabilized_bundle, status

    def _can_reuse_user_masks(
        self,
        user_row: dict[str, Any],
        renderer_name: str,
        *,
        prefer_latency: bool,
    ) -> bool:
        if not self._renderer_requires_user_parsing(renderer_name, user_row):
            return False
        if self._stable_user_mask_bundle is None or self._stable_user_mask_row is None:
            return False
        if int(user_row.get("candidate_face_count") or 1) > 1:
            return False
        max_reuse_frames = (
            self.user_mask_latency_max_reuse_frames
            if prefer_latency
            else self.user_mask_max_reuse_frames
        )
        if self._user_mask_reuse_age >= max_reuse_frames:
            return False
        motion = user_row.get("_motion", {})
        if bool(motion.get("fast")):
            return False
        if float(motion.get("pose_delta") or 0.0) > self.user_mask_reuse_pose_delta_max:
            return False
        if float(motion.get("center_delta_norm") or 0.0) > self.user_mask_reuse_center_delta_max:
            return False
        if float(motion.get("size_delta_norm") or 0.0) > self.user_mask_reuse_size_delta_max:
            return False
        if self._bbox_iou(self._stable_user_mask_row.get("face_bbox"), user_row.get("face_bbox")) < self.user_mask_reuse_bbox_iou_min:
            return False
        return True

    def _parse_user_masks(
        self,
        frame_bgr: np.ndarray,
        user_row: dict[str, Any],
        renderer_name: str,
        *,
        prefer_latency: bool,
    ) -> tuple[dict[str, Any] | None, str, float]:
        if not self._renderer_requires_user_parsing(renderer_name, user_row):
            self._user_mask_bundle = None
            return None, "disabled", 0.0
        self._ensure_user_parser()
        if not self.user_parsing_ready or self._user_parser is None:
            self._user_mask_bundle = None
            return None, "unavailable", 0.0
        if self._can_reuse_user_masks(user_row, renderer_name, prefer_latency=prefer_latency):
            self._user_mask_reuse_age += 1
            self._user_mask_bundle = self._stable_user_mask_bundle
            return (
                self._stable_user_mask_bundle,
                "reuse_stable_mask_latency" if prefer_latency else "reuse_stable_mask",
                0.0,
            )
        started_at = time.perf_counter()
        mask_bundle = self._user_parser.parse_frame(frame_bgr, user_row)
        latency_ms = round((time.perf_counter() - started_at) * 1000.0, 3)
        if mask_bundle is None:
            if self._stable_user_mask_bundle is not None:
                self._user_mask_reuse_age = min(
                    self._user_mask_reuse_age + 1,
                    max(self.user_mask_latency_max_reuse_frames, self.user_mask_max_reuse_frames),
                )
                self._user_mask_bundle = self._stable_user_mask_bundle
                return self._stable_user_mask_bundle, "hold_previous_mask", latency_ms
            self._user_mask_bundle = None
            return None, "no_mask", latency_ms
        stabilized_bundle, status = self._stabilize_user_mask_bundle(mask_bundle, user_row)
        return stabilized_bundle, status, latency_ms

    @staticmethod
    def _face_center(face_bbox: dict[str, Any]) -> tuple[float, float]:
        return (
            float(face_bbox["x"]) + float(face_bbox["w"]) * 0.5,
            float(face_bbox["y"]) + float(face_bbox["h"]) * 0.5,
        )

    def _is_face_tracking_outlier(self, raw_user_row: dict[str, Any]) -> bool:
        prev_row = self._smoothed_user_row
        if prev_row is None:
            return False

        raw_bbox = raw_user_row["face_bbox"]
        prev_bbox = prev_row["face_bbox"]
        raw_pose = raw_user_row["pose"]
        prev_pose = prev_row["pose"]
        prev_center_x, prev_center_y = self._face_center(prev_bbox)
        raw_center_x, raw_center_y = self._face_center(raw_bbox)
        center_delta_norm = max(
            abs(raw_center_x - prev_center_x) / max(1.0, float(prev_bbox["w"])),
            abs(raw_center_y - prev_center_y) / max(1.0, float(prev_bbox["h"])),
        )
        size_delta_norm = max(
            abs(float(raw_bbox["w"]) - float(prev_bbox["w"])) / max(1.0, float(prev_bbox["w"])),
            abs(float(raw_bbox["h"]) - float(prev_bbox["h"])) / max(1.0, float(prev_bbox["h"])),
        )
        pose_delta = max(
            abs(float(raw_pose["yaw_float"]) - float(prev_pose["yaw_float"])),
            abs(float(raw_pose["pitch_float"]) - float(prev_pose["pitch_float"])),
            abs(float(raw_pose["roll_float"]) - float(prev_pose["roll_float"])),
        )

        severe_jump = center_delta_norm > 0.72 or size_delta_norm > 0.58
        pose_break = pose_delta > 26.0 and center_delta_norm > 0.18
        identity_break = center_delta_norm > 0.40 and size_delta_norm > 0.30
        multi_face_break = (
            max(int(raw_user_row.get("candidate_face_count") or 1), int(prev_row.get("candidate_face_count") or 1)) > 1
            and (center_delta_norm > 0.24 or size_delta_norm > 0.20)
            and self._bbox_iou(prev_bbox, raw_bbox) < 0.58
        )
        return bool(severe_jump or pose_break or identity_break or multi_face_break)

    def _hold_previous_tracking_frame(
        self,
        frame_bgr: np.ndarray,
        renderer_name: str,
    ) -> tuple[dict[str, Any], np.ndarray, str | None, str | None, list[tuple[dict[str, Any], float]]]:
        held_user_row = self._smoothed_user_row
        if held_user_row is None:
            return {"ok": False}, frame_bgr.copy(), None, None, []

        held_blend_assets = self._blend_assets or ([(self._selected_asset, 1.0)] if self._selected_asset is not None else [])
        output_frame = frame_bgr.copy()
        if held_blend_assets:
            output_frame = compose_overlay_blend_frame(
                held_user_row,
                frame_bgr,
                held_blend_assets,
                self.asset_root,
                renderer_name=renderer_name,
                user_mask_bundle=self._user_mask_bundle,
            )
        selected_asset_id = None if self._selected_asset is None else str(self._selected_asset["asset_id"])
        selected_pose_key = None if self._selected_asset is None else str(self._selected_asset["pose_key"])
        return held_user_row, output_frame, selected_asset_id, selected_pose_key, list(held_blend_assets)

    def _smooth_user_row(self, user_row: dict[str, Any]) -> dict[str, Any]:
        prev_row = self._smoothed_user_row
        if prev_row is None:
            seeded_row = dict(user_row)
            seeded_row["_motion"] = {
                "pose_delta": 0.0,
                "center_delta_norm": 0.0,
                "size_delta_norm": 0.0,
                "fast": False,
                "moderate": False,
            }
            self._smoothed_user_row = seeded_row
            return seeded_row

        raw_pose = user_row["pose"]
        prev_pose = prev_row["pose"]
        raw_bbox = user_row["face_bbox"]
        prev_bbox = prev_row["face_bbox"]
        pose_delta = max(
            abs(float(raw_pose["yaw_float"]) - float(prev_pose["yaw_float"])),
            abs(float(raw_pose["pitch_float"]) - float(prev_pose["pitch_float"])),
            abs(float(raw_pose["roll_float"]) - float(prev_pose["roll_float"])),
        )
        prev_center_x, prev_center_y = self._face_center(prev_bbox)
        raw_center_x, raw_center_y = self._face_center(raw_bbox)
        center_delta_norm = max(
            abs(raw_center_x - prev_center_x) / max(1.0, float(prev_bbox["w"])),
            abs(raw_center_y - prev_center_y) / max(1.0, float(prev_bbox["h"])),
        )
        size_delta_norm = max(
            abs(float(raw_bbox["w"]) - float(prev_bbox["w"])) / max(1.0, float(prev_bbox["w"])),
            abs(float(raw_bbox["h"]) - float(prev_bbox["h"])) / max(1.0, float(prev_bbox["h"])),
        )

        pose_alpha = 0.64
        if pose_delta >= 7.0 or center_delta_norm >= 0.12:
            pose_alpha = 0.96
        elif pose_delta >= 3.0 or center_delta_norm >= 0.05:
            pose_alpha = 0.82

        geometry_alpha = 0.86
        if pose_delta >= 7.0 or center_delta_norm >= 0.10 or size_delta_norm >= 0.09:
            geometry_alpha = 1.0
        elif pose_delta >= 2.5 or center_delta_norm >= 0.04 or size_delta_norm >= 0.04:
            geometry_alpha = 0.95

        smoothed_pose = {
            "yaw_float": round(lerp(float(prev_pose["yaw_float"]), float(raw_pose["yaw_float"]), pose_alpha), 6),
            "pitch_float": round(lerp(float(prev_pose["pitch_float"]), float(raw_pose["pitch_float"]), pose_alpha), 6),
            "roll_float": round(lerp(float(prev_pose["roll_float"]), float(raw_pose["roll_float"]), pose_alpha), 6),
        }
        smoothed_pose["yaw_1deg"] = int(round(smoothed_pose["yaw_float"]))
        smoothed_pose["pitch_1deg"] = int(round(smoothed_pose["pitch_float"]))
        smoothed_pose["roll_1deg"] = int(round(smoothed_pose["roll_float"]))

        smoothed_bbox = {
            key: int(round(lerp(float(prev_bbox[key]), float(raw_bbox[key]), geometry_alpha)))
            for key in ("x", "y", "w", "h")
        }
        smoothed_anchors = {
            name: blend_point(prev_row["anchors"].get(name, point), point, geometry_alpha)
            for name, point in user_row["anchors"].items()
        }

        smoothed_row = dict(user_row)
        smoothed_row["pose"] = smoothed_pose
        smoothed_row["face_bbox"] = smoothed_bbox
        smoothed_row["anchors"] = smoothed_anchors
        smoothed_row["face_ratio"] = round(
            lerp(float(prev_row["face_ratio"]), float(user_row["face_ratio"]), geometry_alpha),
            6,
        )
        smoothed_row["_motion"] = {
            "pose_delta": round(pose_delta, 4),
            "center_delta_norm": round(center_delta_norm, 4),
            "size_delta_norm": round(size_delta_norm, 4),
            "fast": bool(pose_delta >= 7.0 or center_delta_norm >= 0.10 or size_delta_norm >= 0.09),
            "moderate": bool(pose_delta >= 3.0 or center_delta_norm >= 0.05 or size_delta_norm >= 0.04),
        }
        self._smoothed_user_row = smoothed_row
        return smoothed_row

    @staticmethod
    def _redistribute_weights(weights: list[float], primary_min_weight: float) -> list[float]:
        if not weights or len(weights) == 1 or weights[0] >= primary_min_weight:
            return weights
        remainder = max(0.0, 1.0 - primary_min_weight)
        others_total = sum(weights[1:])
        if others_total <= 0.0:
            return [1.0] + [0.0] * (len(weights) - 1)
        adjusted = [primary_min_weight]
        adjusted.extend(weight / others_total * remainder for weight in weights[1:])
        return adjusted

    @staticmethod
    def _normalize_weighted_assets(
        weighted_assets: list[tuple[dict[str, Any], float]],
    ) -> list[tuple[dict[str, Any], float]]:
        positive_assets = [(asset_row, float(weight)) for asset_row, weight in weighted_assets if float(weight) > 0.0]
        total_weight = sum(weight for _, weight in positive_assets)
        if total_weight <= 0.0:
            return []
        return [
            (asset_row, round(weight / total_weight, 6))
            for asset_row, weight in positive_assets
        ]

    def _build_blend_assets(
        self,
        user_row: dict[str, Any],
        ranked_assets: list[tuple[dict[str, Any], float]],
        primary_asset: dict[str, Any],
        selection_mode: str,
    ) -> list[tuple[dict[str, Any], float]]:
        user_pose = user_row["pose"]
        motion = user_row.get("_motion", {})
        if motion.get("fast"):
            return [(primary_asset, 1.0)]
        renderer_name = self._active_renderer_name
        mesh_dense_renderer = renderer_name in {"mesh_v2", "mesh_v3", "mesh_v4"}
        side_view_yaw = self._side_view_yaw(user_row, primary_asset)
        vertical_view_pitch = self._vertical_view_pitch(user_row, primary_asset)
        if mesh_dense_renderer and (selection_mode != "stable" or side_view_yaw >= 18 or vertical_view_pitch >= 12):
            return [(primary_asset, 1.0)]
        candidates: list[tuple[dict[str, Any], float]] = []
        seen_ids: set[str] = set()

        def append_candidate(asset_row: dict[str, Any], score: float | None = None) -> None:
            asset_id = str(asset_row["asset_id"])
            if asset_id in seen_ids:
                return
            seen_ids.add(asset_id)
            resolved_score = asset_rank_score(user_row, asset_row) if score is None else score
            candidates.append((asset_row, resolved_score))

        append_candidate(primary_asset)
        for asset_row, score in ranked_assets:
            append_candidate(asset_row, score)

        primary_pose_gap = pose_distance(user_pose, primary_asset)
        selected_candidates = [candidates[0]]
        for asset_row, score in candidates[1:]:
            yaw_gap = abs(user_pose["yaw_1deg"] - int(asset_row["yaw_1deg"]))
            pitch_gap = abs(user_pose["pitch_1deg"] - int(asset_row["pitch_1deg"]))
            roll_gap = abs(user_pose["roll_1deg"] - int(asset_row["roll_1deg"]))
            candidate_pose_gap = pose_distance(user_pose, asset_row)
            if yaw_gap > 8 or pitch_gap > 7 or roll_gap > 5:
                continue
            if candidate_pose_gap > primary_pose_gap + 12.0:
                continue
            if score > selected_candidates[0][1] + 12.0:
                continue
            selected_candidates.append((asset_row, score))
            if len(selected_candidates) >= 2:
                break

        if len(selected_candidates) == 1:
            return [(primary_asset, 1.0)]

        min_score = min(score for _, score in selected_candidates)
        raw_weights: list[float] = []
        for asset_row, score in selected_candidates:
            pose_gap = max(0.75, pose_distance(user_pose, asset_row))
            relative_score = max(0.0, score - min_score)
            weight = 1.0 / (0.8 + pose_gap + 0.35 * relative_score)
            if asset_row["asset_id"] == primary_asset["asset_id"]:
                weight *= 1.20 if selection_mode == "switch" else 1.45
            raw_weights.append(weight)

        total_weight = sum(raw_weights)
        if total_weight <= 0.0:
            return [(primary_asset, 1.0)]

        normalized_weights = [weight / total_weight for weight in raw_weights]
        primary_min_weight = 0.60 if selection_mode == "switch" else 0.72
        normalized_weights = self._redistribute_weights(normalized_weights, primary_min_weight)
        weighted_assets = [
            (asset_row, round(weight, 6))
            for (asset_row, _), weight in zip(selected_candidates, normalized_weights)
            if weight > 0.0
        ]
        if not mesh_dense_renderer or len(weighted_assets) <= 1:
            return weighted_assets

        primary_weight = float(weighted_assets[0][1])
        if primary_weight >= 0.84:
            return [(primary_asset, 1.0)]

        primary_score = float(selected_candidates[0][1])
        conservative_assets = [weighted_assets[0]]
        for (asset_row, score), (_, weight) in zip(selected_candidates[1:], weighted_assets[1:]):
            yaw_gap = abs(user_pose["yaw_1deg"] - int(asset_row["yaw_1deg"]))
            pitch_gap = abs(user_pose["pitch_1deg"] - int(asset_row["pitch_1deg"]))
            roll_gap = abs(user_pose["roll_1deg"] - int(asset_row["roll_1deg"]))
            if yaw_gap > 3 or pitch_gap > 3 or roll_gap > 2:
                continue
            if float(score) > primary_score + 4.0:
                continue
            if float(weight) < 0.18:
                continue
            conservative_assets.append((asset_row, float(weight)))
            break

        if len(conservative_assets) <= 1:
            return [(primary_asset, 1.0)]
        return self._normalize_weighted_assets(conservative_assets)

    @staticmethod
    def _side_view_yaw(user_row: dict[str, Any], *asset_rows: dict[str, Any]) -> int:
        yaw_values = [abs(int(user_row["pose"]["yaw_1deg"]))]
        yaw_values.extend(abs(int(asset_row["yaw_1deg"])) for asset_row in asset_rows if asset_row is not None)
        return max(yaw_values)

    @staticmethod
    def _vertical_view_pitch(user_row: dict[str, Any], *asset_rows: dict[str, Any]) -> int:
        pitch_values = [abs(int(user_row["pose"]["pitch_1deg"]))]
        pitch_values.extend(abs(int(asset_row["pitch_1deg"])) for asset_row in asset_rows if asset_row is not None)
        return max(pitch_values)

    @staticmethod
    def _yaw_band_key(yaw_value: int) -> tuple[int, int] | None:
        abs_yaw = abs(int(yaw_value))
        if abs_yaw < 18:
            return None
        band_index = min(4, max(0, (abs_yaw - 18) // 6))
        return (1 if int(yaw_value) >= 0 else -1, band_index)

    @staticmethod
    def _yaw_band_limits(band_key: tuple[int, int]) -> tuple[int, int, int]:
        sign, band_index = band_key
        lower = 18 + band_index * 6
        upper = min(45, lower + 5)
        return sign, lower, upper

    @staticmethod
    def _pitch_band_key(pitch_value: int) -> tuple[int, int] | None:
        pitch_value = int(pitch_value)
        if pitch_value >= 14:
            return (1, min(3, max(0, (pitch_value - 14) // 5)))
        if pitch_value <= -8:
            return (-1, min(1, max(0, (abs(pitch_value) - 8) // 4)))
        return None

    @staticmethod
    def _pitch_band_limits(band_key: tuple[int, int]) -> tuple[int, int]:
        sign, band_index = band_key
        if sign > 0:
            lower = 14 + band_index * 5
            upper = 30 if band_index >= 3 else lower + 4
            return lower, upper
        lower_abs = 8 + band_index * 4
        upper_abs = min(15, lower_abs + 3)
        return -upper_abs, -lower_abs

    def _prefer_side_band_candidate(
        self,
        user_row: dict[str, Any],
        ranked_assets: list[tuple[dict[str, Any], float]],
        current_asset: dict[str, Any],
        best_asset: dict[str, Any],
        best_score: float,
        moderate_motion: bool,
        fast_motion: bool,
    ) -> tuple[dict[str, Any], float, bool]:
        if fast_motion:
            return best_asset, best_score, False

        current_band = self._yaw_band_key(int(current_asset["yaw_1deg"]))
        if current_band is None:
            return best_asset, best_score, False

        user_yaw = int(user_row["pose"]["yaw_1deg"])
        current_yaw_gap = abs(user_yaw - int(current_asset["yaw_1deg"]))
        if moderate_motion and current_yaw_gap >= 2:
            return best_asset, best_score, False
        user_sign = 1 if user_yaw > 0 else -1 if user_yaw < 0 else 0
        band_sign, lower, upper = self._yaw_band_limits(current_band)
        release_margin = 1
        if user_sign != band_sign or not (lower - release_margin <= abs(user_yaw) <= upper + release_margin):
            return best_asset, best_score, False

        band_candidates = [
            (asset_row, score)
            for asset_row, score in ranked_assets
            if self._yaw_band_key(int(asset_row["yaw_1deg"])) == current_band
        ]
        if not band_candidates:
            return best_asset, best_score, False

        band_asset, band_score = band_candidates[0]
        global_best_band = self._yaw_band_key(int(best_asset["yaw_1deg"]))
        allowed_gap = 1.2 if moderate_motion else 2.0
        if global_best_band == current_band or band_score <= best_score + allowed_gap:
            return band_asset, band_score, band_asset["asset_id"] != best_asset["asset_id"]
        return best_asset, best_score, False

    def _prefer_pitch_band_candidate(
        self,
        user_row: dict[str, Any],
        current_asset: dict[str, Any],
        current_score: float,
        best_asset: dict[str, Any],
        best_score: float,
        moderate_motion: bool,
        fast_motion: bool,
    ) -> tuple[dict[str, Any], float, bool]:
        if fast_motion:
            return best_asset, best_score, False

        current_band = self._pitch_band_key(int(current_asset["pitch_1deg"]))
        if current_band is None:
            return best_asset, best_score, False

        user_pitch = int(user_row["pose"]["pitch_1deg"])
        user_yaw = int(user_row["pose"]["yaw_1deg"])
        lower, upper = self._pitch_band_limits(current_band)
        release_margin = 1 if moderate_motion else 2
        if not (lower - release_margin <= user_pitch <= upper + release_margin):
            return best_asset, best_score, False

        best_band = self._pitch_band_key(int(best_asset["pitch_1deg"]))
        current_yaw_gap = abs(user_yaw - int(current_asset["yaw_1deg"]))
        allowed_gap = 1.8 if moderate_motion else 3.8
        if current_yaw_gap >= 2:
            allowed_gap = 1.2 if moderate_motion else 2.4
        if abs(user_pitch - int(best_asset["pitch_1deg"])) <= 2 and best_band == current_band:
            allowed_gap += 0.6
        if current_yaw_gap >= 3 and best_band != current_band:
            return best_asset, best_score, False
        if best_band == current_band or current_score <= best_score + allowed_gap:
            return current_asset, current_score, current_asset["asset_id"] != best_asset["asset_id"]
        return best_asset, best_score, False

    def _prefer_render_safe_candidate(
        self,
        user_row: dict[str, Any],
        ranked_assets: list[tuple[dict[str, Any], float]],
        best_asset: dict[str, Any],
        best_score: float,
        moderate_motion: bool,
        fast_motion: bool,
    ) -> tuple[dict[str, Any], float, bool]:
        best_risk = self._asset_crop_risk(best_asset)
        best_bucket = self._crop_risk_bucket(best_risk)
        if best_bucket <= 0:
            return best_asset, best_score, False

        allowed_gap = 1.4 if fast_motion else 2.4 if moderate_motion else 3.8
        if best_bucket >= 2:
            allowed_gap += 1.0

        safer_candidates: list[tuple[int, float, float, float, dict[str, Any]]] = []
        for asset_row, score in ranked_assets[:5]:
            risk_score = self._asset_crop_risk(asset_row)
            risk_bucket = self._crop_risk_bucket(risk_score)
            if risk_bucket >= best_bucket:
                continue
            if float(score) > best_score + allowed_gap:
                continue
            if risk_bucket > 0 and risk_score > best_risk - 0.08:
                continue
            safer_candidates.append(
                (
                    risk_bucket,
                    risk_score,
                    float(score),
                    pose_distance(user_row["pose"], asset_row),
                    asset_row,
                )
            )

        if not safer_candidates:
            return best_asset, best_score, False

        safer_candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3], item[4]["asset_id"]))
        chosen_candidate = safer_candidates[0]
        return chosen_candidate[4], chosen_candidate[2], chosen_candidate[4]["asset_id"] != best_asset["asset_id"]

    def _prefer_frontal_safe_candidate(
        self,
        user_row: dict[str, Any],
        ranked_assets: list[tuple[dict[str, Any], float]],
        best_asset: dict[str, Any],
        best_score: float,
        moderate_motion: bool,
        fast_motion: bool,
    ) -> tuple[dict[str, Any], float, bool]:
        if fast_motion:
            return best_asset, best_score, False

        user_yaw = int(user_row["pose"]["yaw_1deg"])
        user_abs_yaw = abs(user_yaw)
        if user_abs_yaw > 12:
            return best_asset, best_score, False

        best_abs_yaw = abs(int(best_asset["yaw_1deg"]))
        best_yaw_gap = abs(user_yaw - int(best_asset["yaw_1deg"]))
        if best_abs_yaw <= 10 and best_yaw_gap <= 5:
            return best_asset, best_score, False

        allowed_gap = 1.8 if moderate_motion else 3.2
        max_asset_abs_yaw = min(10, user_abs_yaw + 4)
        safer_candidates: list[tuple[int, int, float, float, dict[str, Any]]] = []
        for asset_row, score in ranked_assets[:8]:
            asset_yaw = int(asset_row["yaw_1deg"])
            asset_abs_yaw = abs(asset_yaw)
            yaw_gap = abs(user_yaw - asset_yaw)
            if asset_abs_yaw > max_asset_abs_yaw or yaw_gap > 6:
                continue
            if float(score) > best_score + allowed_gap:
                continue
            safer_candidates.append(
                (
                    asset_abs_yaw,
                    yaw_gap,
                    float(score),
                    pose_distance(user_row["pose"], asset_row),
                    asset_row,
                )
            )

        if not safer_candidates:
            return best_asset, best_score, False

        safer_candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3], item[4]["asset_id"]))
        chosen_candidate = safer_candidates[0]
        chosen_asset = chosen_candidate[4]
        return chosen_asset, chosen_candidate[2], chosen_asset["asset_id"] != best_asset["asset_id"]

    def _select_asset(
        self,
        user_row: dict[str, Any],
    ) -> tuple[dict[str, Any], float, str, list[tuple[dict[str, Any], float]]]:
        ranked_assets = select_best_assets(user_row, self.assets, limit=10)
        if not ranked_assets:
            raise RuntimeError("No candidate assets available")

        best_asset, best_score = ranked_assets[0]
        current_asset = self._selected_asset
        current_score: float | None = None

        def finalize(
            chosen_asset: dict[str, Any],
            chosen_score: float,
            chosen_mode: str,
            chosen_blend_assets: list[tuple[dict[str, Any], float]],
        ) -> tuple[dict[str, Any], float, str, list[tuple[dict[str, Any], float]]]:
            self._last_selection_trace = self._build_selection_trace(
                user_row=user_row,
                ranked_assets=ranked_assets,
                selected_asset=chosen_asset,
                selected_score=chosen_score,
                selection_mode=chosen_mode,
                current_asset=current_asset,
                current_score=current_score,
                blend_assets=chosen_blend_assets,
            )
            return chosen_asset, chosen_score, chosen_mode, chosen_blend_assets

        if current_asset is None:
            best_asset, best_score, frontal_safe_selected = self._prefer_frontal_safe_candidate(
                user_row,
                ranked_assets,
                best_asset,
                best_score,
                False,
                False,
            )
            best_asset, best_score, safe_candidate_selected = self._prefer_render_safe_candidate(
                user_row,
                ranked_assets,
                best_asset,
                best_score,
                False,
                False,
            )
            self._selected_asset = best_asset
            self._blend_assets = self._build_blend_assets(user_row, ranked_assets, best_asset, "initial")
            self._frames_since_switch = 1
            if frontal_safe_selected:
                return finalize(best_asset, best_score, "initial_frontal_safe", self._blend_assets)
            if safe_candidate_selected:
                return finalize(best_asset, best_score, "initial_safe_asset", self._blend_assets)
            return finalize(best_asset, best_score, "initial", self._blend_assets)

        current_score = asset_rank_score(user_row, current_asset)
        current_pose_gap = pose_distance(user_row["pose"], current_asset)
        motion = user_row.get("_motion", {})
        fast_motion = bool(motion.get("fast"))
        moderate_motion = bool(motion.get("moderate"))
        best_asset, best_score, band_locked = self._prefer_side_band_candidate(
            user_row,
            ranked_assets,
            current_asset,
            best_asset,
            best_score,
            moderate_motion,
            fast_motion,
        )
        band_lock_label = "side_band" if band_locked else None
        best_asset, best_score, pitch_band_locked = self._prefer_pitch_band_candidate(
            user_row,
            current_asset,
            current_score,
            best_asset,
            best_score,
            moderate_motion,
            fast_motion,
        )
        if pitch_band_locked and band_lock_label is None:
            band_lock_label = "pitch_band"
        best_asset, best_score, frontal_safe_selected = self._prefer_frontal_safe_candidate(
            user_row,
            ranked_assets,
            best_asset,
            best_score,
            moderate_motion,
            fast_motion,
        )
        if frontal_safe_selected and band_lock_label is None:
            band_lock_label = "frontal_safe"
        best_asset, best_score, safe_candidate_selected = self._prefer_render_safe_candidate(
            user_row,
            ranked_assets,
            best_asset,
            best_score,
            moderate_motion,
            fast_motion,
        )
        if safe_candidate_selected:
            band_lock_label = "safe_asset"
        best_pose_gap = pose_distance(user_row["pose"], best_asset)
        same_asset = current_asset["asset_id"] == best_asset["asset_id"]
        side_view_yaw = self._side_view_yaw(user_row, current_asset, best_asset)
        side_view = side_view_yaw >= 18
        vertical_view_pitch = self._vertical_view_pitch(user_row, current_asset, best_asset)
        vertical_view = vertical_view_pitch >= 12
        current_yaw_gap = abs(user_row["pose"]["yaw_1deg"] - int(current_asset["yaw_1deg"]))
        current_pitch_gap = abs(user_row["pose"]["pitch_1deg"] - int(current_asset["pitch_1deg"]))
        current_roll_gap = abs(user_row["pose"]["roll_1deg"] - int(current_asset["roll_1deg"]))
        pitch_dominant = current_pitch_gap >= current_yaw_gap + 1 and current_pitch_gap >= 2
        neighbor_pose = (
            abs(int(current_asset["yaw_1deg"]) - int(best_asset["yaw_1deg"])) <= (2 if side_view else 1)
            and abs(int(current_asset["pitch_1deg"]) - int(best_asset["pitch_1deg"])) <= (3 if vertical_view else (2 if side_view else 1))
            and abs(int(current_asset["roll_1deg"]) - int(best_asset["roll_1deg"])) <= (2 if side_view else 1)
        )
        current_within_deadband = (
            current_yaw_gap <= (1 if side_view else (1 if moderate_motion else 2))
            and current_pitch_gap <= (
                3 if vertical_view and not moderate_motion else
                2 if vertical_view else
                2 if side_view else
                (1 if moderate_motion else 2)
            )
            and current_roll_gap <= (2 if side_view else 1)
        )
        significant_improvement = (current_score - best_score) >= (
            4.6 if vertical_view and pitch_dominant and not moderate_motion else
            4.0 if side_view and not moderate_motion else
            3.0 if side_view else
            2.2 if moderate_motion else
            3.2
        )
        if fast_motion:
            hold_margin = 1.0
        elif moderate_motion:
            hold_margin = 2.8 if side_view else 2.6 if vertical_view else 2.1
        else:
            hold_margin = (
                4.6 if vertical_view and current_asset["pose_key"] == best_asset["pose_key"] else
                4.0 if vertical_view else
                3.8 if side_view and current_asset["pose_key"] == best_asset["pose_key"] else
                2.9 if side_view else
                3.8 if current_asset["pose_key"] == best_asset["pose_key"] else
                3.0
            )
        if current_yaw_gap >= 2 and current_pitch_gap >= 1:
            hold_margin -= 0.8 if moderate_motion else 1.0
        if current_yaw_gap >= 3 and current_pitch_gap >= 2:
            hold_margin -= 0.4
        hold_margin = max(1.0, hold_margin)
        force_switch = current_pose_gap > 16.0 and best_pose_gap + 3.0 < current_pose_gap
        if side_view and current_yaw_gap >= 3 and best_pose_gap + 1.5 < current_pose_gap:
            force_switch = True
        if safe_candidate_selected and not same_asset:
            force_switch = True
        in_cooldown = self._frames_since_switch < 1

        if same_asset:
            self._blend_assets = self._build_blend_assets(user_row, ranked_assets, current_asset, "stable")
            self._frames_since_switch += 1
            if band_lock_label == "side_band":
                return finalize(current_asset, current_score, "stable_side_band", self._blend_assets)
            if band_lock_label == "pitch_band":
                return finalize(current_asset, current_score, "stable_pitch_band", self._blend_assets)
            if band_lock_label == "safe_asset":
                return finalize(current_asset, current_score, "stable_safe_asset", self._blend_assets)
            return finalize(current_asset, current_score, "stable", self._blend_assets)

        if not safe_candidate_selected and not fast_motion and current_within_deadband and neighbor_pose and not significant_improvement:
            self._blend_assets = self._build_blend_assets(user_row, ranked_assets, current_asset, "hold")
            self._frames_since_switch += 1
            if band_lock_label == "side_band":
                return finalize(current_asset, current_score, "hold_side_band", self._blend_assets)
            if band_lock_label == "pitch_band":
                return finalize(current_asset, current_score, "hold_pitch_band", self._blend_assets)
            if band_lock_label == "safe_asset":
                return finalize(current_asset, current_score, "hold_safe_asset", self._blend_assets)
            return finalize(current_asset, current_score, "hold_deadband", self._blend_assets)

        if in_cooldown or (not force_switch and current_score <= best_score + hold_margin):
            self._blend_assets = self._build_blend_assets(user_row, ranked_assets, current_asset, "hold")
            self._frames_since_switch += 1
            if band_lock_label == "side_band":
                return finalize(current_asset, current_score, "hold_side_band", self._blend_assets)
            if band_lock_label == "pitch_band":
                return finalize(current_asset, current_score, "hold_pitch_band", self._blend_assets)
            if band_lock_label == "safe_asset":
                return finalize(current_asset, current_score, "hold_safe_asset", self._blend_assets)
            return finalize(current_asset, current_score, "hold", self._blend_assets)

        previous_blend_assets = self._blend_assets or [(current_asset, 1.0)]
        if fast_motion:
            self._transition = None
        else:
            self._transition = {
                "from_blend_assets": previous_blend_assets,
                "from_asset_id": current_asset["asset_id"],
                "step": 0,
                "steps": (
                    3
                    if (vertical_view and pitch_dominant and not side_view) or (current_yaw_gap >= 2 and current_pitch_gap >= 1)
                    else 2
                    if side_view or vertical_view
                    else 1
                ),
            }
        self._selected_asset = best_asset
        self._blend_assets = self._build_blend_assets(user_row, ranked_assets, best_asset, "switch")
        self._frames_since_switch = 1
        if band_lock_label == "safe_asset":
            return finalize(best_asset, best_score, "switch_safe_asset", self._blend_assets)
        return finalize(best_asset, best_score, "switch", self._blend_assets)

    def _compose_output_frame(
        self,
        user_row: dict[str, Any],
        frame_bgr: np.ndarray,
        blend_assets: list[tuple[dict[str, Any], float]],
        renderer_name: str,
        user_mask_bundle: dict[str, Any] | None,
    ) -> tuple[np.ndarray, float, str | None]:
        target_frame = compose_overlay_blend_frame(
            user_row,
            frame_bgr,
            blend_assets,
            self.asset_root,
            renderer_name=renderer_name,
            user_mask_bundle=user_mask_bundle,
        )
        if self._transition is None:
            return target_frame, 1.0, None

        from_frame = compose_overlay_blend_frame(
            user_row,
            frame_bgr,
            self._transition["from_blend_assets"],
            self.asset_root,
            renderer_name=renderer_name,
            user_mask_bundle=user_mask_bundle,
        )
        self._transition["step"] += 1
        transition_progress = min(1.0, self._transition["step"] / float(self._transition["steps"]))
        blended_frame = cv2.addWeighted(from_frame, 1.0 - transition_progress, target_frame, transition_progress, 0.0)
        from_asset_id = str(self._transition["from_asset_id"])
        if transition_progress >= 1.0:
            self._transition = None
        return blended_frame, transition_progress, from_asset_id

    def process_frame(
        self,
        frame_bgr: np.ndarray,
        renderer_name: str | None = None,
        render_frame_bgr: np.ndarray | None = None,
        tracked_user_row: dict[str, Any] | None = None,
        prefer_latency: bool = False,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        started_at = time.perf_counter()
        with self._lock:
            session = self._get_or_create_session(session_id)
            previous_session = self._current_session
            self._current_session = session
            try:
                resolved_renderer = self._set_active_renderer(renderer_name)
                feature_started_at = time.perf_counter()
                compose_frame_bgr = (
                    render_frame_bgr
                    if isinstance(render_frame_bgr, np.ndarray)
                    and render_frame_bgr.shape == frame_bgr.shape
                    else frame_bgr
                )
                if tracked_user_row is not None:
                    raw_user_row = dict(tracked_user_row)
                    feature_latency_ms = 0.0
                else:
                    reference_face_bbox = None if self._smoothed_user_row is None else self._smoothed_user_row.get("face_bbox")
                    raw_user_row = extract_feature_from_frame_bgr(
                        frame_bgr,
                        self._landmarker,
                        file_name="runtime_frame.jpg",
                        reference_face_bbox=reference_face_bbox,
                    )
                    feature_latency_ms = round((time.perf_counter() - feature_started_at) * 1000.0, 3)

                user_row = raw_user_row
                selected_asset_id = None
                selected_pose_key = None
                score = None
                runtime_status = "ok"
                selection_mode = "idle"
                transition_progress = 0.0
                transition_from_asset_id = None
                blend_assets: list[tuple[dict[str, Any], float]] = []
                output_frame = compose_frame_bgr.copy()
                user_mask_bundle: dict[str, Any] | None = None
                user_parsing_status = "disabled"
                user_parsing_latency_ms = 0.0
                selection_trace: dict[str, Any] | None = self._last_selection_trace

                overlay_started_at = time.perf_counter()
                if raw_user_row.get("ok"):
                    if self._is_face_tracking_outlier(raw_user_row):
                        self._missing_face_count = 0
                        self._invalid_face_count += 1
                        if self._invalid_face_count < 2 and self._smoothed_user_row is not None:
                            user_row, output_frame, selected_asset_id, selected_pose_key, blend_assets = self._hold_previous_tracking_frame(
                                compose_frame_bgr,
                                resolved_renderer,
                            )
                            runtime_status = "face_tracking_outlier_hold"
                            selection_mode = "hold_tracking"
                            transition_progress = 1.0 if blend_assets else 0.0
                            user_parsing_status = "hold_previous"
                            if self._last_selection_trace is not None:
                                selection_trace = dict(self._last_selection_trace)
                                selection_trace["decision"] = selection_mode
                        else:
                            self._invalid_face_count = 0
                            user_row = self._smooth_user_row(raw_user_row)
                            user_mask_bundle, user_parsing_status, user_parsing_latency_ms = self._parse_user_masks(
                                frame_bgr,
                                user_row,
                                resolved_renderer,
                                prefer_latency=prefer_latency,
                            )
                            user_row = self._attach_runtime_fit_context(user_row, user_mask_bundle)
                            best_asset, score, selection_mode, blend_assets = self._select_asset(user_row)
                            selected_asset_id = best_asset["asset_id"]
                            selected_pose_key = best_asset["pose_key"]
                            selection_trace = self._last_selection_trace
                            output_frame, transition_progress, transition_from_asset_id = self._compose_output_frame(
                                user_row,
                                compose_frame_bgr,
                                blend_assets,
                                resolved_renderer,
                                user_mask_bundle,
                            )
                    else:
                        self._missing_face_count = 0
                        self._invalid_face_count = 0
                        user_row = self._smooth_user_row(raw_user_row)
                        user_mask_bundle, user_parsing_status, user_parsing_latency_ms = self._parse_user_masks(
                            frame_bgr,
                            user_row,
                            resolved_renderer,
                            prefer_latency=prefer_latency,
                        )
                        user_row = self._attach_runtime_fit_context(user_row, user_mask_bundle)
                        best_asset, score, selection_mode, blend_assets = self._select_asset(user_row)
                        selected_asset_id = best_asset["asset_id"]
                        selected_pose_key = best_asset["pose_key"]
                        selection_trace = self._last_selection_trace
                        output_frame, transition_progress, transition_from_asset_id = self._compose_output_frame(
                            user_row,
                            compose_frame_bgr,
                            blend_assets,
                            resolved_renderer,
                            user_mask_bundle,
                        )
                else:
                    runtime_status = str(raw_user_row.get("reason", "no_face_or_pose"))
                    selection_mode = "no_face"
                    self._missing_face_count += 1
                    self._invalid_face_count = 0
                    if self._missing_face_count >= 3:
                        self._reset_session_state(session)
                overlay_latency_ms = round((time.perf_counter() - overlay_started_at) * 1000.0, 3)
                session.last_seen_monotonic = time.monotonic()
                active_session_count = len(self._sessions)
            finally:
                self._current_session = previous_session

        encoded_ok, encoded = cv2.imencode(".jpg", output_frame, jpeg_params(self.jpeg_quality))
        if not encoded_ok:
            raise RuntimeError("Failed to encode overlay image")

        total_latency_ms = round((time.perf_counter() - started_at) * 1000.0, 3)
        return {
            "image_bytes": encoded.tobytes(),
            "output_frame_bgr": output_frame,
            "user_row": user_row,
            "raw_user_row": raw_user_row,
            "selected_asset_id": selected_asset_id,
            "selected_pose_key": selected_pose_key,
            "score": score,
            "status": runtime_status,
            "selection_mode": selection_mode,
            "blend_asset_ids": [str(asset_row["asset_id"]) for asset_row, _ in blend_assets],
            "blend_weights": [round(float(weight), 4) for _, weight in blend_assets],
            "transition_progress": round(transition_progress, 3),
            "transition_from_asset_id": transition_from_asset_id,
            "renderer_name": resolved_renderer,
            "latency_ms": total_latency_ms,
            "feature_latency_ms": feature_latency_ms,
            "overlay_latency_ms": overlay_latency_ms,
            "user_parsing_status": user_parsing_status,
            "user_parsing_latency_ms": user_parsing_latency_ms,
            "session_id": session.session_id,
            "active_session_count": active_session_count,
            "selection_trace": selection_trace,
        }

    def close(self) -> None:
        with self._lock:
            self._sessions.clear()
            self._landmarker.close()
