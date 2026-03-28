from __future__ import annotations

import logging
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
from PIL import Image

from app.angle_priority_selection import (
    is_angle_priority_pose_compatible,
    rank_assets_by_angle_priority,
    shortlist_assets_by_angle_priority,
    should_release_current_asset,
)
from app.models import FeatureMessageModel
from app.overlay_postprocess_pipeline import apply_overlay_postprocess
from app.render import build_render_task
from app.server_render import compose_bundle_frame
from cv2_cuda_utils import opencv_add_weighted, opencv_cvt_color


TOOLS_DIR = Path(__file__).resolve().parents[1] / "hairddae_tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from face_feature_utils import build_landmarker, extract_feature_from_frame_bgr
from local_demo_paths import default_face_landmarker_model_path, generated_root, read_json, resolve_asset_path
from realtime_face_parsing import RuntimeFaceParsing
from run_hair_overlay_poc import (
    AVAILABLE_RENDERERS,
    DEFAULT_RENDERER,
    asset_rank_score,
    compose_overlay_blend_frame,
    compose_overlay_transition_frames,
    derive_geom_from_feature,
    normalize_renderer_name,
    pose_distance,
    resolve_hair_tone_gain,
    select_best_assets,
)


logger = logging.getLogger(__name__)


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
    broken_asset_ids: set[str] = field(default_factory=set)
    last_render_error: str | None = None


@dataclass(frozen=True)
class RuntimeBundleRenderEntry:
    asset_id: str
    metadata: dict[str, Any]
    anchors_payload: dict[str, Any]
    hair_rgba_path: Path | None
    hair_bbox: dict[str, Any] | None
    hair_luma: float | None = None
    face_mask_path: Path | None = None
    protect_face_mask_path: Path | None = None


@dataclass(frozen=True)
class RuntimeBundleRenderPayload:
    hair_rgba_path: Path | None
    render_task: dict[str, Any] | None
    hair_bbox: dict[str, Any] | None
    face_mask_path: Path | None = None
    protect_face_mask_path: Path | None = None


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
        self.disable_user_parsing_in_latency_mode = (
            str(os.environ.get("LOCAL_DEMO_DISABLE_USER_PARSING_IN_LATENCY_MODE", "")).strip().lower()
            in {"1", "true", "yes", "on"}
        )
        self.selection_candidate_limit = max(
            24,
            int(os.environ.get("INFERENCE_RTC_SELECTION_CANDIDATE_LIMIT", "96")),
        )
        self.render_cost_blend_disable_ratio = float(
            os.environ.get("INFERENCE_RTC_BLEND_DISABLE_RENDER_COST_RATIO", "0.118")
        )
        self.render_cost_renderer_downgrade_ratio = float(
            os.environ.get("INFERENCE_RTC_RENDERER_DOWNGRADE_RENDER_COST_RATIO", "0.108")
        )
        self.render_cost_preference_score_gap = float(
            os.environ.get("INFERENCE_RTC_RENDER_COST_PREFERENCE_SCORE_GAP", "2.4")
        )
        self.switch_cooldown_frames = max(
            1,
            int(os.environ.get("INFERENCE_RTC_SWITCH_COOLDOWN_FRAMES", "3")),
        )
        self.switch_hold_margin_bias = float(
            os.environ.get("INFERENCE_RTC_SWITCH_HOLD_MARGIN_BIAS", "0.8")
        )
        self.switch_significant_improvement_bias = float(
            os.environ.get("INFERENCE_RTC_SWITCH_SIGNIFICANT_IMPROVEMENT_BIAS", "0.8")
        )
        self.angle_priority_enabled = str(
            os.environ.get("INFERENCE_RTC_ANGLE_PRIORITY_ENABLED", "0")
        ).strip().lower() in {"1", "true", "yes", "on"}
        self.pose_smoothing_enabled = str(
            os.environ.get("INFERENCE_RTC_POSE_SMOOTHING_ENABLED", "1")
        ).strip().lower() in {"1", "true", "yes", "on"}
        self.bundle_render_enabled = str(
            os.environ.get("INFERENCE_RTC_BUNDLE_RENDER_ENABLED", "1")
        ).strip().lower() in {"1", "true", "yes", "on"}
        self.bundle_render_latency_only = str(
            os.environ.get("INFERENCE_RTC_BUNDLE_RENDER_LATENCY_ONLY", "1")
        ).strip().lower() in {"1", "true", "yes", "on"}
        self.bundle_render_render_cost_ratio = float(
            os.environ.get("INFERENCE_RTC_BUNDLE_RENDER_COST_RATIO", "0.098")
        )
        self.bundle_render_allow_transition = str(
            os.environ.get("INFERENCE_RTC_BUNDLE_RENDER_ALLOW_TRANSITION", "1")
        ).strip().lower() in {"1", "true", "yes", "on"}
        self.lightweight_overlay_only = str(
            os.environ.get("INFERENCE_RTC_LIGHTWEIGHT_OVERLAY_ONLY", "0")
        ).strip().lower() in {"1", "true", "yes", "on"}
        self.lightweight_renderer_name = normalize_renderer_name(
            os.environ.get("INFERENCE_RTC_LIGHTWEIGHT_RENDERER_NAME", DEFAULT_RENDERER)
        )
        self._lock = threading.Lock()
        self._landmarker = None
        self._user_parser: RuntimeFaceParsing | None = None
        self._current_session: RuntimeSessionState | None = None
        self._sessions: dict[str, RuntimeSessionState] = {}
        self._integrity_rejected_asset_ids: set[str] = set()
        self._asset_pose_index: dict[tuple[int, int, int], list[dict[str, Any]]] = {}
        self._bundle_render_entry_cache: dict[str, RuntimeBundleRenderEntry] = {}
        self._bundle_render_entry_cache_limit = max(
            8,
            int(os.environ.get("INFERENCE_RTC_BUNDLE_RENDER_ENTRY_CACHE_LIMIT", "64")),
        )
        self.user_parsing_ready = False
        self.user_parsing_error: str | None = None
        self.available_renderers = [name for name in AVAILABLE_RENDERERS if name != "mesh_v4"]
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

    def _ensure_landmarker(self) -> Any:
        if self._landmarker is None:
            self._landmarker = build_landmarker(self.model_path, num_faces=3)
        return self._landmarker

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
        session.last_render_error = None

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

    @property
    def _broken_asset_ids(self) -> set[str]:
        return self._require_session().broken_asset_ids

    @property
    def _last_render_error(self) -> str | None:
        return self._require_session().last_render_error

    @_last_render_error.setter
    def _last_render_error(self, value: str | None) -> None:
        self._require_session().last_render_error = value

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

        boundary_touches = asset_row.get("boundary_touches") or {}
        naturalness_tags = set(asset_row.get("naturalness_failure_tags_v1") or [])
        risk_score = 0.0
        if bool(boundary_touches.get("top")):
            risk_score += 0.18
        if bool(boundary_touches.get("bottom")):
            risk_score += 0.08
        if bool(boundary_touches.get("left")):
            risk_score += 0.11
        if bool(boundary_touches.get("right")):
            risk_score += 0.11

        render_cost_ratio = self._asset_render_cost_ratio(asset_row)
        risk_score += max(0.0, render_cost_ratio - 0.10) * 1.75
        risk_score += min(0.20, float(asset_row.get("face_overlap_ratio") or 0.0) * 10.0)
        risk_score += min(0.18, float(asset_row.get("naturalness_risk_v1") or 0.0) * 1.8)
        risk_score += min(0.12, max(0, int(asset_row.get("mask_component_count") or 1) - 1) * 0.03)
        risk_score += min(0.08, float(asset_row.get("hole_ratio") or 0.0) * 4.0)

        fringe_fill_ratio = float(asset_row.get("fringe_fill_ratio") or 0.0)
        if 0.0 < fringe_fill_ratio < 0.62:
            risk_score += min(0.06, (0.62 - fringe_fill_ratio) * 0.35)

        if "face_skin_overlap_risk" in naturalness_tags:
            risk_score += 0.08
        if "downward_face_cover_risk" in naturalness_tags:
            risk_score += 0.10
        if "ear_skin_overlap_risk" in naturalness_tags:
            risk_score += 0.05

        asset_row["_crop_edge_risk"] = round(min(1.0, risk_score), 6)
        return float(asset_row["_crop_edge_risk"])

    def _asset_render_cost_ratio(self, asset_row: dict[str, Any]) -> float:
        cached_ratio = asset_row.get("_render_cost_ratio")
        if cached_ratio is not None:
            return float(cached_ratio)

        image_size = asset_row.get("image_size") or {}
        image_width = float(image_size.get("width") or 0.0)
        image_height = float(image_size.get("height") or 0.0)
        image_area = image_width * image_height

        bbox = asset_row.get("hair_rgba_bbox") or asset_row.get("mask_roi") or {}
        bbox_width = float(bbox.get("w") or 0.0)
        bbox_height = float(bbox.get("h") or 0.0)
        bbox_ratio = 0.0
        if image_area > 0.0 and bbox_width > 0.0 and bbox_height > 0.0:
            bbox_ratio = (bbox_width * bbox_height) / image_area

        alpha_ratio = float(asset_row.get("alpha_area_ratio") or 0.0)
        hair_ratio = float(asset_row.get("hair_area_ratio") or 0.0)
        render_cost_ratio = max(bbox_ratio, alpha_ratio * 1.18, hair_ratio * 1.28)
        asset_row["_render_cost_ratio"] = round(min(1.0, render_cost_ratio), 6)
        return float(asset_row["_render_cost_ratio"])

    @staticmethod
    def _render_cost_bucket(render_cost_ratio: float) -> int:
        if render_cost_ratio <= 0.095:
            return 0
        if render_cost_ratio <= 0.115:
            return 1
        if render_cost_ratio <= 0.135:
            return 2
        return 3

    def _choose_pose_representative(self, pose_rows: list[dict[str, Any]]) -> dict[str, Any]:
        ranked_rows = sorted(pose_rows, key=self._asset_preference_key)
        ranked_rows = [
            row
            for row in ranked_rows
            if self._asset_bundle_integrity_error(row) is None
        ]
        if not ranked_rows:
            return pose_rows[0]
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

    def _asset_trace_summary(self, asset_row: dict[str, Any] | None, score: float | None = None) -> dict[str, Any] | None:
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
            "render_cost_ratio": round(self._asset_render_cost_ratio(asset_row), 6),
            "crop_risk": round(self._asset_crop_risk(asset_row), 6),
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
        candidate_metrics: dict[str, Any] | None = None,
        selection_latency_ms: float | None = None,
    ) -> dict[str, Any]:
        top_candidates: list[dict[str, Any]] = []
        for rank, (asset_row, score) in enumerate(ranked_assets[:5], start=1):
            candidate_summary = self._asset_trace_summary(asset_row, score)
            if candidate_summary is None:
                continue
            candidate_summary["rank"] = rank
            candidate_summary["pose_distance"] = round(pose_distance(user_row["pose"], asset_row), 6)
            top_candidates.append(candidate_summary)

        trace = {
            "decision": selection_mode,
            "selected": self._asset_trace_summary(selected_asset, selected_score),
            "current": self._asset_trace_summary(current_asset, current_score),
            "top_candidates": top_candidates,
            "blend_asset_ids": [str(asset_row["asset_id"]) for asset_row, _ in (blend_assets or [])],
        }
        if candidate_metrics:
            trace["candidate_metrics"] = candidate_metrics
        if selection_latency_ms is not None:
            trace["selection_latency_ms"] = round(float(selection_latency_ms), 3)
        return trace

    def _merge_selection_trace_fields(self, **fields: Any) -> dict[str, Any] | None:
        if self._current_session is None or self._last_selection_trace is None:
            return None

        trace = dict(self._last_selection_trace)
        for key, value in fields.items():
            if isinstance(trace.get(key), dict) and isinstance(value, dict):
                merged_value = dict(trace[key])
                merged_value.update(value)
                trace[key] = merged_value
            else:
                trace[key] = value
        self._last_selection_trace = trace
        return trace

    def _asset_bundle_integrity_error(self, asset_row: dict[str, Any]) -> str | None:
        cached = asset_row.get("_bundle_integrity_error")
        if isinstance(cached, str):
            return cached or None

        asset_id = str(asset_row.get("asset_id") or "").strip()
        metadata_path_raw = str(asset_row.get("metadata_path") or "").strip()
        error: str | None = None
        metadata: dict[str, Any] | None = None

        if not metadata_path_raw:
            error = "missing metadata_path"
        else:
            metadata_path = resolve_asset_path(self.asset_root, metadata_path_raw)
            if not metadata_path.is_file():
                error = f"missing metadata file: {metadata_path}"
            else:
                try:
                    loaded_metadata = read_json(metadata_path)
                except Exception as exc:
                    error = f"invalid metadata json: {metadata_path} ({exc})"
                else:
                    if not isinstance(loaded_metadata, dict):
                        error = f"invalid metadata payload: {metadata_path}"
                    else:
                        metadata = loaded_metadata

        if error is None and metadata is not None:
            hair_rgba_path_raw = str(metadata.get("hair_rgba_path") or "").strip()
            hair_rgba_path = resolve_asset_path(self.asset_root, hair_rgba_path_raw) if hair_rgba_path_raw else None
            hair_rgba_exists = bool(hair_rgba_path is not None and hair_rgba_path.is_file())

            def path_exists(raw_path: str) -> bool:
                resolved_path = resolve_asset_path(self.asset_root, raw_path)
                return resolved_path.is_file()

            required_asset_specs = (
                ("anchors_path", "json"),
                ("image_path", "image"),
                ("alpha_path", "alpha"),
                ("hair_mask_path", "grayscale"),
                ("face_mask_path", "grayscale"),
                ("forehead_mask_path", "grayscale"),
                ("ear_mask_left_path", "grayscale"),
                ("ear_mask_right_path", "grayscale"),
                ("neck_shoulder_mask_path", "grayscale"),
                ("protect_face_mask_path", "grayscale"),
            )
            for key, kind in required_asset_specs:
                raw_value = str(metadata.get(key) or "").strip()
                if kind == "json":
                    if not raw_value:
                        error = f"missing metadata field: {key}"
                        break
                    resolved_path = resolve_asset_path(self.asset_root, raw_value)
                    if not resolved_path.is_file():
                        error = f"missing asset file for {key}: {resolved_path}"
                        break
                    continue
                if kind == "image":
                    image_ok = bool(raw_value) and path_exists(raw_value)
                    hair_rgba_ok = hair_rgba_exists
                    if not image_ok and not hair_rgba_ok:
                        error = "missing image_path and hair_rgba_path fallback"
                        break
                    continue
                if kind == "alpha":
                    alpha_ok = bool(raw_value) and path_exists(raw_value)
                    hair_rgba_ok = hair_rgba_exists
                    if not alpha_ok and not hair_rgba_ok:
                        error = "missing alpha_path and hair_rgba_path fallback"
                        break
                    continue
                if not raw_value:
                    error = f"missing metadata field: {key}"
                    break
                resolved_path = resolve_asset_path(self.asset_root, raw_value)
                if not resolved_path.is_file():
                    error = f"missing asset file for {key}: {resolved_path}"
                    break

        asset_row["_bundle_integrity_error"] = "" if error is None else error
        if error is not None and asset_id:
            self._integrity_rejected_asset_ids.add(asset_id)
        return error

    def _candidate_assets(self) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        broken_asset_ids = self._broken_asset_ids
        for asset_row in self.assets:
            asset_id = str(asset_row.get("asset_id") or "").strip()
            if asset_id and asset_id in broken_asset_ids:
                continue
            if self._asset_bundle_integrity_error(asset_row) is not None:
                continue
            candidates.append(asset_row)
        return candidates

    @staticmethod
    def _pose_index_key(yaw_value: int, pitch_value: int, roll_value: int) -> tuple[int, int, int]:
        return (int(yaw_value), int(pitch_value), int(roll_value))

    def _build_asset_pose_index(
        self,
        asset_rows: list[dict[str, Any]],
    ) -> dict[tuple[int, int, int], list[dict[str, Any]]]:
        index: dict[tuple[int, int, int], list[dict[str, Any]]] = {}
        for asset_row in asset_rows:
            index.setdefault(
                self._pose_index_key(
                    int(asset_row.get("yaw_1deg") or 0),
                    int(asset_row.get("pitch_1deg") or 0),
                    int(asset_row.get("roll_1deg") or 0),
                ),
                [],
            ).append(asset_row)
        return index

    def _indexed_candidate_assets(
        self,
        user_row: dict[str, Any],
        *,
        yaw_tolerance: int,
        pitch_tolerance: int,
        roll_tolerance: int,
        limit: int = 384,
    ) -> list[dict[str, Any]]:
        user_pose = user_row.get("pose", {})
        user_yaw = int(user_pose.get("yaw_1deg") or 0)
        user_pitch = int(user_pose.get("pitch_1deg") or 0)
        user_roll = int(user_pose.get("roll_1deg") or 0)
        broken_asset_ids = self._broken_asset_ids
        ranked_candidates: list[tuple[int, int, int, str, dict[str, Any]]] = []
        seen_asset_ids: set[str] = set()

        for yaw_value in range(user_yaw - yaw_tolerance, user_yaw + yaw_tolerance + 1):
            for pitch_value in range(user_pitch - pitch_tolerance, user_pitch + pitch_tolerance + 1):
                for roll_value in range(user_roll - roll_tolerance, user_roll + roll_tolerance + 1):
                    for asset_row in self._asset_pose_index.get(
                        self._pose_index_key(yaw_value, pitch_value, roll_value),
                        (),
                    ):
                        asset_id = str(asset_row.get("asset_id") or "").strip()
                        if not asset_id or asset_id in seen_asset_ids or asset_id in broken_asset_ids:
                            continue
                        if self._asset_bundle_integrity_error(asset_row) is not None:
                            continue
                        seen_asset_ids.add(asset_id)
                        ranked_candidates.append(
                            (
                                abs(user_yaw - yaw_value) + abs(user_pitch - pitch_value) + abs(user_roll - roll_value),
                                abs(user_yaw - yaw_value),
                                abs(user_pitch - pitch_value) + abs(user_roll - roll_value),
                                asset_id,
                                asset_row,
                            )
                        )

        ranked_candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
        return [asset_row for _, _, _, _, asset_row in ranked_candidates[:limit]]

    def _candidate_assets_for_user_row(
        self,
        user_row: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if not self._asset_pose_index or not isinstance(user_row.get("pose"), dict):
            candidates = self._candidate_assets()
            return candidates, {
                "source": "full_scan",
                "candidate_pool_size": len(candidates),
                "runtime_asset_count": len(self.assets),
            }

        windows = [(tolerance, tolerance, tolerance) for tolerance in range(0, 11)]
        minimum_candidates = 8
        for yaw_tolerance, pitch_tolerance, roll_tolerance in windows:
            candidates = self._indexed_candidate_assets(
                user_row,
                yaw_tolerance=yaw_tolerance,
                pitch_tolerance=pitch_tolerance,
                roll_tolerance=roll_tolerance,
            )
            if len(candidates) >= minimum_candidates:
                return candidates, {
                    "source": "pose_index",
                    "candidate_pool_size": len(candidates),
                    "runtime_asset_count": len(self.assets),
                    "pose_window": {
                        "yaw_tolerance": yaw_tolerance,
                        "pitch_tolerance": pitch_tolerance,
                        "roll_tolerance": roll_tolerance,
                    },
                }

        candidates = self._candidate_assets()
        return candidates, {
            "source": "full_scan",
            "candidate_pool_size": len(candidates),
            "runtime_asset_count": len(self.assets),
            "pose_window": {
                "yaw_tolerance": windows[-1][0],
                "pitch_tolerance": windows[-1][1],
                "roll_tolerance": windows[-1][2],
            },
        }

    def _angle_priority_candidate_assets_for_user_row(
        self,
        user_row: dict[str, Any],
        *,
        limit: int,
        max_radius: int = 12,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if not self._asset_pose_index or not isinstance(user_row.get("pose"), dict):
            candidates = shortlist_assets_by_angle_priority(
                user_row,
                self._candidate_assets(),
                limit=limit,
            )
            return candidates, {
                "source": "angle_priority_full_scan",
                "candidate_pool_size": len(candidates),
                "runtime_asset_count": len(self.assets),
                "pose_radius": None,
            }

        user_pose = user_row.get("pose") or {}
        user_yaw = int(user_pose.get("yaw_1deg") or 0)
        user_pitch = int(user_pose.get("pitch_1deg") or 0)
        user_roll = int(user_pose.get("roll_1deg") or 0)
        broken_asset_ids = self._broken_asset_ids

        for radius in range(0, max_radius + 1):
            ring_candidates: list[dict[str, Any]] = []
            seen_asset_ids: set[str] = set()
            for yaw_value in range(user_yaw - radius, user_yaw + radius + 1):
                for pitch_value in range(user_pitch - radius, user_pitch + radius + 1):
                    for roll_value in range(user_roll - radius, user_roll + radius + 1):
                        if max(abs(user_yaw - yaw_value), abs(user_pitch - pitch_value), abs(user_roll - roll_value)) != radius:
                            continue
                        for asset_row in self._asset_pose_index.get(
                            self._pose_index_key(yaw_value, pitch_value, roll_value),
                            (),
                        ):
                            asset_id = str(asset_row.get("asset_id") or "").strip()
                            if not asset_id or asset_id in seen_asset_ids or asset_id in broken_asset_ids:
                                continue
                            if self._asset_bundle_integrity_error(asset_row) is not None:
                                continue
                            seen_asset_ids.add(asset_id)
                            ring_candidates.append(asset_row)
            if ring_candidates:
                candidates = shortlist_assets_by_angle_priority(
                    user_row,
                    ring_candidates,
                    limit=limit,
                )
                return candidates, {
                    "source": "angle_priority_pose_ring",
                    "candidate_pool_size": len(candidates),
                    "runtime_asset_count": len(self.assets),
                    "pose_radius": radius,
                }

        candidates = shortlist_assets_by_angle_priority(
            user_row,
            self._candidate_assets(),
            limit=limit,
        )
        return candidates, {
            "source": "angle_priority_full_scan_fallback",
            "candidate_pool_size": len(candidates),
            "runtime_asset_count": len(self.assets),
            "pose_radius": max_radius,
        }

    def _ranking_candidate_limit(
        self,
        user_row: dict[str, Any],
        candidate_pool_size: int,
    ) -> int:
        yaw_value = abs(int((user_row.get("pose") or {}).get("yaw_1deg") or 0))
        pitch_value = abs(int((user_row.get("pose") or {}).get("pitch_1deg") or 0))
        motion = user_row.get("_motion", {})
        if yaw_value >= 18 or pitch_value >= 12:
            limit = min(self.selection_candidate_limit, 96)
        elif yaw_value >= 10 or pitch_value >= 8:
            limit = min(self.selection_candidate_limit, 84)
        else:
            limit = min(self.selection_candidate_limit, 72)

        if motion.get("fast"):
            limit = min(limit, 56)
        elif motion.get("moderate"):
            limit = min(limit, 72)

        if candidate_pool_size >= 640:
            limit = min(limit, 48)
        elif candidate_pool_size >= 384:
            limit = min(limit, 56)
        elif candidate_pool_size >= 256:
            limit = min(limit, 64)

        return max(18, min(max(18, candidate_pool_size), limit))

    @staticmethod
    def _asset_ids_from_blend_assets(blend_assets: list[tuple[dict[str, Any], float]]) -> list[str]:
        return [
            str(asset_row.get("asset_id") or "").strip()
            for asset_row, _ in blend_assets
            if str(asset_row.get("asset_id") or "").strip()
        ]

    def _transition_asset_ids(self) -> list[str]:
        if self._transition is None:
            return []

        asset_ids: list[str] = []
        from_asset_id = str(self._transition.get("from_asset_id") or "").strip()
        if from_asset_id:
            asset_ids.append(from_asset_id)

        from_blend_assets = self._transition.get("from_blend_assets")
        if isinstance(from_blend_assets, list):
            asset_ids.extend(
                [
                    str(asset_row.get("asset_id") or "").strip()
                    for asset_row, _ in from_blend_assets
                    if isinstance(asset_row, dict) and str(asset_row.get("asset_id") or "").strip()
                ]
            )
        return asset_ids

    def _mark_render_failure(
        self,
        *,
        asset_ids: list[str],
        error: Exception,
        context: str,
    ) -> None:
        normalized_asset_ids = sorted({asset_id for asset_id in asset_ids if asset_id})
        if normalized_asset_ids:
            self._broken_asset_ids.update(normalized_asset_ids)

        self._last_render_error = str(error)
        if self._last_selection_trace is not None:
            trace = dict(self._last_selection_trace)
            trace["decision"] = context
            trace["render_error"] = str(error)
            trace["rejected_asset_ids"] = normalized_asset_ids
            self._last_selection_trace = trace

        session = self._require_session()
        logger.warning(
            "hair runtime render failure: session=%s context=%s asset_ids=%s error=%s",
            session.session_id,
            context,
            normalized_asset_ids,
            error,
        )
        self._selected_asset = None
        self._blend_assets = []
        self._transition = None
        self._frames_since_switch = 0

    def _select_and_compose_output_frame(
        self,
        *,
        user_row: dict[str, Any],
        compose_frame_bgr: np.ndarray,
        source_frame_bgr: np.ndarray | None = None,
        renderer_name: str,
        user_mask_bundle: dict[str, Any] | None,
        representative_asset_id: str | None,
        prefer_latency: bool,
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        fallback_used = False

        for attempt in range(2):
            selected_asset_id: str | None = None
            blend_assets: list[tuple[dict[str, Any], float]] = []
            try:
                best_asset, score, selection_mode, blend_assets = self._select_asset(
                    user_row,
                    representative_asset_id=representative_asset_id,
                )
                selected_asset_id = str(best_asset["asset_id"])
                selected_pose_key = str(best_asset["pose_key"])
                compose_started_at = time.perf_counter()
                output_frame, transition_progress, transition_from_asset_id, effective_renderer_name, coverage_mask = self._compose_output_frame(
                    user_row,
                    compose_frame_bgr,
                    blend_assets,
                    renderer_name,
                    user_mask_bundle,
                    prefer_latency=prefer_latency,
                    source_frame_bgr=source_frame_bgr,
                )
                compose_latency_ms = round((time.perf_counter() - compose_started_at) * 1000.0, 3)
                selection_trace = self._last_selection_trace
                if selection_trace is not None:
                    selection_trace = dict(selection_trace)
                    selection_trace["compose_latency_ms"] = compose_latency_ms
                    selection_trace["blend_asset_count"] = len(blend_assets)
                    selection_trace["effective_renderer_name"] = effective_renderer_name
                    if blend_assets:
                        selection_trace["primary_render_cost_ratio"] = round(
                            self._asset_render_cost_ratio(blend_assets[0][0]),
                            6,
                        )
                if fallback_used and selection_trace is not None:
                    selection_trace = dict(selection_trace)
                    selection_trace["render_fallback_used"] = True
                if selection_trace is not None:
                    self._last_selection_trace = selection_trace
                return {
                    "status": "ok",
                    "output_frame": output_frame,
                    "selected_asset_id": selected_asset_id,
                    "selected_pose_key": selected_pose_key,
                    "score": score,
                    "selection_mode": selection_mode,
                    "blend_assets": blend_assets,
                    "transition_progress": transition_progress,
                    "transition_from_asset_id": transition_from_asset_id,
                    "selection_trace": selection_trace,
                    "render_error": None,
                    "effective_renderer_name": effective_renderer_name,
                    "coverage_mask": coverage_mask,
                }
            except Exception as exc:
                last_error = exc
                failure_asset_ids = []
                if selected_asset_id is not None:
                    failure_asset_ids.append(selected_asset_id)
                failure_asset_ids.extend(self._asset_ids_from_blend_assets(blend_assets))
                failure_asset_ids.extend(self._transition_asset_ids())
                self._mark_render_failure(
                    asset_ids=failure_asset_ids,
                    error=exc,
                    context="render_retry" if attempt == 0 else "render_failed",
                )
                fallback_used = True
                if not failure_asset_ids:
                    break

        failed_trace: dict[str, Any] | None = None
        if self._last_selection_trace is not None:
            failed_trace = dict(self._last_selection_trace)
            failed_trace["render_fallback_failed"] = True
        elif last_error is not None:
            failed_trace = {
                "decision": "render_failed",
                "render_error": str(last_error),
            }
        return {
            "status": "overlay_error",
            "output_frame": compose_frame_bgr.copy(),
            "selected_asset_id": None,
            "selected_pose_key": None,
            "score": None,
            "selection_mode": "overlay_error",
            "blend_assets": [],
            "transition_progress": 0.0,
            "transition_from_asset_id": None,
            "selection_trace": failed_trace,
            "render_error": None if last_error is None else str(last_error),
            "effective_renderer_name": None,
            "coverage_mask": None,
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
        self._integrity_rejected_asset_ids = set()
        self.assets = self._pose_representatives(runtime_source)
        self._asset_pose_index = self._build_asset_pose_index(self.assets)
        if not self.assets:
            raise RuntimeError(f"No assets available in {asset_index_path}")
        self.asset_count = len(all_assets)
        self.approved_asset_count = len(approved_assets)
        self.approved_runtime_asset_count = len(approved_runtime_assets)
        self.approved_strict_asset_count = len(approved_strict_assets)
        self.blacklisted_asset_count = len(blacklisted_asset_ids)
        self.integrity_rejected_asset_count = len(self._integrity_rejected_asset_ids)
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
            "integrity_rejected_asset_count": self.integrity_rejected_asset_count,
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
        if self.lightweight_overlay_only:
            preferred_renderer = self._preferred_lightweight_renderer(resolved_renderer)
            if preferred_renderer is not None:
                resolved_renderer = preferred_renderer
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

    def _preferred_lightweight_renderer(self, fallback_renderer: str) -> str | None:
        preferred_renderer = normalize_renderer_name(self.lightweight_renderer_name)
        if preferred_renderer in self.available_renderers:
            return preferred_renderer
        if "mesh_v2" in self.available_renderers:
            return "mesh_v2"
        if fallback_renderer in self.available_renderers:
            return fallback_renderer
        return self.available_renderers[0] if self.available_renderers else None

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
        blended = opencv_add_weighted(
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
        if prefer_latency and self.disable_user_parsing_in_latency_mode:
            stable_bundle = self._stable_user_mask_bundle
            stable_row = self._stable_user_mask_row
            if (
                stable_bundle is not None
                and stable_row is not None
                and int(user_row.get("candidate_face_count") or 1) <= 1
                and self._bbox_iou(stable_row.get("face_bbox"), user_row.get("face_bbox")) >= 0.68
            ):
                self._user_mask_reuse_age = min(
                    self._user_mask_reuse_age + 1,
                    max(self.user_mask_latency_max_reuse_frames, self.user_mask_max_reuse_frames),
                )
                self._user_mask_bundle = stable_bundle
                return stable_bundle, "reuse_stable_mask_forced_latency", 0.0
            self._user_mask_bundle = None
            return None, "latency_skip", 0.0
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
            try:
                output_frame = compose_overlay_blend_frame(
                    held_user_row,
                    frame_bgr,
                    held_blend_assets,
                    self.asset_root,
                    renderer_name=renderer_name,
                    user_mask_bundle=self._user_mask_bundle,
                )
            except Exception as exc:
                self._mark_render_failure(
                    asset_ids=self._asset_ids_from_blend_assets(held_blend_assets),
                    error=exc,
                    context="hold_previous_failed",
                )
                return {"ok": False}, frame_bgr.copy(), None, None, []
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
        motion = {
            "pose_delta": round(pose_delta, 4),
            "center_delta_norm": round(center_delta_norm, 4),
            "size_delta_norm": round(size_delta_norm, 4),
            "fast": bool(pose_delta >= 7.0 or center_delta_norm >= 0.10 or size_delta_norm >= 0.09),
            "moderate": bool(pose_delta >= 3.0 or center_delta_norm >= 0.05 or size_delta_norm >= 0.04),
        }

        if not self.pose_smoothing_enabled:
            passthrough_row = dict(user_row)
            passthrough_row["_motion"] = motion
            self._smoothed_user_row = passthrough_row
            return passthrough_row

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
        smoothed_row["_motion"] = motion
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
        if self.lightweight_overlay_only:
            return [(primary_asset, 1.0)]
        if motion.get("fast"):
            return [(primary_asset, 1.0)]
        if self._asset_render_cost_ratio(primary_asset) >= self.render_cost_blend_disable_ratio:
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
            if yaw_gap > 8 or pitch_gap > 7 or roll_gap > 3:
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
            if yaw_gap > 3 or pitch_gap > 3 or roll_gap > 1:
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

    @staticmethod
    def _prefer_representative_candidate(
        representative_asset_id: str | None,
        ranked_assets: list[tuple[dict[str, Any], float]],
        best_asset: dict[str, Any],
        best_score: float,
    ) -> tuple[dict[str, Any], float, bool]:
        if not representative_asset_id:
            return best_asset, best_score, False

        for asset_row, score in ranked_assets[:8]:
            if str(asset_row.get("asset_id") or "") != representative_asset_id:
                continue
            if float(score) <= best_score + 2.0:
                return asset_row, float(score), asset_row["asset_id"] != best_asset["asset_id"]
            break
        return best_asset, best_score, False

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
        if should_release_current_asset(getattr(self, "angle_priority_enabled", False), user_row, current_asset, best_asset):
            return best_asset, best_score, False
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
            if not is_angle_priority_pose_compatible(
                getattr(self, "angle_priority_enabled", False),
                user_row,
                best_asset,
                asset_row,
            ):
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

    def _prefer_render_cost_candidate(
        self,
        user_row: dict[str, Any],
        ranked_assets: list[tuple[dict[str, Any], float]],
        best_asset: dict[str, Any],
        best_score: float,
        moderate_motion: bool,
        fast_motion: bool,
    ) -> tuple[dict[str, Any], float, bool]:
        best_render_cost = self._asset_render_cost_ratio(best_asset)
        best_bucket = self._render_cost_bucket(best_render_cost)
        if best_bucket <= 0:
            return best_asset, best_score, False

        if fast_motion:
            allowed_gap = min(1.0, self.render_cost_preference_score_gap)
        elif moderate_motion:
            allowed_gap = min(1.8, self.render_cost_preference_score_gap)
        else:
            allowed_gap = self.render_cost_preference_score_gap
        if best_bucket >= 2:
            allowed_gap += 0.8

        best_pose_gap = pose_distance(user_row["pose"], best_asset)
        cheaper_candidates: list[tuple[int, float, float, float, dict[str, Any]]] = []
        for asset_row, score in ranked_assets[:6]:
            render_cost_ratio = self._asset_render_cost_ratio(asset_row)
            render_cost_bucket = self._render_cost_bucket(render_cost_ratio)
            if render_cost_bucket >= best_bucket:
                continue
            if float(score) > best_score + allowed_gap:
                continue
            if render_cost_ratio > best_render_cost - 0.008:
                continue
            candidate_pose_gap = pose_distance(user_row["pose"], asset_row)
            if candidate_pose_gap > best_pose_gap + 4.0:
                continue
            if not is_angle_priority_pose_compatible(
                getattr(self, "angle_priority_enabled", False),
                user_row,
                best_asset,
                asset_row,
            ):
                continue
            cheaper_candidates.append(
                (
                    render_cost_bucket,
                    render_cost_ratio,
                    float(score),
                    candidate_pose_gap,
                    asset_row,
                )
            )

        if not cheaper_candidates:
            return best_asset, best_score, False

        cheaper_candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3], item[4]["asset_id"]))
        chosen_candidate = cheaper_candidates[0]
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
        representative_asset_id: str | None = None,
    ) -> tuple[dict[str, Any], float, str, list[tuple[dict[str, Any], float]]]:
        selection_started_at = time.perf_counter()
        if getattr(self, "angle_priority_enabled", False):
            if "_geom" not in user_row:
                user_row["_geom"] = derive_geom_from_feature(user_row)
            ranking_candidate_limit = self._ranking_candidate_limit(user_row, self.runtime_asset_count)
            shortlist, candidate_metrics = self._angle_priority_candidate_assets_for_user_row(
                user_row,
                limit=max(80, ranking_candidate_limit),
            )
            candidate_metrics = dict(candidate_metrics)
            candidate_metrics["ranking_candidate_limit"] = ranking_candidate_limit
            ranked_assets = rank_assets_by_angle_priority(
                user_row,
                shortlist,
                limit=10,
                asset_score_fn=asset_rank_score,
                asset_crop_risk_fn=self._asset_crop_risk,
            )
            if ranked_assets:
                user_row["_best_score"] = ranked_assets[0][1]
        else:
            candidate_assets, candidate_metrics = self._candidate_assets_for_user_row(user_row)
            ranking_candidate_limit = self._ranking_candidate_limit(user_row, len(candidate_assets))
            candidate_metrics = dict(candidate_metrics)
            candidate_metrics["ranking_candidate_limit"] = ranking_candidate_limit
            ranked_assets = select_best_assets(
                user_row,
                candidate_assets,
                limit=10,
                candidate_limit=ranking_candidate_limit,
            )
        if not ranked_assets:
            raise RuntimeError("No candidate assets available")
        selection_latency_ms = round((time.perf_counter() - selection_started_at) * 1000.0, 3)

        best_asset, best_score = ranked_assets[0]
        best_asset, best_score, representative_selected = self._prefer_representative_candidate(
            representative_asset_id,
            ranked_assets,
            best_asset,
            float(best_score),
        )
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
                candidate_metrics=candidate_metrics,
                selection_latency_ms=selection_latency_ms,
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
            best_asset, best_score, cost_candidate_selected = self._prefer_render_cost_candidate(
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
            if representative_selected:
                return finalize(best_asset, best_score, "initial_representative", self._blend_assets)
            if frontal_safe_selected:
                return finalize(best_asset, best_score, "initial_frontal_safe", self._blend_assets)
            if cost_candidate_selected:
                return finalize(best_asset, best_score, "initial_cost_aware", self._blend_assets)
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
        best_asset, best_score, cost_candidate_selected = self._prefer_render_cost_candidate(
            user_row,
            ranked_assets,
            best_asset,
            best_score,
            moderate_motion,
            fast_motion,
        )
        if cost_candidate_selected and band_lock_label is None:
            band_lock_label = "cost_aware"
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
        best_yaw_gap = abs(user_row["pose"]["yaw_1deg"] - int(best_asset["yaw_1deg"]))
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
        significant_improvement_threshold = (
            4.6 if vertical_view and pitch_dominant and not moderate_motion else
            4.0 if side_view and not moderate_motion else
            3.0 if side_view else
            2.2 if moderate_motion else
            3.2
        )
        if not fast_motion:
            significant_improvement_threshold += self.switch_significant_improvement_bias
        significant_improvement = (current_score - best_score) >= significant_improvement_threshold
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
        if not fast_motion:
            hold_margin += self.switch_hold_margin_bias
            if current_within_deadband and neighbor_pose:
                hold_margin += min(0.6, self.switch_hold_margin_bias * 0.75)
        hold_margin = max(1.0, hold_margin)
        force_switch = current_pose_gap > 16.0 and best_pose_gap + 3.0 < current_pose_gap
        if side_view and current_yaw_gap >= 3 and best_pose_gap + 1.5 < current_pose_gap:
            force_switch = True
        if safe_candidate_selected and not same_asset:
            force_switch = True
        in_cooldown = self._frames_since_switch < self.switch_cooldown_frames
        if should_release_current_asset(getattr(self, "angle_priority_enabled", False), user_row, current_asset, best_asset):
            significant_improvement = True
            hold_margin = max(0.8, hold_margin - 1.8)
            in_cooldown = False
            if current_yaw_gap >= 4 or best_yaw_gap <= 2:
                force_switch = True

        if same_asset:
            self._blend_assets = self._build_blend_assets(user_row, ranked_assets, current_asset, "stable")
            self._frames_since_switch += 1
            if band_lock_label == "side_band":
                return finalize(current_asset, current_score, "stable_side_band", self._blend_assets)
            if band_lock_label == "pitch_band":
                return finalize(current_asset, current_score, "stable_pitch_band", self._blend_assets)
            if band_lock_label == "cost_aware":
                return finalize(current_asset, current_score, "stable_cost_aware", self._blend_assets)
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
            if band_lock_label == "cost_aware":
                return finalize(current_asset, current_score, "hold_cost_aware", self._blend_assets)
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
            if band_lock_label == "cost_aware":
                return finalize(current_asset, current_score, "hold_cost_aware", self._blend_assets)
            if band_lock_label == "safe_asset":
                return finalize(current_asset, current_score, "hold_safe_asset", self._blend_assets)
            return finalize(current_asset, current_score, "hold", self._blend_assets)

        previous_blend_assets = self._blend_assets or [(current_asset, 1.0)]
        if fast_motion or self.lightweight_overlay_only:
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
        *,
        prefer_latency: bool,
        source_frame_bgr: np.ndarray | None = None,
    ) -> tuple[np.ndarray, float, str | None, str, np.ndarray | None]:
        resolve_mode_started_at = time.perf_counter()
        compose_mode = self._resolve_compose_mode(
            user_row,
            renderer_name,
            blend_assets,
            prefer_latency=prefer_latency,
        )
        resolve_compose_mode_ms = round((time.perf_counter() - resolve_mode_started_at) * 1000.0, 3)
        if compose_mode == "bundle_render":
            self._merge_selection_trace_fields(
                compose_detail_ms={"compose_mode": "bundle_render", "resolve_compose_mode_ms": resolve_compose_mode_ms}
            )
            return self._compose_bundle_output_frame(
                user_row,
                frame_bgr,
                source_frame_bgr,
                blend_assets,
                prefer_latency=prefer_latency,
            )

        if self.lightweight_overlay_only and self._transition is not None:
            self._transition = None
        resolve_renderer_started_at = time.perf_counter()
        effective_renderer_name = self._resolve_compose_renderer(user_row, renderer_name, blend_assets)
        resolve_compose_renderer_ms = round((time.perf_counter() - resolve_renderer_started_at) * 1000.0, 3)
        if self._transition is None:
            overlay_blend_started_at = time.perf_counter()
            overlay_blend_detail_ms: dict[str, object] = {}
            target_frame = compose_overlay_blend_frame(
                user_row,
                frame_bgr,
                blend_assets,
                self.asset_root,
                renderer_name=effective_renderer_name,
                user_mask_bundle=user_mask_bundle,
                debug_payload=overlay_blend_detail_ms,
            )
            overlay_blend_ms = round((time.perf_counter() - overlay_blend_started_at) * 1000.0, 3)
            coverage_mask = overlay_blend_detail_ms.pop("_coverage_mask", None)
            self._merge_selection_trace_fields(
                compose_detail_ms={
                    "compose_mode": "overlay",
                    "resolve_compose_mode_ms": resolve_compose_mode_ms,
                    "resolve_compose_renderer_ms": resolve_compose_renderer_ms,
                    "overlay_blend_ms": overlay_blend_ms,
                    "overlay_blend_detail_ms": overlay_blend_detail_ms,
                    "transition_blend_ms": 0.0,
                }
            )
            return target_frame, 1.0, None, effective_renderer_name, coverage_mask

        overlay_transition_started_at = time.perf_counter()
        overlay_transition_detail_ms: dict[str, object] = {}
        from_frame, target_frame = compose_overlay_transition_frames(
            user_row,
            frame_bgr,
            self._transition["from_blend_assets"],
            blend_assets,
            self.asset_root,
            renderer_name=effective_renderer_name,
            user_mask_bundle=user_mask_bundle,
            debug_payload=overlay_transition_detail_ms,
        )
        overlay_transition_frames_ms = round((time.perf_counter() - overlay_transition_started_at) * 1000.0, 3)
        self._transition["step"] += 1
        transition_progress = min(1.0, self._transition["step"] / float(self._transition["steps"]))
        transition_blend_started_at = time.perf_counter()
        blended_frame = opencv_add_weighted(from_frame, 1.0 - transition_progress, target_frame, transition_progress, 0.0)
        transition_blend_ms = round((time.perf_counter() - transition_blend_started_at) * 1000.0, 3)
        coverage_mask = overlay_transition_detail_ms.pop("_coverage_mask", None)
        from_asset_id = str(self._transition["from_asset_id"])
        if transition_progress >= 1.0:
            self._transition = None
        self._merge_selection_trace_fields(
            compose_detail_ms={
                "compose_mode": "overlay_transition",
                "resolve_compose_mode_ms": resolve_compose_mode_ms,
                "resolve_compose_renderer_ms": resolve_compose_renderer_ms,
                "overlay_transition_frames_ms": overlay_transition_frames_ms,
                "transition_blend_ms": transition_blend_ms,
                "overlay_transition_detail_ms": overlay_transition_detail_ms,
            }
        )
        return blended_frame, transition_progress, from_asset_id, effective_renderer_name, coverage_mask

    def _resolve_compose_mode(
        self,
        user_row: dict[str, Any],
        renderer_name: str,
        blend_assets: list[tuple[dict[str, Any], float]],
        *,
        prefer_latency: bool,
    ) -> str:
        if self.lightweight_overlay_only or not self.bundle_render_enabled or not blend_assets:
            return "overlay"
        if bool(user_row.get("_force_bundle_render")):
            primary_asset = blend_assets[0][0]
            try:
                entry = self._bundle_render_entry_for_asset(primary_asset)
            except Exception:
                return "overlay"
            if entry.hair_rgba_path is None or entry.hair_bbox is None:
                return "overlay"
            return "bundle_render"
        if self.bundle_render_latency_only and not prefer_latency:
            return "overlay"

        primary_asset = blend_assets[0][0]
        if self._asset_render_cost_ratio(primary_asset) < self.bundle_render_render_cost_ratio:
            return "overlay"

        resolved_renderer = normalize_renderer_name(renderer_name)
        if resolved_renderer not in {"mesh_v2", "mesh_v3", "mesh_v4"}:
            return "overlay"

        try:
            entry = self._bundle_render_entry_for_asset(primary_asset)
        except Exception:
            return "overlay"
        if entry.hair_rgba_path is None or entry.hair_bbox is None:
            return "overlay"
        return "bundle_render"

    @staticmethod
    def _estimate_hair_rgba_luma(hair_rgba_path: Path | None) -> float | None:
        if hair_rgba_path is None or not hair_rgba_path.is_file():
            return None
        try:
            rgba_image = Image.open(hair_rgba_path).convert("RGBA")
        except Exception:
            return None

        rgba = np.asarray(rgba_image, dtype=np.uint8)
        if rgba.ndim != 3 or rgba.shape[2] != 4:
            return None

        alpha_mask = rgba[:, :, 3] >= 24
        active_pixels = int(np.count_nonzero(alpha_mask))
        if active_pixels < max(32, int(round(alpha_mask.size * 0.006))):
            return None

        rgb = rgba[:, :, :3].astype(np.float32)
        luma = (
            rgb[:, :, 0] * 0.114
            + rgb[:, :, 1] * 0.587
            + rgb[:, :, 2] * 0.299
        )
        mean_luma = float(np.mean(luma[alpha_mask]))
        if not np.isfinite(mean_luma) or mean_luma <= 1.0:
            return None
        return round(mean_luma, 3)

    def _bundle_render_entry_for_asset(
        self,
        asset_row: dict[str, Any],
        *,
        debug_payload: dict[str, object] | None = None,
    ) -> RuntimeBundleRenderEntry:
        entry_started_at = time.perf_counter()
        cache_key = str(asset_row.get("asset_id") or asset_row.get("metadata_path") or "").strip()
        if cache_key:
            cached_entry = self._bundle_render_entry_cache.get(cache_key)
            if cached_entry is not None:
                if debug_payload is not None:
                    debug_payload.update(
                        {
                            "entry_cache_hit": True,
                            "metadata_json_ms": 0.0,
                            "anchors_json_ms": 0.0,
                            "hair_luma_ms": 0.0,
                            "entry_total_ms": round((time.perf_counter() - entry_started_at) * 1000.0, 3),
                        }
                    )
                return cached_entry

        metadata_path_raw = str(asset_row.get("metadata_path") or "").strip()
        anchors_path_raw = str(asset_row.get("anchors_path") or "").strip()
        if not metadata_path_raw or not anchors_path_raw:
            raise FileNotFoundError("missing metadata_path or anchors_path for bundle render")

        metadata_started_at = time.perf_counter()
        metadata = read_json(resolve_asset_path(self.asset_root, metadata_path_raw))
        metadata_json_ms = round((time.perf_counter() - metadata_started_at) * 1000.0, 3)
        anchors_started_at = time.perf_counter()
        anchors_payload = read_json(resolve_asset_path(self.asset_root, anchors_path_raw))
        anchors_json_ms = round((time.perf_counter() - anchors_started_at) * 1000.0, 3)
        hair_rgba_path_raw = str(metadata.get("hair_rgba_path") or "").strip()
        face_mask_path_raw = str(metadata.get("face_mask_path") or "").strip()
        protect_face_mask_path_raw = str(metadata.get("protect_face_mask_path") or "").strip()
        hair_rgba_path = (
            resolve_asset_path(self.asset_root, hair_rgba_path_raw)
            if hair_rgba_path_raw
            else None
        )
        if hair_rgba_path is not None and not hair_rgba_path.is_file():
            hair_rgba_path = None
        face_mask_path = (
            resolve_asset_path(self.asset_root, face_mask_path_raw)
            if face_mask_path_raw
            else None
        )
        if face_mask_path is not None and not face_mask_path.is_file():
            face_mask_path = None
        protect_face_mask_path = (
            resolve_asset_path(self.asset_root, protect_face_mask_path_raw)
            if protect_face_mask_path_raw
            else None
        )
        if protect_face_mask_path is not None and not protect_face_mask_path.is_file():
            protect_face_mask_path = None
        hair_luma_started_at = time.perf_counter()
        hair_luma = self._estimate_hair_rgba_luma(hair_rgba_path)
        hair_luma_ms = round((time.perf_counter() - hair_luma_started_at) * 1000.0, 3)

        entry = RuntimeBundleRenderEntry(
            asset_id=str(asset_row.get("asset_id") or metadata_path_raw),
            metadata=metadata,
            anchors_payload=anchors_payload,
            hair_rgba_path=hair_rgba_path,
            hair_bbox=metadata.get("hair_rgba_bbox"),
            hair_luma=hair_luma,
            face_mask_path=face_mask_path,
            protect_face_mask_path=protect_face_mask_path,
        )
        if cache_key:
            if cache_key not in self._bundle_render_entry_cache and len(self._bundle_render_entry_cache) >= self._bundle_render_entry_cache_limit:
                oldest_key = next(iter(self._bundle_render_entry_cache))
                self._bundle_render_entry_cache.pop(oldest_key, None)
            self._bundle_render_entry_cache[cache_key] = entry
        if debug_payload is not None:
            debug_payload.update(
                {
                    "entry_cache_hit": False,
                    "metadata_json_ms": metadata_json_ms,
                    "anchors_json_ms": anchors_json_ms,
                    "hair_luma_ms": hair_luma_ms,
                    "entry_total_ms": round((time.perf_counter() - entry_started_at) * 1000.0, 3),
                }
            )
        return entry

    def _feature_message_from_user_row(self, user_row: dict[str, Any]) -> FeatureMessageModel:
        return FeatureMessageModel.model_validate(
            {
                "type": "feature",
                "feature_schema_version": 2,
                "coordinate_space": "pixel_v1",
                "anchor_set": "face_anchor_v1",
                "transform_version": "affine_v1",
                "seq": 1,
                "ts_ms": 0,
                "apply_session_id": "runtime",
                "hair_id": 1,
                "image_size": user_row["image_size"],
                "pose": user_row["pose"],
                "face_bbox": user_row["face_bbox"],
                "anchors": user_row["anchors"],
            }
        )

    def _compose_single_bundle_render_frame(
        self,
        user_row: dict[str, Any],
        frame_bgr: np.ndarray,
        asset_row: dict[str, Any],
        *,
        source_frame_bgr: np.ndarray | None = None,
        debug_payload: dict[str, object] | None = None,
    ) -> tuple[np.ndarray, np.ndarray | None]:
        compose_started_at = time.perf_counter()
        entry_debug_payload: dict[str, object] = {}
        entry = self._bundle_render_entry_for_asset(asset_row, debug_payload=entry_debug_payload)
        if entry.hair_rgba_path is None or entry.hair_bbox is None:
            raise FileNotFoundError(f"bundle render unavailable for asset {entry.asset_id}")

        render_task_started_at = time.perf_counter()
        render_task = build_render_task(
            feature=self._feature_message_from_user_row(user_row),
            asset_anchors_payload=entry.anchors_payload,
            metadata=entry.metadata,
        )
        if render_task is None:
            raise RuntimeError(f"failed to build render_task for asset {entry.asset_id}")
        render_task_build_ms = round((time.perf_counter() - render_task_started_at) * 1000.0, 3)

        payload = RuntimeBundleRenderPayload(
            hair_rgba_path=entry.hair_rgba_path,
            render_task=render_task.to_message(),
            hair_bbox=entry.hair_bbox,
            face_mask_path=entry.face_mask_path,
            protect_face_mask_path=entry.protect_face_mask_path,
        )
        rgb_gain = resolve_hair_tone_gain(user_row, entry.hair_luma)
        skin_replacement_color_rgb = None
        scalp_color = user_row.get("_hair_scalp_color")
        if scalp_color is not None:
            scalp_color_array = np.asarray(scalp_color, dtype=np.float32).reshape(-1)
            if scalp_color_array.size >= 3 and bool(np.all(np.isfinite(scalp_color_array[:3]))):
                skin_replacement_color_rgb = scalp_color_array[:3][::-1].astype(np.float32)
        frame_to_pil_started_at = time.perf_counter()
        frame_image = Image.fromarray(opencv_cvt_color(frame_bgr, cv2.COLOR_BGR2RGB))
        frame_to_pil_ms = round((time.perf_counter() - frame_to_pil_started_at) * 1000.0, 3)
        original_frame_image = None
        source_to_pil_ms = 0.0
        if isinstance(source_frame_bgr, np.ndarray) and source_frame_bgr.shape == frame_bgr.shape:
            source_to_pil_started_at = time.perf_counter()
            original_frame_image = Image.fromarray(opencv_cvt_color(source_frame_bgr, cv2.COLOR_BGR2RGB))
            source_to_pil_ms = round((time.perf_counter() - source_to_pil_started_at) * 1000.0, 3)
        server_debug_payload: dict[str, object] = {}
        compose_bundle_started_at = time.perf_counter()
        rendered_image = compose_bundle_frame(
            frame_image,
            payload,
            rgb_gain=rgb_gain,
            original_frame_image=original_frame_image,
            skin_replacement_color_rgb=skin_replacement_color_rgb,
            debug_payload=server_debug_payload,
        )
        compose_bundle_frame_ms = round((time.perf_counter() - compose_bundle_started_at) * 1000.0, 3)
        pil_to_bgr_started_at = time.perf_counter()
        rendered_bgr = opencv_cvt_color(np.asarray(rendered_image), cv2.COLOR_RGB2BGR)
        pil_to_bgr_ms = round((time.perf_counter() - pil_to_bgr_started_at) * 1000.0, 3)
        coverage_mask = server_debug_payload.get("coverage_mask")
        if not isinstance(coverage_mask, np.ndarray) or coverage_mask.shape != frame_bgr.shape[:2]:
            coverage_mask = None
        if debug_payload is not None:
            debug_payload.update(
                {
                    "asset_id": entry.asset_id,
                    "entry_cache_hit": bool(entry_debug_payload.get("entry_cache_hit")),
                    "entry_detail_ms": entry_debug_payload,
                    "render_task_build_ms": render_task_build_ms,
                    "frame_to_pil_ms": frame_to_pil_ms,
                    "source_to_pil_ms": source_to_pil_ms,
                    "compose_bundle_frame_ms": compose_bundle_frame_ms,
                    "pil_to_bgr_ms": pil_to_bgr_ms,
                    "bundle_frame_detail_ms": dict(server_debug_payload.get("timings_ms") or {}),
                    "total_ms": round((time.perf_counter() - compose_started_at) * 1000.0, 3),
                }
            )
        return rendered_bgr, coverage_mask

    def _compose_bundle_output_frame(
        self,
        user_row: dict[str, Any],
        frame_bgr: np.ndarray,
        source_frame_bgr: np.ndarray | None,
        blend_assets: list[tuple[dict[str, Any], float]],
        *,
        prefer_latency: bool,
    ) -> tuple[np.ndarray, float, str | None, str, np.ndarray | None]:
        primary_asset = blend_assets[0][0]
        target_debug_payload: dict[str, object] = {}
        target_frame, target_coverage_mask = self._compose_single_bundle_render_frame(
            user_row,
            frame_bgr,
            primary_asset,
            source_frame_bgr=source_frame_bgr,
            debug_payload=target_debug_payload,
        )

        primary_render_cost_ratio = self._asset_render_cost_ratio(primary_asset)
        compose_detail_ms: dict[str, object] = {
            "compose_mode": "bundle_render",
            "primary_asset_id": str(primary_asset.get("asset_id") or ""),
            "primary_render_cost_ratio": round(primary_render_cost_ratio, 6),
            "target_bundle_ms": round(float(target_debug_payload.get("total_ms") or 0.0), 3),
            "target_entry_cache_hit": bool(target_debug_payload.get("entry_cache_hit")),
            "transition_enabled": bool(self._transition is not None and self.bundle_render_allow_transition and not prefer_latency),
        }
        if (
            self._transition is None
            or not self.bundle_render_allow_transition
            or prefer_latency
            or primary_render_cost_ratio >= max(
                self.bundle_render_render_cost_ratio + 0.012,
                self.render_cost_renderer_downgrade_ratio,
            )
        ):
            compose_detail_ms["transition_blend_ms"] = 0.0
            self._merge_selection_trace_fields(
                compose_detail_ms=compose_detail_ms,
                bundle_detail_ms={"target": target_debug_payload},
            )
            return target_frame, 1.0, None, "bundle_render", target_coverage_mask

        from_asset_id = str(self._transition["from_asset_id"])
        from_asset = next(
            (
                asset_row
                for asset_row, _ in self._transition["from_blend_assets"]
                if str(asset_row.get("asset_id") or "") == from_asset_id
            ),
            None,
        )
        if from_asset is None:
            self._transition = None
            compose_detail_ms["transition_blend_ms"] = 0.0
            self._merge_selection_trace_fields(
                compose_detail_ms=compose_detail_ms,
                bundle_detail_ms={"target": target_debug_payload},
            )
            return target_frame, 1.0, None, "bundle_render", target_coverage_mask

        from_debug_payload: dict[str, object] = {}
        from_frame, from_coverage_mask = self._compose_single_bundle_render_frame(
            user_row,
            frame_bgr,
            from_asset,
            source_frame_bgr=source_frame_bgr,
            debug_payload=from_debug_payload,
        )
        self._transition["step"] += 1
        transition_progress = min(1.0, self._transition["step"] / float(self._transition["steps"]))
        transition_blend_started_at = time.perf_counter()
        blended_frame = opencv_add_weighted(
            from_frame,
            1.0 - transition_progress,
            target_frame,
            transition_progress,
            0.0,
        )
        transition_blend_ms = round((time.perf_counter() - transition_blend_started_at) * 1000.0, 3)
        blended_coverage_mask = target_coverage_mask
        if (
            isinstance(target_coverage_mask, np.ndarray)
            and isinstance(from_coverage_mask, np.ndarray)
            and target_coverage_mask.shape == from_coverage_mask.shape
        ):
            blended_coverage_mask = np.maximum(target_coverage_mask, from_coverage_mask)
        if transition_progress >= 1.0:
            self._transition = None
        compose_detail_ms.update(
            {
                "from_asset_id": from_asset_id,
                "from_bundle_ms": round(float(from_debug_payload.get("total_ms") or 0.0), 3),
                "from_entry_cache_hit": bool(from_debug_payload.get("entry_cache_hit")),
                "transition_blend_ms": transition_blend_ms,
            }
        )
        self._merge_selection_trace_fields(
            compose_detail_ms=compose_detail_ms,
            bundle_detail_ms={"target": target_debug_payload, "from": from_debug_payload},
        )
        return blended_frame, transition_progress, from_asset_id, "bundle_render", blended_coverage_mask

    def _apply_overlay_postprocess(
        self,
        output_frame_bgr: np.ndarray,
        base_frame_bgr: np.ndarray,
        user_row: dict[str, Any],
        *,
        renderer_name: str,
        coverage_mask: np.ndarray | None = None,
    ) -> np.ndarray:
        return apply_overlay_postprocess(
            output_frame_bgr,
            base_frame_bgr,
            user_row,
            renderer_name=renderer_name,
            coverage_mask=coverage_mask,
        )

    def _resolve_compose_renderer(
        self,
        user_row: dict[str, Any],
        renderer_name: str,
        blend_assets: list[tuple[dict[str, Any], float]],
    ) -> str:
        resolved_renderer = normalize_renderer_name(renderer_name)
        if self.lightweight_overlay_only:
            preferred_renderer = self._preferred_lightweight_renderer(resolved_renderer)
            if preferred_renderer is not None:
                return preferred_renderer
        if resolved_renderer not in {"mesh_v3", "mesh_v4"} or not blend_assets:
            return resolved_renderer

        primary_asset = blend_assets[0][0]
        render_cost_ratio = self._asset_render_cost_ratio(primary_asset)
        if render_cost_ratio < self.render_cost_renderer_downgrade_ratio:
            return resolved_renderer
        if "mesh_v2" in self.available_renderers:
            return "mesh_v2"
        return resolved_renderer

    def process_frame(
        self,
        frame_bgr: np.ndarray,
        renderer_name: str | None = None,
        render_frame_bgr: np.ndarray | None = None,
        source_frame_bgr: np.ndarray | None = None,
        tracked_user_row: dict[str, Any] | None = None,
        prefer_latency: bool = False,
        session_id: str | None = None,
        representative_asset_id: str | None = None,
        encode_output: bool = True,
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
                compose_source_bgr = (
                    source_frame_bgr
                    if isinstance(source_frame_bgr, np.ndarray)
                    and source_frame_bgr.shape == frame_bgr.shape
                    else frame_bgr
                )
                if tracked_user_row is not None:
                    raw_user_row = dict(tracked_user_row)
                    feature_latency_ms = 0.0
                else:
                    reference_face_bbox = None if self._smoothed_user_row is None else self._smoothed_user_row.get("face_bbox")
                    raw_user_row = extract_feature_from_frame_bgr(
                        frame_bgr,
                        self._ensure_landmarker(),
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
                overlay_coverage_mask: np.ndarray | None = None
                blend_assets: list[tuple[dict[str, Any], float]] = []
                output_frame = compose_frame_bgr.copy()
                render_error = None
                user_mask_bundle: dict[str, Any] | None = None
                user_parsing_status = "disabled"
                user_parsing_latency_ms = 0.0
                overlay_detail_ms: dict[str, float | str] = {}
                selection_trace: dict[str, Any] | None = self._last_selection_trace
                effective_renderer_name = resolved_renderer

                overlay_started_at = time.perf_counter()
                if raw_user_row.get("ok"):
                    if self._is_face_tracking_outlier(raw_user_row):
                        self._missing_face_count = 0
                        self._invalid_face_count += 1
                        if self._invalid_face_count < 2 and self._smoothed_user_row is not None:
                            hold_started_at = time.perf_counter()
                            user_row, output_frame, selected_asset_id, selected_pose_key, blend_assets = self._hold_previous_tracking_frame(
                                compose_frame_bgr,
                                resolved_renderer,
                            )
                            overlay_detail_ms["hold_previous_ms"] = round((time.perf_counter() - hold_started_at) * 1000.0, 3)
                            runtime_status = "face_tracking_outlier_hold"
                            selection_mode = "hold_tracking"
                            transition_progress = 1.0 if blend_assets else 0.0
                            user_parsing_status = "hold_previous"
                            if self._last_selection_trace is not None:
                                selection_trace = dict(self._last_selection_trace)
                                selection_trace["decision"] = selection_mode
                        else:
                            self._invalid_face_count = 0
                            smooth_started_at = time.perf_counter()
                            user_row = self._smooth_user_row(raw_user_row)
                            overlay_detail_ms["smooth_ms"] = round((time.perf_counter() - smooth_started_at) * 1000.0, 3)
                            user_mask_bundle, user_parsing_status, user_parsing_latency_ms = self._parse_user_masks(
                                frame_bgr,
                                user_row,
                                resolved_renderer,
                                prefer_latency=prefer_latency,
                            )
                            overlay_detail_ms["parse_user_masks_ms"] = round(float(user_parsing_latency_ms), 3)
                            attach_context_started_at = time.perf_counter()
                            user_row = self._attach_runtime_fit_context(user_row, user_mask_bundle)
                            overlay_detail_ms["attach_context_ms"] = round((time.perf_counter() - attach_context_started_at) * 1000.0, 3)
                            render_flow_started_at = time.perf_counter()
                            render_result = self._select_and_compose_output_frame(
                                user_row=user_row,
                                compose_frame_bgr=compose_frame_bgr,
                                source_frame_bgr=compose_source_bgr,
                                renderer_name=resolved_renderer,
                                user_mask_bundle=user_mask_bundle,
                                representative_asset_id=representative_asset_id,
                                prefer_latency=prefer_latency,
                            )
                            overlay_detail_ms["select_and_compose_ms"] = round((time.perf_counter() - render_flow_started_at) * 1000.0, 3)
                            output_frame = render_result["output_frame"]
                            selected_asset_id = render_result["selected_asset_id"]
                            selected_pose_key = render_result["selected_pose_key"]
                            score = render_result["score"]
                            selection_mode = render_result["selection_mode"]
                            blend_assets = render_result["blend_assets"]
                            transition_progress = render_result["transition_progress"]
                            transition_from_asset_id = render_result["transition_from_asset_id"]
                            selection_trace = render_result["selection_trace"]
                            render_error = render_result["render_error"]
                            runtime_status = render_result["status"]
                            effective_renderer_name = str(render_result.get("effective_renderer_name") or resolved_renderer)
                            overlay_coverage_mask = render_result.get("coverage_mask")
                            postprocess_started_at = time.perf_counter()
                            output_frame = self._apply_overlay_postprocess(
                                output_frame,
                                compose_frame_bgr,
                                user_row,
                                renderer_name=effective_renderer_name,
                                coverage_mask=overlay_coverage_mask,
                            )
                            overlay_detail_ms["postprocess_ms"] = round((time.perf_counter() - postprocess_started_at) * 1000.0, 3)
                    else:
                        self._missing_face_count = 0
                        self._invalid_face_count = 0
                        smooth_started_at = time.perf_counter()
                        user_row = self._smooth_user_row(raw_user_row)
                        overlay_detail_ms["smooth_ms"] = round((time.perf_counter() - smooth_started_at) * 1000.0, 3)
                        user_mask_bundle, user_parsing_status, user_parsing_latency_ms = self._parse_user_masks(
                            frame_bgr,
                            user_row,
                            resolved_renderer,
                            prefer_latency=prefer_latency,
                        )
                        overlay_detail_ms["parse_user_masks_ms"] = round(float(user_parsing_latency_ms), 3)
                        attach_context_started_at = time.perf_counter()
                        user_row = self._attach_runtime_fit_context(user_row, user_mask_bundle)
                        overlay_detail_ms["attach_context_ms"] = round((time.perf_counter() - attach_context_started_at) * 1000.0, 3)
                        render_flow_started_at = time.perf_counter()
                        render_result = self._select_and_compose_output_frame(
                            user_row=user_row,
                            compose_frame_bgr=compose_frame_bgr,
                            source_frame_bgr=compose_source_bgr,
                            renderer_name=resolved_renderer,
                            user_mask_bundle=user_mask_bundle,
                            representative_asset_id=representative_asset_id,
                            prefer_latency=prefer_latency,
                        )
                        overlay_detail_ms["select_and_compose_ms"] = round((time.perf_counter() - render_flow_started_at) * 1000.0, 3)
                        output_frame = render_result["output_frame"]
                        selected_asset_id = render_result["selected_asset_id"]
                        selected_pose_key = render_result["selected_pose_key"]
                        score = render_result["score"]
                        selection_mode = render_result["selection_mode"]
                        blend_assets = render_result["blend_assets"]
                        transition_progress = render_result["transition_progress"]
                        transition_from_asset_id = render_result["transition_from_asset_id"]
                        selection_trace = render_result["selection_trace"]
                        render_error = render_result["render_error"]
                        runtime_status = render_result["status"]
                        effective_renderer_name = str(render_result.get("effective_renderer_name") or resolved_renderer)
                        overlay_coverage_mask = render_result.get("coverage_mask")
                        postprocess_started_at = time.perf_counter()
                        output_frame = self._apply_overlay_postprocess(
                            output_frame,
                            compose_frame_bgr,
                            user_row,
                            renderer_name=effective_renderer_name,
                            coverage_mask=overlay_coverage_mask,
                        )
                        overlay_detail_ms["postprocess_ms"] = round((time.perf_counter() - postprocess_started_at) * 1000.0, 3)
                else:
                    runtime_status = str(raw_user_row.get("reason", "no_face_or_pose"))
                    selection_mode = "no_face"
                    self._missing_face_count += 1
                    self._invalid_face_count = 0
                    if self._missing_face_count >= 3:
                        self._reset_session_state(session)
                overlay_latency_ms = round((time.perf_counter() - overlay_started_at) * 1000.0, 3)
                overlay_detail_ms["overlay_total_ms"] = overlay_latency_ms
                overlay_detail_ms["user_parsing_status"] = user_parsing_status
                if selection_trace is not None:
                    selection_trace = dict(selection_trace)
                    existing_overlay_detail = selection_trace.get("overlay_detail_ms")
                    merged_overlay_detail = (
                        dict(existing_overlay_detail)
                        if isinstance(existing_overlay_detail, dict)
                        else {}
                    )
                    merged_overlay_detail.update(overlay_detail_ms)
                    selection_trace["overlay_detail_ms"] = merged_overlay_detail
                    self._last_selection_trace = selection_trace
                session.last_seen_monotonic = time.monotonic()
                active_session_count = len(self._sessions)
            finally:
                self._current_session = previous_session

        image_bytes: bytes | None = None
        if encode_output:
            encoded_ok, encoded = cv2.imencode(".jpg", output_frame, jpeg_params(self.jpeg_quality))
            if not encoded_ok:
                raise RuntimeError("Failed to encode overlay image")
            image_bytes = encoded.tobytes()

        total_latency_ms = round((time.perf_counter() - started_at) * 1000.0, 3)
        selection_latency_ms = 0.0
        compose_latency_ms = 0.0
        candidate_source = None
        candidate_pool_size = None
        compose_detail_ms: dict[str, object] | None = None
        bundle_detail_ms: dict[str, object] | None = None
        overlay_detail_payload: dict[str, object] | None = None
        if selection_trace is not None:
            selection_latency_ms = float(selection_trace.get("selection_latency_ms") or 0.0)
            compose_latency_ms = float(selection_trace.get("compose_latency_ms") or 0.0)
            candidate_metrics = selection_trace.get("candidate_metrics") or {}
            if isinstance(candidate_metrics, dict):
                candidate_source = candidate_metrics.get("source")
                candidate_pool_size = candidate_metrics.get("candidate_pool_size")
            compose_detail_candidate = selection_trace.get("compose_detail_ms")
            if isinstance(compose_detail_candidate, dict):
                compose_detail_ms = compose_detail_candidate
            bundle_detail_candidate = selection_trace.get("bundle_detail_ms")
            if isinstance(bundle_detail_candidate, dict):
                bundle_detail_ms = bundle_detail_candidate
            overlay_detail_candidate = selection_trace.get("overlay_detail_ms")
            if isinstance(overlay_detail_candidate, dict):
                overlay_detail_payload = overlay_detail_candidate
        if total_latency_ms >= 100.0 or overlay_latency_ms >= 80.0:
            logger.info(
                "hair runtime perf dataset=%s selection_mode=%s asset=%s feature_ms=%.1f selection_ms=%.1f compose_ms=%.1f parsing_ms=%.1f overlay_ms=%.1f total_ms=%.1f candidate_source=%s candidate_pool=%s",
                self.asset_root.name,
                selection_mode,
                selected_asset_id,
                feature_latency_ms,
                selection_latency_ms,
                compose_latency_ms,
                user_parsing_latency_ms,
                overlay_latency_ms,
                total_latency_ms,
                candidate_source,
                candidate_pool_size,
            )
            logger.info(
                "hair runtime overlay detail dataset=%s selection_mode=%s asset=%s detail=%s",
                self.asset_root.name,
                selection_mode,
                selected_asset_id,
                overlay_detail_payload or {},
            )
            if compose_detail_ms is not None:
                logger.info(
                    "hair runtime compose detail dataset=%s selection_mode=%s asset=%s detail=%s",
                    self.asset_root.name,
                    selection_mode,
                    selected_asset_id,
                    compose_detail_ms,
                )
            if bundle_detail_ms is not None:
                logger.info(
                    "hair runtime bundle detail dataset=%s selection_mode=%s asset=%s detail=%s",
                    self.asset_root.name,
                    selection_mode,
                    selected_asset_id,
                    bundle_detail_ms,
                )
        return {
            "image_bytes": image_bytes,
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
            "renderer_name": effective_renderer_name,
            "requested_renderer_name": resolved_renderer,
            "latency_ms": total_latency_ms,
            "feature_latency_ms": feature_latency_ms,
            "selection_latency_ms": selection_latency_ms,
            "compose_latency_ms": compose_latency_ms,
            "primary_overlay_latency_ms": overlay_latency_ms,
            "fallback_latency_ms": 0.0,
            "overlay_latency_ms": overlay_latency_ms,
            "user_parsing_status": user_parsing_status,
            "user_parsing_latency_ms": user_parsing_latency_ms,
            "session_id": session.session_id,
            "active_session_count": active_session_count,
            "overlay_detail_ms": overlay_detail_payload,
            "compose_detail_ms": compose_detail_ms,
            "bundle_detail_ms": bundle_detail_ms,
            "selection_trace": selection_trace,
            "render_error": render_error,
        }

    def reset_session(self, session_id: str | None) -> None:
        normalized_session_id = self._sanitize_session_id(session_id)
        with self._lock:
            session = self._sessions.get(normalized_session_id)
            if session is None:
                return
            self._reset_session_state(session)

    def close(self) -> None:
        with self._lock:
            self._sessions.clear()
            if self._landmarker is not None:
                self._landmarker.close()
