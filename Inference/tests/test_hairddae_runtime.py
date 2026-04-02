from __future__ import annotations

import json
import threading
from pathlib import Path

import cv2
import numpy as np
import pytest

pytest.importorskip("cv2")
pytest.importorskip("mediapipe")

import app.overlay_postprocess_pipeline as overlay_postprocess_pipeline
from app.hairddae_runtime import HairOverlayRuntime, RuntimeBundleRenderEntry
from hairddae_tools.run_hair_overlay_poc import asset_rank_score, pose_distance


def build_runtime_stub() -> HairOverlayRuntime:
    runtime = HairOverlayRuntime.__new__(HairOverlayRuntime)
    runtime.asset_root = Path(".")
    runtime.model_path = Path(".")
    runtime.jpeg_quality = 88
    runtime.approved_only_mode = True
    runtime.approved_strict_only_mode = False
    runtime.session_ttl_sec = 180
    runtime.session_limit = 8
    runtime.user_mask_max_reuse_frames = 1
    runtime.user_mask_latency_max_reuse_frames = 2
    runtime.user_mask_reuse_pose_delta_max = 1.2
    runtime.user_mask_reuse_center_delta_max = 0.018
    runtime.user_mask_reuse_size_delta_max = 0.018
    runtime.user_mask_reuse_bbox_iou_min = 0.86
    runtime.disable_user_parsing_in_latency_mode = False
    runtime._lock = threading.Lock()
    runtime._landmarker = None
    runtime._user_parser = None
    runtime._current_session = None
    runtime._sessions = {}
    runtime._integrity_rejected_asset_ids = set()
    runtime._asset_pose_index = {}
    runtime.user_parsing_ready = False
    runtime.user_parsing_error = None
    runtime.available_renderers = ["mesh_v3"]
    runtime.default_renderer_name = "mesh_v3"
    runtime.selection_candidate_limit = 96
    runtime.render_cost_blend_disable_ratio = 0.118
    runtime.render_cost_renderer_downgrade_ratio = 0.108
    runtime.render_cost_preference_score_gap = 2.4
    runtime.switch_cooldown_frames = 3
    runtime.switch_hold_margin_bias = 0.8
    runtime.switch_significant_improvement_bias = 0.8
    runtime.force_switch_angle_deg = 10
    runtime.angle_priority_enabled = False
    runtime.pose_smoothing_enabled = True
    runtime.bundle_render_enabled = True
    runtime.bundle_render_latency_only = True
    runtime.bundle_render_render_cost_ratio = 0.098
    runtime.bundle_render_allow_transition = True
    runtime.lightweight_overlay_only = False
    runtime.lightweight_renderer_name = "mesh_v2"
    runtime.assets = []
    runtime.asset_count = 0
    runtime.approved_asset_count = 0
    runtime.approved_runtime_asset_count = 0
    runtime.approved_strict_asset_count = 0
    runtime.blacklisted_asset_count = 0
    runtime.integrity_rejected_asset_count = 0
    runtime.runtime_asset_count = 0
    runtime.unique_pose_count = 0
    runtime.pitch_range = {"min": 0, "max": 0, "high_pitch_pose_count": 0}
    runtime._bundle_render_entry_cache = {}
    return runtime


def test_smooth_user_row_can_disable_pose_smoothing() -> None:
    runtime = build_runtime_stub()
    runtime.pose_smoothing_enabled = False
    runtime._current_session = runtime._get_or_create_session("no-smooth")
    try:
        first_row = {
            "pose": {
                "yaw_float": 0.0,
                "pitch_float": 0.0,
                "roll_float": 0.0,
                "yaw_1deg": 0,
                "pitch_1deg": 0,
                "roll_1deg": 0,
            },
            "face_bbox": {"x": 10, "y": 12, "w": 100, "h": 120},
            "anchors": {"left_eye": {"x": 35.0, "y": 48.0}},
            "face_ratio": 0.41,
        }
        second_row = {
            "pose": {
                "yaw_float": 6.0,
                "pitch_float": 2.0,
                "roll_float": 1.0,
                "yaw_1deg": 6,
                "pitch_1deg": 2,
                "roll_1deg": 1,
            },
            "face_bbox": {"x": 24, "y": 20, "w": 110, "h": 126},
            "anchors": {"left_eye": {"x": 41.0, "y": 52.0}},
            "face_ratio": 0.46,
        }

        seeded_row = runtime._smooth_user_row(first_row)
        passthrough_row = runtime._smooth_user_row(second_row)
    finally:
        runtime._current_session = None

    assert seeded_row["pose"] == first_row["pose"]
    assert seeded_row["_motion"]["pose_delta"] == 0.0
    assert passthrough_row["pose"] == second_row["pose"]
    assert passthrough_row["face_bbox"] == second_row["face_bbox"]
    assert passthrough_row["anchors"] == second_row["anchors"]
    assert passthrough_row["face_ratio"] == second_row["face_ratio"]
    assert passthrough_row["_motion"]["pose_delta"] == 6.0
    assert passthrough_row["_motion"]["fast"] is True


def test_select_asset_holds_during_switch_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = build_runtime_stub()
    current_asset = {"asset_id": "asset-current", "pose_key": "pose-current", "yaw_1deg": 0, "pitch_1deg": 0, "roll_1deg": 0}
    best_asset = {"asset_id": "asset-best", "pose_key": "pose-best", "yaw_1deg": 4, "pitch_1deg": 0, "roll_1deg": 0}
    session = runtime._get_or_create_session("cooldown")
    runtime._current_session = session
    runtime._selected_asset = current_asset
    runtime._blend_assets = [(current_asset, 1.0)]
    runtime._frames_since_switch = 1

    user_row = {
        "pose": {"yaw_1deg": 4, "pitch_1deg": 0, "roll_1deg": 0},
        "_motion": {"fast": False, "moderate": False},
    }

    monkeypatch.setattr(runtime, "_candidate_assets_for_user_row", lambda user_row: ([current_asset, best_asset], {"source": "test", "candidate_pool_size": 2}))
    monkeypatch.setattr("app.hairddae_runtime.select_best_assets", lambda user_row, candidate_assets, limit=10, candidate_limit=96: [(best_asset, 1.0), (current_asset, 4.0)])
    monkeypatch.setattr("app.hairddae_runtime.asset_rank_score", lambda user_row, asset_row: 4.0 if asset_row["asset_id"] == "asset-current" else 1.0)
    monkeypatch.setattr(runtime, "_prefer_side_band_candidate", lambda *args, **kwargs: (args[3], args[4], False))
    monkeypatch.setattr(runtime, "_prefer_pitch_band_candidate", lambda *args, **kwargs: (args[3], args[4], False))
    monkeypatch.setattr(runtime, "_prefer_frontal_safe_candidate", lambda *args, **kwargs: (args[2], args[3], False))
    monkeypatch.setattr(runtime, "_prefer_render_cost_candidate", lambda *args, **kwargs: (args[2], args[3], False))
    monkeypatch.setattr(runtime, "_prefer_render_safe_candidate", lambda *args, **kwargs: (args[2], args[3], False))
    monkeypatch.setattr(runtime, "_build_blend_assets", lambda user_row, ranked_assets, primary_asset, selection_mode: [(primary_asset, 1.0)])
    monkeypatch.setattr(runtime, "_build_selection_trace", lambda **kwargs: {"decision": kwargs["selection_mode"]})

    try:
        selected_asset, _, selection_mode, blend_assets = runtime._select_asset(user_row)
    finally:
        runtime._current_session = None

    assert selected_asset["asset_id"] == "asset-current"
    assert selection_mode == "hold"
    assert blend_assets == [(current_asset, 1.0)]


def test_select_asset_force_switches_when_angle_gap_reaches_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = build_runtime_stub()
    current_asset = {"asset_id": "asset-current", "pose_key": "pose-current", "yaw_1deg": 0, "pitch_1deg": 0, "roll_1deg": 0}
    best_asset = {"asset_id": "asset-best", "pose_key": "pose-best", "yaw_1deg": 10, "pitch_1deg": 0, "roll_1deg": 0}
    session = runtime._get_or_create_session("force-switch-angle")
    runtime._current_session = session
    runtime._selected_asset = current_asset
    runtime._blend_assets = [(current_asset, 1.0)]
    runtime._frames_since_switch = 1

    user_row = {
        "pose": {"yaw_1deg": 10, "pitch_1deg": 0, "roll_1deg": 0},
        "_motion": {"fast": False, "moderate": False},
    }

    monkeypatch.setattr(runtime, "_candidate_assets_for_user_row", lambda user_row: ([current_asset, best_asset], {"source": "test", "candidate_pool_size": 2}))
    monkeypatch.setattr("app.hairddae_runtime.select_best_assets", lambda user_row, candidate_assets, limit=10, candidate_limit=96: [(best_asset, 1.0), (current_asset, 4.0)])
    monkeypatch.setattr("app.hairddae_runtime.asset_rank_score", lambda user_row, asset_row: 4.0 if asset_row["asset_id"] == "asset-current" else 1.0)
    monkeypatch.setattr(runtime, "_prefer_side_band_candidate", lambda *args, **kwargs: (args[3], args[4], False))
    monkeypatch.setattr(runtime, "_prefer_pitch_band_candidate", lambda *args, **kwargs: (args[3], args[4], False))
    monkeypatch.setattr(runtime, "_prefer_frontal_safe_candidate", lambda *args, **kwargs: (args[2], args[3], False))
    monkeypatch.setattr(runtime, "_prefer_render_cost_candidate", lambda *args, **kwargs: (args[2], args[3], False))
    monkeypatch.setattr(runtime, "_prefer_render_safe_candidate", lambda *args, **kwargs: (args[2], args[3], False))
    monkeypatch.setattr(runtime, "_build_blend_assets", lambda user_row, ranked_assets, primary_asset, selection_mode: [(primary_asset, 1.0)])
    monkeypatch.setattr(runtime, "_build_selection_trace", lambda **kwargs: {"decision": kwargs["selection_mode"]})

    try:
        selected_asset, _, selection_mode, blend_assets = runtime._select_asset(user_row)
    finally:
        runtime._current_session = None

    assert selected_asset["asset_id"] == "asset-best"
    assert selection_mode == "switch"
    assert blend_assets == [(best_asset, 1.0)]


def test_select_asset_angle_priority_prepares_geom_before_scoring(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = build_runtime_stub()
    runtime.angle_priority_enabled = True
    current_asset = {"asset_id": "asset-current", "pose_key": "pose-current", "yaw_1deg": 0, "pitch_1deg": 0, "roll_1deg": 0}
    best_asset = {"asset_id": "asset-best", "pose_key": "pose-best", "yaw_1deg": 14, "pitch_1deg": 2, "roll_1deg": 0}

    user_row = {
        "pose": {"yaw_1deg": 14, "pitch_1deg": 2, "roll_1deg": 0},
        "_motion": {"fast": False, "moderate": False},
    }

    monkeypatch.setattr(
        runtime,
        "_angle_priority_candidate_assets_for_user_row",
        lambda row, *, limit, max_radius=12: ([current_asset, best_asset], {"source": "test", "candidate_pool_size": 2, "pose_radius": 0}),
    )
    monkeypatch.setattr("app.hairddae_runtime.derive_geom_from_feature", lambda row: {"temple_span_norm": 0.2, "lower_span_norm": 0.2, "crown_offset_norm": 0.2, "face_ratio": 0.4})
    monkeypatch.setattr("app.hairddae_runtime.asset_rank_score", lambda row, asset: 0.1 if row["_geom"]["face_ratio"] == 0.4 and asset["asset_id"] == "asset-best" else 1.0)
    monkeypatch.setattr(runtime, "_asset_crop_risk", lambda asset_row: 0.0)
    monkeypatch.setattr(runtime, "_prefer_side_band_candidate", lambda *args, **kwargs: (args[2], args[3], False))
    monkeypatch.setattr(runtime, "_prefer_pitch_band_candidate", lambda *args, **kwargs: (args[2], args[3], False))
    monkeypatch.setattr(runtime, "_prefer_frontal_safe_candidate", lambda *args, **kwargs: (args[2], args[3], False))
    monkeypatch.setattr(runtime, "_prefer_render_cost_candidate", lambda *args, **kwargs: (args[2], args[3], False))
    monkeypatch.setattr(runtime, "_prefer_render_safe_candidate", lambda *args, **kwargs: (args[2], args[3], False))
    monkeypatch.setattr(runtime, "_build_blend_assets", lambda row, ranked_assets, primary_asset, selection_mode: [(primary_asset, 1.0)])
    monkeypatch.setattr(runtime, "_build_selection_trace", lambda **kwargs: {"decision": kwargs["selection_mode"]})

    runtime._current_session = runtime._get_or_create_session("angle-priority-geom")
    try:
        selected_asset, _, selection_mode, blend_assets = runtime._select_asset(user_row)
    finally:
        runtime._current_session = None

    assert user_row["_geom"]["face_ratio"] == 0.4
    assert user_row["_best_score"] == 0.1
    assert selected_asset["asset_id"] == "asset-best"
    assert selection_mode == "initial"
    assert blend_assets == [(best_asset, 1.0)]


def test_select_asset_angle_priority_fallback_shortlist_keeps_late_pose_match(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = build_runtime_stub()
    runtime.angle_priority_enabled = True
    wrong_assets = [
        {
            "asset_id": f"wrong-{index}",
            "pose_key": f"wrong-{index}",
            "yaw_1deg": -29,
            "pitch_1deg": -15,
            "roll_1deg": 10,
        }
        for index in range(96)
    ]
    good_asset = {
        "asset_id": "good",
        "pose_key": "good",
        "yaw_1deg": -30,
        "pitch_1deg": 6,
        "roll_1deg": -8,
    }
    candidate_assets = wrong_assets + [good_asset]
    user_row = {
        "pose": {"yaw_1deg": -29, "pitch_1deg": 5, "roll_1deg": -7},
        "_motion": {"fast": False, "moderate": False},
    }

    runtime.assets = candidate_assets
    runtime.runtime_asset_count = len(candidate_assets)
    runtime._asset_pose_index = runtime._build_asset_pose_index(candidate_assets)
    monkeypatch.setattr(runtime, "_asset_bundle_integrity_error", lambda asset_row: None)
    monkeypatch.setattr("app.hairddae_runtime.derive_geom_from_feature", lambda row: {"temple_span_norm": 0.2, "lower_span_norm": 0.2, "crown_offset_norm": 0.2, "face_ratio": 0.4})
    monkeypatch.setattr("app.hairddae_runtime.asset_rank_score", lambda row, asset: 0.0)
    monkeypatch.setattr(runtime, "_asset_crop_risk", lambda asset_row: 0.0)
    monkeypatch.setattr(runtime, "_prefer_side_band_candidate", lambda *args, **kwargs: (args[2], args[3], False))
    monkeypatch.setattr(runtime, "_prefer_pitch_band_candidate", lambda *args, **kwargs: (args[2], args[3], False))
    monkeypatch.setattr(runtime, "_prefer_frontal_safe_candidate", lambda *args, **kwargs: (args[2], args[3], False))
    monkeypatch.setattr(runtime, "_prefer_render_cost_candidate", lambda *args, **kwargs: (args[2], args[3], False))
    monkeypatch.setattr(runtime, "_prefer_render_safe_candidate", lambda *args, **kwargs: (args[2], args[3], False))
    monkeypatch.setattr(runtime, "_build_blend_assets", lambda row, ranked_assets, primary_asset, selection_mode: [(primary_asset, 1.0)])
    monkeypatch.setattr(runtime, "_build_selection_trace", lambda **kwargs: {"decision": kwargs["selection_mode"]})

    runtime._current_session = runtime._get_or_create_session("angle-priority-shortlist")
    try:
        selected_asset, _, selection_mode, blend_assets = runtime._select_asset(user_row)
    finally:
        runtime._current_session = None

    assert selected_asset["asset_id"] == "good"
    assert selection_mode == "initial"
    assert blend_assets == [(good_asset, 1.0)]


def test_roll_gap_is_weighted_more_strongly_in_pose_ranking() -> None:
    user_row = {
        "pose": {"yaw_1deg": 0, "pitch_1deg": 0, "roll_1deg": 8},
        "_geom": {
            "temple_span_norm": 0.2,
            "lower_span_norm": 0.2,
            "crown_offset_norm": 0.2,
            "face_ratio": 0.2,
        },
    }
    exact_roll_asset = {
        "asset_id": "exact",
        "yaw_1deg": 0,
        "pitch_1deg": 0,
        "roll_1deg": 8,
        "temple_span_ratio": 0.2,
        "lower_span_ratio": 0.2,
        "crown_offset_ratio": 0.2,
        "face_ratio": 0.2,
        "quality_score": 0.0,
        "hair_mean_confidence": 0.0,
        "failure_tags": [],
        "naturalness_risk_v1": 0.0,
        "naturalness_failure_tags_v1": [],
        "face_overlap_ratio": 0.0,
        "quality_status": "approved",
        "approved_runtime": True,
        "approved": True,
        "ear_visibility_left": 0.0,
        "ear_visibility_right": 0.0,
        "forehead_visible_ratio": 0.0,
        "alpha_area_ratio": 0.0,
        "hair_height_ratio": 0.0,
    }
    wrong_roll_asset = dict(exact_roll_asset)
    wrong_roll_asset["asset_id"] = "wrong-roll"
    wrong_roll_asset["roll_1deg"] = -2

    assert pose_distance(user_row["pose"], exact_roll_asset) < pose_distance(user_row["pose"], wrong_roll_asset)
    assert asset_rank_score(user_row, exact_roll_asset) < asset_rank_score(user_row, wrong_roll_asset)


def test_process_frame_blacklists_broken_asset_and_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = build_runtime_stub()
    broken_asset = {"asset_id": "broken-a", "pose_key": "pose-a"}
    fallback_asset = {"asset_id": "fallback-b", "pose_key": "pose-b"}

    monkeypatch.setattr(runtime, "_set_active_renderer", lambda renderer_name: "mesh_v3")
    monkeypatch.setattr(runtime, "_is_face_tracking_outlier", lambda raw_user_row: False)
    monkeypatch.setattr(runtime, "_smooth_user_row", lambda user_row: dict(user_row))
    monkeypatch.setattr(
        runtime,
        "_parse_user_masks",
        lambda frame_bgr, user_row, renderer_name, prefer_latency=False: (None, "disabled", 0.0),
    )
    monkeypatch.setattr(runtime, "_attach_runtime_fit_context", lambda user_row, user_mask_bundle: user_row)
    monkeypatch.setattr(runtime, "_asset_bundle_integrity_error", lambda asset_row: None)

    def fake_select(user_row: dict[str, object], representative_asset_id: str | None = None):
        if "broken-a" in runtime._broken_asset_ids:
            runtime._last_selection_trace = {"decision": "fallback"}
            return fallback_asset, 1.5, "fallback", [(fallback_asset, 1.0)]
        runtime._last_selection_trace = {"decision": "initial"}
        return broken_asset, 1.0, "initial", [(broken_asset, 1.0)]

    def fake_compose(
        user_row: dict[str, object],
        frame_bgr: np.ndarray,
        blend_assets: list[tuple[dict[str, object], float]],
        renderer_name: str,
        user_mask_bundle: dict[str, object] | None,
        *,
        prefer_latency: bool,
        source_frame_bgr=None,
    ):
        asset_ids = [str(asset_row["asset_id"]) for asset_row, _ in blend_assets]
        if "broken-a" in asset_ids:
            raise FileNotFoundError("missing broken-a asset image")
        return np.full_like(frame_bgr, 77), 1.0, None, renderer_name, None

    monkeypatch.setattr(runtime, "_select_asset", fake_select)
    monkeypatch.setattr(runtime, "_compose_output_frame", fake_compose)

    result = runtime.process_frame(
        np.zeros((8, 8, 3), dtype=np.uint8),
        tracked_user_row={
            "ok": True,
            "pose": {"yaw_1deg": 0, "pitch_1deg": 0, "roll_1deg": 0},
            "face_bbox": {"x": 0.1, "y": 0.1, "w": 0.4, "h": 0.4},
        },
        session_id="runtime-fallback",
    )

    assert result["status"] == "ok"
    assert result["selected_asset_id"] == "fallback-b"
    assert result["selection_mode"] == "fallback"
    assert result["render_error"] is None
    assert np.array_equal(result["output_frame_bgr"], np.full((8, 8, 3), 77, dtype=np.uint8))
    assert "broken-a" in runtime._sessions["runtime-fallback"].broken_asset_ids
    assert result["selection_trace"]["render_fallback_used"] is True


def test_process_frame_returns_passthrough_when_all_candidates_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = build_runtime_stub()
    broken_asset = {"asset_id": "broken-a", "pose_key": "pose-a"}

    monkeypatch.setattr(runtime, "_set_active_renderer", lambda renderer_name: "mesh_v3")
    monkeypatch.setattr(runtime, "_is_face_tracking_outlier", lambda raw_user_row: False)
    monkeypatch.setattr(runtime, "_smooth_user_row", lambda user_row: dict(user_row))
    monkeypatch.setattr(
        runtime,
        "_parse_user_masks",
        lambda frame_bgr, user_row, renderer_name, prefer_latency=False: (None, "disabled", 0.0),
    )
    monkeypatch.setattr(runtime, "_attach_runtime_fit_context", lambda user_row, user_mask_bundle: user_row)
    monkeypatch.setattr(runtime, "_asset_bundle_integrity_error", lambda asset_row: None)
    monkeypatch.setattr(
        runtime,
        "_select_asset",
        lambda user_row, representative_asset_id=None: (
            runtime.__setattr__("_last_selection_trace", {"decision": "initial"}) or broken_asset,
            1.0,
            "initial",
            [(broken_asset, 1.0)],
        ),
    )
    monkeypatch.setattr(
        runtime,
        "_compose_output_frame",
        lambda user_row, frame_bgr, blend_assets, renderer_name, user_mask_bundle, *, prefer_latency, source_frame_bgr=None: (_ for _ in ()).throw(
            FileNotFoundError("missing broken-a asset image")
        ),
    )

    frame_bgr = np.full((8, 8, 3), 15, dtype=np.uint8)
    result = runtime.process_frame(
        frame_bgr,
        tracked_user_row={
            "ok": True,
            "pose": {"yaw_1deg": 0, "pitch_1deg": 0, "roll_1deg": 0},
            "face_bbox": {"x": 0.1, "y": 0.1, "w": 0.4, "h": 0.4},
        },
        session_id="runtime-overlay-error",
    )

    assert result["status"] == "overlay_error"
    assert result["selected_asset_id"] is None
    assert result["selection_mode"] == "overlay_error"
    assert result["render_error"] == "missing broken-a asset image"
    assert np.array_equal(result["output_frame_bgr"], frame_bgr)


def test_process_frame_can_skip_jpeg_encoding(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = build_runtime_stub()

    monkeypatch.setattr(runtime, "_set_active_renderer", lambda renderer_name: "mesh_v3")
    monkeypatch.setattr(runtime, "_is_face_tracking_outlier", lambda raw_user_row: False)
    monkeypatch.setattr(runtime, "_smooth_user_row", lambda user_row: dict(user_row))
    monkeypatch.setattr(
        runtime,
        "_parse_user_masks",
        lambda frame_bgr, user_row, renderer_name, prefer_latency=False: (None, "disabled", 0.0),
    )
    monkeypatch.setattr(runtime, "_attach_runtime_fit_context", lambda user_row, user_mask_bundle: user_row)
    monkeypatch.setattr(
        runtime,
        "_select_and_compose_output_frame",
        lambda **kwargs: {
            "output_frame": np.full((8, 8, 3), 77, dtype=np.uint8),
            "selected_asset_id": "asset-a",
            "selected_pose_key": "pose-a",
            "score": 1.0,
            "selection_mode": "stable",
            "blend_assets": [({"asset_id": "asset-a"}, 1.0)],
            "transition_progress": 0.0,
            "transition_from_asset_id": None,
            "selection_trace": {"decision": "stable"},
            "render_error": None,
            "status": "ok",
            "effective_renderer_name": "mesh_v3",
            "coverage_mask": None,
        },
    )
    monkeypatch.setattr(
        "app.hairddae_runtime.cv2.imencode",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("imencode should be skipped")),
    )

    result = runtime.process_frame(
        np.zeros((8, 8, 3), dtype=np.uint8),
        tracked_user_row={
            "ok": True,
            "pose": {"yaw_1deg": 0, "pitch_1deg": 0, "roll_1deg": 0},
            "face_bbox": {"x": 0.1, "y": 0.1, "w": 0.4, "h": 0.4},
        },
        session_id="runtime-no-jpeg",
        encode_output=False,
    )

    assert result["status"] == "ok"
    assert result["image_bytes"] is None
    assert np.array_equal(result["output_frame_bgr"], np.full((8, 8, 3), 77, dtype=np.uint8))


def test_parse_user_masks_skips_parser_in_forced_latency_mode() -> None:
    runtime = build_runtime_stub()
    runtime.disable_user_parsing_in_latency_mode = True
    runtime.user_parsing_ready = True

    class ParserStub:
        def parse_frame(self, frame_bgr: np.ndarray, user_row: dict[str, object]) -> dict[str, object]:
            raise AssertionError("parser should not be called in forced latency mode")

    runtime._user_parser = ParserStub()
    runtime._current_session = runtime._get_or_create_session("latency-skip")

    try:
        user_mask_bundle, status, latency_ms = runtime._parse_user_masks(
            np.zeros((8, 8, 3), dtype=np.uint8),
            {
                "candidate_face_count": 1,
                "pose": {"yaw_1deg": 12, "pitch_1deg": 0, "roll_1deg": 0},
                "face_bbox": {"x": 1, "y": 1, "w": 4, "h": 4},
            },
            "mesh_v3",
            prefer_latency=True,
        )
    finally:
        runtime._current_session = None

    assert user_mask_bundle is None
    assert status == "latency_skip"
    assert latency_ms == 0.0


def test_parse_user_masks_reuses_stable_mask_in_forced_latency_mode() -> None:
    runtime = build_runtime_stub()
    runtime.disable_user_parsing_in_latency_mode = True
    runtime.user_parsing_ready = True

    class ParserStub:
        def parse_frame(self, frame_bgr: np.ndarray, user_row: dict[str, object]) -> dict[str, object]:
            raise AssertionError("parser should not be called when stable mask is reused")

    runtime._user_parser = ParserStub()
    runtime._current_session = runtime._get_or_create_session("latency-reuse")
    runtime._stable_user_mask_bundle = {"metrics": {"face_bbox": {"x": 1, "y": 1, "w": 4, "h": 4}}}
    runtime._stable_user_mask_row = {
        "face_bbox": {"x": 1, "y": 1, "w": 4, "h": 4},
    }

    try:
        user_mask_bundle, status, latency_ms = runtime._parse_user_masks(
            np.zeros((8, 8, 3), dtype=np.uint8),
            {
                "candidate_face_count": 1,
                "pose": {"yaw_1deg": 15, "pitch_1deg": 0, "roll_1deg": 0},
                "face_bbox": {"x": 1, "y": 1, "w": 4, "h": 4},
            },
            "mesh_v3",
            prefer_latency=True,
        )
    finally:
        runtime._current_session = None

    assert user_mask_bundle == {"metrics": {"face_bbox": {"x": 1, "y": 1, "w": 4, "h": 4}}}
    assert status == "reuse_stable_mask_forced_latency"
    assert latency_ms == 0.0


def test_candidate_assets_for_user_row_prefers_pose_index(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = build_runtime_stub()
    runtime.assets = [
        {"asset_id": f"near-{index:02d}", "yaw_1deg": index % 2, "pitch_1deg": 0, "roll_1deg": 0}
        for index in range(20)
    ]
    runtime.assets.append({"asset_id": "far-c", "yaw_1deg": 18, "pitch_1deg": 9, "roll_1deg": 4})
    runtime._asset_pose_index = runtime._build_asset_pose_index(runtime.assets)
    runtime.runtime_asset_count = len(runtime.assets)
    runtime._current_session = runtime._get_or_create_session("pose-index")
    runtime._current_session.broken_asset_ids.add("near-00")
    monkeypatch.setattr(runtime, "_asset_bundle_integrity_error", lambda asset_row: None)

    try:
        candidates, metrics = runtime._candidate_assets_for_user_row(
            {
                "pose": {"yaw_1deg": 0, "pitch_1deg": 0, "roll_1deg": 0},
            }
        )
    finally:
        runtime._current_session = None

    assert metrics["source"] == "pose_index"
    assert metrics["runtime_asset_count"] == 21
    assert metrics["candidate_pool_size"] >= 8
    assert "near-00" not in [asset_row["asset_id"] for asset_row in candidates]
    assert "far-c" not in [asset_row["asset_id"] for asset_row in candidates]


def test_build_selection_trace_includes_candidate_metrics() -> None:
    runtime = build_runtime_stub()
    asset = {
        "asset_id": "asset-a",
        "pose_key": "pose-a",
        "quality_status": "approved",
        "approved": True,
        "approved_runtime": True,
        "approved_strict": False,
        "quality_score": 1.2,
        "naturalness_risk_v1": 0.01,
        "face_overlap_ratio": 0.0,
        "failure_tags": [],
        "naturalness_failure_tags_v1": [],
        "yaw_1deg": 0,
        "pitch_1deg": 0,
        "roll_1deg": 0,
    }

    trace = runtime._build_selection_trace(
        user_row={"pose": {"yaw_1deg": 0, "pitch_1deg": 0, "roll_1deg": 0}},
        ranked_assets=[(asset, 1.25)],
        selected_asset=asset,
        selected_score=1.25,
        selection_mode="initial",
        blend_assets=[(asset, 1.0)],
        candidate_metrics={"source": "pose_index", "candidate_pool_size": 24},
        selection_latency_ms=3.75,
    )

    assert trace["candidate_metrics"]["source"] == "pose_index"
    assert trace["candidate_metrics"]["candidate_pool_size"] == 24
    assert trace["selection_latency_ms"] == 3.75


def test_asset_bundle_integrity_error_skips_image_decode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = build_runtime_stub()
    runtime.asset_root = tmp_path

    metadata_path = tmp_path / "metadata.json"
    anchors_path = tmp_path / "anchors.json"
    hair_rgba_path = tmp_path / "hair_rgba.png"
    hair_mask_path = tmp_path / "hair_mask.png"
    face_mask_path = tmp_path / "face_mask.png"
    forehead_mask_path = tmp_path / "forehead_mask.png"
    ear_left_path = tmp_path / "ear_left.png"
    ear_right_path = tmp_path / "ear_right.png"
    neck_path = tmp_path / "neck.png"
    protect_path = tmp_path / "protect.png"

    metadata_path.write_text(
        json.dumps(
            {
                "anchors_path": anchors_path.name,
                "hair_rgba_path": hair_rgba_path.name,
                "hair_mask_path": hair_mask_path.name,
                "face_mask_path": face_mask_path.name,
                "forehead_mask_path": forehead_mask_path.name,
                "ear_mask_left_path": ear_left_path.name,
                "ear_mask_right_path": ear_right_path.name,
                "neck_shoulder_mask_path": neck_path.name,
                "protect_face_mask_path": protect_path.name,
            }
        ),
        encoding="utf-8",
    )
    anchors_path.write_text(json.dumps({"anchors": {}}), encoding="utf-8")
    for path in (hair_rgba_path, hair_mask_path, face_mask_path, forehead_mask_path, ear_left_path, ear_right_path, neck_path, protect_path):
        path.write_bytes(b"x")

    asset_row = {"asset_id": "asset-a", "metadata_path": metadata_path.name}
    monkeypatch.setattr(
        "app.hairddae_runtime.cv2.imread",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("decode should not run")),
    )

    assert runtime._asset_bundle_integrity_error(asset_row) is None


def test_asset_crop_risk_uses_metadata_only() -> None:
    runtime = build_runtime_stub()
    asset_row = {
        "asset_id": "asset-a",
        "image_size": {"width": 1000, "height": 1000},
        "hair_rgba_bbox": {"x": 40, "y": 20, "w": 360, "h": 380},
        "alpha_area_ratio": 0.081,
        "hair_area_ratio": 0.074,
        "boundary_touches": {"top": True, "bottom": False, "left": False, "right": True},
        "face_overlap_ratio": 0.012,
        "naturalness_risk_v1": 0.05,
        "mask_component_count": 2,
        "hole_ratio": 0.01,
        "fringe_fill_ratio": 0.55,
        "naturalness_failure_tags_v1": ["face_skin_overlap_risk"],
    }

    risk_score = runtime._asset_crop_risk(asset_row)

    assert risk_score > 0.25
    assert asset_row["_crop_edge_risk"] == round(risk_score, 6)


def test_build_blend_assets_disables_blend_for_large_render_cost() -> None:
    runtime = build_runtime_stub()
    runtime._current_session = runtime._get_or_create_session("blend-cost")
    primary_asset = {
        "asset_id": "asset-a",
        "yaw_1deg": 0,
        "pitch_1deg": 0,
        "roll_1deg": 0,
        "image_size": {"width": 1000, "height": 1000},
        "hair_rgba_bbox": {"x": 0, "y": 0, "w": 360, "h": 360},
        "alpha_area_ratio": 0.09,
        "hair_area_ratio": 0.08,
    }
    neighbor_asset = {
        "asset_id": "asset-b",
        "yaw_1deg": 1,
        "pitch_1deg": 0,
        "roll_1deg": 0,
        "image_size": {"width": 1000, "height": 1000},
        "hair_rgba_bbox": {"x": 0, "y": 0, "w": 220, "h": 220},
        "alpha_area_ratio": 0.03,
        "hair_area_ratio": 0.03,
    }

    try:
        weighted_assets = runtime._build_blend_assets(
            {"pose": {"yaw_1deg": 0, "pitch_1deg": 0, "roll_1deg": 0}, "_motion": {"fast": False}},
            [(primary_asset, 1.0), (neighbor_asset, 1.5)],
            primary_asset,
            "stable",
        )
    finally:
        runtime._current_session = None

    assert weighted_assets == [(primary_asset, 1.0)]


def test_build_blend_assets_disables_blend_in_lightweight_overlay_mode() -> None:
    runtime = build_runtime_stub()
    runtime.lightweight_overlay_only = True
    primary_asset = {
        "asset_id": "asset-a",
        "yaw_1deg": 0,
        "pitch_1deg": 0,
        "roll_1deg": 0,
    }
    neighbor_asset = {
        "asset_id": "asset-b",
        "yaw_1deg": 1,
        "pitch_1deg": 0,
        "roll_1deg": 0,
    }

    weighted_assets = runtime._build_blend_assets(
        {"pose": {"yaw_1deg": 0, "pitch_1deg": 0, "roll_1deg": 0}, "_motion": {"fast": False}},
        [(primary_asset, 1.0), (neighbor_asset, 1.5)],
        primary_asset,
        "stable",
    )

    assert weighted_assets == [(primary_asset, 1.0)]


def test_resolve_compose_mode_prefers_bundle_render_for_large_latency_asset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = build_runtime_stub()
    asset = {
        "asset_id": "asset-a",
        "image_size": {"width": 1000, "height": 1000},
        "hair_rgba_bbox": {"x": 0, "y": 0, "w": 360, "h": 360},
        "alpha_area_ratio": 0.09,
        "hair_area_ratio": 0.08,
    }
    monkeypatch.setattr(
        runtime,
        "_bundle_render_entry_for_asset",
        lambda asset_row, **kwargs: RuntimeBundleRenderEntry(
            asset_id=str(asset_row["asset_id"]),
            metadata={},
            anchors_payload={},
            hair_rgba_path=Path("hair.png"),
            hair_bbox={"x": 0, "y": 0, "w": 10, "h": 10},
        ),
    )

    assert runtime._resolve_compose_mode(
        {"pose": {"yaw_1deg": 0, "pitch_1deg": 0, "roll_1deg": 0}},
        "mesh_v3",
        [(asset, 1.0)],
        prefer_latency=True,
    ) == "bundle_render"
    assert runtime._resolve_compose_mode(
        {"pose": {"yaw_1deg": 0, "pitch_1deg": 0, "roll_1deg": 0}},
        "mesh_v3",
        [(asset, 1.0)],
        prefer_latency=False,
    ) == "overlay"


def test_resolve_compose_mode_forces_bundle_render_when_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = build_runtime_stub()
    asset = {
        "asset_id": "asset-a",
        "image_size": {"width": 1000, "height": 1000},
        "hair_rgba_bbox": {"x": 0, "y": 0, "w": 120, "h": 120},
        "alpha_area_ratio": 0.01,
        "hair_area_ratio": 0.01,
    }
    monkeypatch.setattr(
        runtime,
        "_bundle_render_entry_for_asset",
        lambda asset_row, **kwargs: RuntimeBundleRenderEntry(
            asset_id=str(asset_row["asset_id"]),
            metadata={},
            anchors_payload={},
            hair_rgba_path=Path("hair.png"),
            hair_bbox={"x": 0, "y": 0, "w": 10, "h": 10},
        ),
    )

    assert runtime._resolve_compose_mode(
        {"_force_bundle_render": True, "pose": {"yaw_1deg": 0, "pitch_1deg": 0, "roll_1deg": 0}},
        "mesh_v3",
        [(asset, 1.0)],
        prefer_latency=False,
    ) == "bundle_render"


def test_resolve_compose_mode_forces_overlay_when_lightweight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = build_runtime_stub()
    runtime.lightweight_overlay_only = True
    asset = {
        "asset_id": "asset-a",
        "image_size": {"width": 1000, "height": 1000},
        "hair_rgba_bbox": {"x": 0, "y": 0, "w": 360, "h": 360},
        "alpha_area_ratio": 0.09,
        "hair_area_ratio": 0.08,
    }
    monkeypatch.setattr(
        runtime,
        "_bundle_render_entry_for_asset",
        lambda asset_row, **kwargs: RuntimeBundleRenderEntry(
            asset_id=str(asset_row["asset_id"]),
            metadata={},
            anchors_payload={},
            hair_rgba_path=Path("hair.png"),
            hair_bbox={"x": 0, "y": 0, "w": 10, "h": 10},
        ),
    )

    assert runtime._resolve_compose_mode(
        {"_force_bundle_render": True, "pose": {"yaw_1deg": 0, "pitch_1deg": 0, "roll_1deg": 0}},
        "mesh_v3",
        [(asset, 1.0)],
        prefer_latency=True,
    ) == "overlay"


def test_set_active_renderer_forces_lightweight_renderer() -> None:
    runtime = build_runtime_stub()
    runtime.lightweight_overlay_only = True
    runtime.available_renderers = ["mesh_v2", "mesh_v3"]
    runtime._current_session = runtime._get_or_create_session("lightweight-renderer")

    try:
        assert runtime._set_active_renderer("mesh_v3") == "mesh_v2"
        assert runtime._active_renderer_name == "mesh_v2"
    finally:
        runtime._current_session = None


def test_compose_output_frame_uses_bundle_render_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = build_runtime_stub()
    frame = np.zeros((8, 8, 3), dtype=np.uint8)
    asset = {"asset_id": "asset-a"}
    monkeypatch.setattr(runtime, "_resolve_compose_mode", lambda *args, **kwargs: "bundle_render")
    monkeypatch.setattr(
        runtime,
        "_compose_bundle_output_frame",
        lambda user_row, frame_bgr, source_frame_bgr, blend_assets, *, prefer_latency: (
            np.full_like(frame_bgr, 33),
            1.0,
            None,
            "bundle_render",
            None,
        ),
    )
    monkeypatch.setattr(
        runtime,
        "_resolve_compose_renderer",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("overlay renderer should not be used")),
    )

    output_frame, transition_progress, transition_from_asset_id, effective_renderer_name, coverage_mask = runtime._compose_output_frame(
        {"pose": {"yaw_1deg": 0, "pitch_1deg": 0, "roll_1deg": 0}},
        frame,
        [(asset, 1.0)],
        "mesh_v3",
        None,
        prefer_latency=True,
    )

    assert np.array_equal(output_frame, np.full((8, 8, 3), 33, dtype=np.uint8))
    assert transition_progress == 1.0
    assert transition_from_asset_id is None
    assert effective_renderer_name == "bundle_render"
    assert coverage_mask is None


def test_compose_output_frame_drops_transition_when_lightweight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = build_runtime_stub()
    runtime.lightweight_overlay_only = True
    runtime.available_renderers = ["mesh_v2", "mesh_v3"]
    runtime._current_session = runtime._get_or_create_session("lightweight-compose")
    runtime._transition = {
        "from_blend_assets": [({"asset_id": "from-asset"}, 1.0)],
        "from_asset_id": "from-asset",
        "step": 0,
        "steps": 2,
    }
    frame = np.zeros((8, 8, 3), dtype=np.uint8)
    asset = {"asset_id": "asset-a"}
    monkeypatch.setattr(runtime, "_resolve_compose_mode", lambda *args, **kwargs: "overlay")
    monkeypatch.setattr(runtime, "_resolve_compose_renderer", lambda *args, **kwargs: "mesh_v2")
    monkeypatch.setattr(
        "app.hairddae_runtime.compose_overlay_blend_frame",
        lambda *args, **kwargs: np.full_like(frame, 21),
    )
    monkeypatch.setattr(
        "app.hairddae_runtime.compose_overlay_transition_frames",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("transition path should not be used")),
    )

    try:
        output_frame, transition_progress, transition_from_asset_id, effective_renderer_name, coverage_mask = runtime._compose_output_frame(
            {"pose": {"yaw_1deg": 0, "pitch_1deg": 0, "roll_1deg": 0}},
            frame,
            [(asset, 1.0)],
            "mesh_v3",
            None,
            prefer_latency=True,
        )
    finally:
        runtime._current_session = None

    assert np.array_equal(output_frame, np.full((8, 8, 3), 21, dtype=np.uint8))
    assert transition_progress == 1.0
    assert transition_from_asset_id is None
    assert effective_renderer_name == "mesh_v2"
    assert coverage_mask is None


def test_compose_output_frame_returns_overlay_coverage_mask(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = build_runtime_stub()
    runtime._current_session = runtime._get_or_create_session("overlay-coverage")
    runtime._last_selection_trace = {"compose_detail_ms": {}}
    frame = np.zeros((8, 8, 3), dtype=np.uint8)
    asset = {"asset_id": "asset-a"}
    expected_coverage = np.zeros((8, 8), dtype=np.uint8)
    expected_coverage[2:6, 2:6] = 255

    monkeypatch.setattr(runtime, "_resolve_compose_mode", lambda *args, **kwargs: "overlay")
    monkeypatch.setattr(runtime, "_resolve_compose_renderer", lambda *args, **kwargs: "legacy")

    def fake_compose_overlay_blend_frame(*args, **kwargs):
        debug_payload = kwargs.get("debug_payload")
        if isinstance(debug_payload, dict):
            debug_payload["_coverage_mask"] = expected_coverage
            debug_payload["blend_path"] = "single_asset_fast"
        return np.full_like(frame, 24)

    monkeypatch.setattr(
        "app.hairddae_runtime.compose_overlay_blend_frame",
        fake_compose_overlay_blend_frame,
    )

    output_frame, transition_progress, transition_from_asset_id, effective_renderer_name, coverage_mask = runtime._compose_output_frame(
        {"pose": {"yaw_1deg": 0, "pitch_1deg": 0, "roll_1deg": 0}},
        frame,
        [(asset, 1.0)],
        "legacy",
        None,
        prefer_latency=True,
    )

    assert np.array_equal(output_frame, np.full((8, 8, 3), 24, dtype=np.uint8))
    assert transition_progress == 1.0
    assert transition_from_asset_id is None
    assert effective_renderer_name == "legacy"
    assert np.array_equal(coverage_mask, expected_coverage)
    assert "_coverage_mask" not in runtime._last_selection_trace["compose_detail_ms"]["overlay_blend_detail_ms"]


def test_compose_single_bundle_render_frame_passes_tone_gain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = build_runtime_stub()
    captured: dict[str, object] = {
        "rgb_gain": None,
        "original_frame_image": None,
        "skin_replacement_color_rgb": None,
    }

    monkeypatch.setattr(
        runtime,
        "_bundle_render_entry_for_asset",
        lambda asset_row, **kwargs: RuntimeBundleRenderEntry(
            asset_id="asset-a",
            metadata={},
            anchors_payload={},
            hair_rgba_path=Path("hair.png"),
            hair_bbox={"x": 0, "y": 0, "w": 4, "h": 4},
            hair_luma=54.0,
        ),
    )
    monkeypatch.setattr(runtime, "_feature_message_from_user_row", lambda user_row: object())

    class RenderTaskStub:
        def to_message(self) -> dict[str, object]:
            return {
                "destination_roi": {"x": 0, "y": 0, "w": 4, "h": 4},
                "matrix": {"a": 1.0, "b": 0.0, "c": 0.0, "d": 1.0, "e": 0.0, "f": 0.0},
            }

    monkeypatch.setattr("app.hairddae_runtime.build_render_task", lambda **kwargs: RenderTaskStub())

    def fake_compose_bundle_frame(frame_image, bundle, *, rgb_gain=None, **kwargs):
        captured["rgb_gain"] = rgb_gain
        captured["original_frame_image"] = kwargs.get("original_frame_image")
        captured["skin_replacement_color_rgb"] = kwargs.get("skin_replacement_color_rgb")
        debug_payload = kwargs.get("debug_payload")
        if isinstance(debug_payload, dict):
            debug_payload["timings_ms"] = {"total_ms": 6.5, "rgba_load_ms": 1.25}
        return frame_image

    monkeypatch.setattr("app.hairddae_runtime.compose_bundle_frame", fake_compose_bundle_frame)

    frame = np.full((8, 8, 3), 28, dtype=np.uint8)
    compose_debug: dict[str, object] = {}
    output, coverage_mask = runtime._compose_single_bundle_render_frame(
        {
            "image_size": {"width": 8, "height": 8},
            "pose": {"yaw_1deg": 0, "pitch_1deg": 0, "roll_1deg": 0},
            "face_bbox": {"x": 0.1, "y": 0.1, "w": 0.4, "h": 0.4},
            "anchors": {},
            "_hair_tone": {"mean_luma": 86.0, "coverage": 0.12},
            "_hair_scalp_color": np.array([90.0, 130.0, 170.0], dtype=np.float32),
        },
        frame,
        {"asset_id": "asset-a"},
        source_frame_bgr=np.full_like(frame, 16),
        debug_payload=compose_debug,
    )

    assert np.array_equal(output, frame)
    assert coverage_mask is None
    assert captured["rgb_gain"] is not None
    assert float(captured["rgb_gain"]) > 1.0
    assert captured["original_frame_image"] is not None
    assert compose_debug["bundle_frame_detail_ms"]["total_ms"] == 6.5
    assert compose_debug["bundle_frame_detail_ms"]["rgba_load_ms"] == 1.25
    assert np.array_equal(
        np.asarray(captured["skin_replacement_color_rgb"]),
        np.array([170.0, 130.0, 90.0], dtype=np.float32),
    )


def test_process_frame_returns_overlay_and_compose_details(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = build_runtime_stub()
    asset = {"asset_id": "asset-a", "pose_key": "pose-a"}

    monkeypatch.setattr(runtime, "_set_active_renderer", lambda renderer_name: "mesh_v3")
    monkeypatch.setattr(runtime, "_is_face_tracking_outlier", lambda raw_user_row: False)
    monkeypatch.setattr(runtime, "_smooth_user_row", lambda user_row: dict(user_row))
    monkeypatch.setattr(
        runtime,
        "_parse_user_masks",
        lambda frame_bgr, user_row, renderer_name, prefer_latency=False: (None, "disabled", 0.0),
    )
    monkeypatch.setattr(runtime, "_attach_runtime_fit_context", lambda user_row, user_mask_bundle: user_row)
    monkeypatch.setattr(
        runtime,
        "_select_asset",
        lambda user_row, representative_asset_id=None: (
            runtime.__setattr__("_last_selection_trace", {"decision": "initial"}) or asset,
            1.0,
            "initial",
            [(asset, 1.0)],
        ),
    )

    def fake_compose(
        user_row: dict[str, object],
        frame_bgr: np.ndarray,
        blend_assets: list[tuple[dict[str, object], float]],
        renderer_name: str,
        user_mask_bundle: dict[str, object] | None,
        *,
        prefer_latency: bool,
        source_frame_bgr=None,
    ):
        runtime._merge_selection_trace_fields(
            compose_detail_ms={"compose_mode": "overlay", "overlay_blend_ms": 3.2}
        )
        return np.full_like(frame_bgr, 77), 1.0, None, renderer_name, None

    monkeypatch.setattr(runtime, "_compose_output_frame", fake_compose)

    result = runtime.process_frame(
        np.zeros((8, 8, 3), dtype=np.uint8),
        tracked_user_row={
            "ok": True,
            "pose": {"yaw_1deg": 0, "pitch_1deg": 0, "roll_1deg": 0},
            "face_bbox": {"x": 0.1, "y": 0.1, "w": 0.4, "h": 0.4},
        },
        session_id="runtime-detail",
    )

    assert result["overlay_detail_ms"] is not None
    assert "smooth_ms" in result["overlay_detail_ms"]
    assert "select_and_compose_ms" in result["overlay_detail_ms"]
    assert "overlay_total_ms" in result["overlay_detail_ms"]
    assert result["compose_detail_ms"]["compose_mode"] == "overlay"
    assert result["selection_trace"]["overlay_detail_ms"]["overlay_total_ms"] == result["overlay_detail_ms"]["overlay_total_ms"]


def test_apply_overlay_postprocess_ignores_when_coverage_consumes_all_residual() -> None:
    runtime = build_runtime_stub()
    output = np.full((6, 6, 3), 40, dtype=np.uint8)
    base = np.full((6, 6, 3), 30, dtype=np.uint8)
    coverage = np.zeros((6, 6), dtype=np.uint8)
    coverage[1:5, 1:5] = 255
    hair_mask = np.zeros((6, 6), dtype=np.uint8)
    hair_mask[1:5, 1:5] = 255

    postprocessed = runtime._apply_overlay_postprocess(
        output,
        base,
        {
            "_hair_binary_mask": hair_mask,
            "_hair_fringe_mask": np.zeros((6, 6), dtype=np.uint8),
            "_hair_background_color": np.array([200.0, 180.0, 160.0], dtype=np.float32),
        },
        renderer_name="bundle_render",
        coverage_mask=coverage,
    )

    assert np.array_equal(postprocessed, output)


def test_apply_overlay_postprocess_skips_when_coverage_mask_missing() -> None:
    runtime = build_runtime_stub()
    output = np.full((8, 8, 3), 50, dtype=np.uint8)
    base = np.full((8, 8, 3), 30, dtype=np.uint8)
    base[:, :4] = np.array([220, 210, 200], dtype=np.uint8)
    hair_mask = np.zeros((8, 8), dtype=np.uint8)
    hair_mask[1:7, 1:7] = 255
    fringe_mask = np.zeros((8, 8), dtype=np.uint8)
    fringe_mask[1:4, 2:6] = 255

    postprocessed = runtime._apply_overlay_postprocess(
        output,
        base,
        {
            "_hair_binary_mask": hair_mask,
            "_hair_fringe_mask": fringe_mask,
            "_hair_background_color": np.array([220.0, 210.0, 200.0], dtype=np.float32),
        },
        renderer_name="legacy",
        coverage_mask=None,
    )

    assert np.array_equal(postprocessed, output)


def test_apply_overlay_postprocess_backgroundizes_segmentation_minus_fringe_using_local_background() -> None:
    runtime = build_runtime_stub()
    output = np.full((8, 8, 3), 50, dtype=np.uint8)
    base = np.full((8, 8, 3), 30, dtype=np.uint8)
    base[:, :4] = np.array([220, 210, 200], dtype=np.uint8)
    base[:, 4:] = np.array([120, 150, 220], dtype=np.uint8)
    coverage = np.zeros((8, 8), dtype=np.uint8)
    coverage[1:4, 2:6] = 255
    hair_mask = np.zeros((8, 8), dtype=np.uint8)
    hair_mask[1:7, 1:7] = 255
    fringe_mask = np.zeros((8, 8), dtype=np.uint8)
    fringe_mask[1:4, 2:6] = 255

    postprocessed = runtime._apply_overlay_postprocess(
        output,
        base,
        {
            "_hair_binary_mask": hair_mask,
            "_hair_fringe_mask": fringe_mask,
            "_hair_background_color": np.array([220.0, 210.0, 200.0], dtype=np.float32),
        },
        renderer_name="bundle_render",
        coverage_mask=coverage,
    )

    left_region = postprocessed[4:7, 1:3].astype(np.float32).mean(axis=(0, 1))
    right_region = postprocessed[4:7, 5:7].astype(np.float32).mean(axis=(0, 1))
    left_bg = base[4:7, 1:3].astype(np.float32).mean(axis=(0, 1))
    right_bg = base[4:7, 5:7].astype(np.float32).mean(axis=(0, 1))

    assert float(np.abs(left_region - left_bg).mean()) < float(np.abs(left_region - right_bg).mean())
    assert float(np.abs(right_region - right_bg).mean()) < float(np.abs(right_region - left_bg).mean())


def test_apply_overlay_postprocess_preserves_fringe_region() -> None:
    runtime = build_runtime_stub()
    output = np.full((8, 8, 3), 50, dtype=np.uint8)
    base = np.full((8, 8, 3), 30, dtype=np.uint8)
    coverage = np.zeros((8, 8), dtype=np.uint8)
    coverage[1:4, 2:6] = 255
    hair_mask = np.zeros((8, 8), dtype=np.uint8)
    hair_mask[1:7, 1:7] = 255
    fringe_mask = np.zeros((8, 8), dtype=np.uint8)
    fringe_mask[1:4, 2:6] = 255

    postprocessed = runtime._apply_overlay_postprocess(
        output,
        base,
        {
            "_hair_binary_mask": hair_mask,
            "_hair_fringe_mask": fringe_mask,
            "_hair_background_color": np.array([220.0, 210.0, 200.0], dtype=np.float32),
        },
        renderer_name="bundle_render",
        coverage_mask=coverage,
    )

    assert np.array_equal(postprocessed[1:4, 2:6], output[1:4, 2:6])


def test_apply_overlay_postprocess_preserves_face_protect_region() -> None:
    runtime = build_runtime_stub()
    output = np.full((8, 8, 3), 50, dtype=np.uint8)
    base = np.full((8, 8, 3), 30, dtype=np.uint8)
    coverage = np.zeros((8, 8), dtype=np.uint8)
    coverage[1:4, 2:6] = 255
    hair_mask = np.zeros((8, 8), dtype=np.uint8)
    hair_mask[1:7, 1:7] = 255
    fringe_mask = np.zeros((8, 8), dtype=np.uint8)
    fringe_mask[1:4, 2:6] = 255
    face_protect = np.zeros((8, 8), dtype=np.uint8)
    face_protect[4:7, 1:3] = 255

    postprocessed = runtime._apply_overlay_postprocess(
        output,
        base,
        {
            "_hair_binary_mask": hair_mask,
            "_hair_fringe_mask": fringe_mask,
            "_hair_face_protect_mask": face_protect,
            "_hair_background_color": np.array([220.0, 210.0, 200.0], dtype=np.float32),
        },
        renderer_name="bundle_render",
        coverage_mask=coverage,
    )

    assert np.array_equal(postprocessed[4:7, 1:3], output[4:7, 1:3])
    assert not np.array_equal(postprocessed[4:7, 5:7], output[4:7, 5:7])


def test_apply_overlay_postprocess_uses_clothing_color_below_shoulder() -> None:
    runtime = build_runtime_stub()
    output = np.full((24, 24, 3), 50, dtype=np.uint8)
    base = np.full((24, 24, 3), np.array([220, 210, 200], dtype=np.uint8), dtype=np.uint8)
    base[16:24, :12] = np.array([30, 40, 230], dtype=np.uint8)
    base[16:24, 12:] = np.array([20, 170, 80], dtype=np.uint8)
    hair_mask = np.zeros((24, 24), dtype=np.uint8)
    hair_mask[2:8, 5:19] = 255
    hair_mask[7:23, 4:9] = 255
    hair_mask[7:23, 15:20] = 255
    coverage = np.zeros((24, 24), dtype=np.uint8)
    coverage[2:10, 8:16] = 255
    user_row = {
        "_hair_binary_mask": hair_mask,
        "_hair_background_color": np.array([220.0, 210.0, 200.0], dtype=np.float32),
        "face_bbox": {"x": 7, "y": 4, "w": 10, "h": 10},
        "anchors": {
            "left_temple": {"x": 8.0, "y": 6.0},
            "right_temple": {"x": 16.0, "y": 6.0},
            "left_ear_root": {"x": 7.0, "y": 14.0},
            "right_ear_root": {"x": 17.0, "y": 14.0},
            "forehead_center": {"x": 12.0, "y": 5.0},
            "crown": {"x": 12.0, "y": 3.0},
            "lower_left": {"x": 9.0, "y": 13.0},
            "lower_right": {"x": 15.0, "y": 13.0},
            "neck_left": {"x": 9.0, "y": 15.0},
            "neck_right": {"x": 15.0, "y": 15.0},
        },
    }

    postprocessed = runtime._apply_overlay_postprocess(
        output,
        base,
        user_row,
        renderer_name="bundle_render",
        coverage_mask=coverage,
    )

    lower_left_region = postprocessed[19:23, 4:9].astype(np.float32).mean(axis=(0, 1))
    lower_right_region = postprocessed[19:23, 15:20].astype(np.float32).mean(axis=(0, 1))
    left_shirt_region = base[19:23, 4:9].astype(np.float32).mean(axis=(0, 1))
    right_shirt_region = base[19:23, 15:20].astype(np.float32).mean(axis=(0, 1))
    background_region = base[2:6, 0:4].astype(np.float32).mean(axis=(0, 1))
    upper_region = postprocessed[4:8, 4:9].astype(np.float32).mean(axis=(0, 1))

    assert float(np.abs(lower_left_region - left_shirt_region).mean()) < float(np.abs(lower_left_region - background_region).mean())
    assert float(np.abs(lower_right_region - right_shirt_region).mean()) < float(np.abs(lower_right_region - background_region).mean())
    assert float(np.abs(lower_left_region - left_shirt_region).mean()) < float(np.abs(lower_left_region - right_shirt_region).mean())
    assert float(np.abs(lower_right_region - right_shirt_region).mean()) < float(np.abs(lower_right_region - left_shirt_region).mean())
    mixed_shirt_region = ((left_shirt_region + right_shirt_region) * 0.5).astype(np.float32)
    assert float(np.abs(upper_region - background_region).mean()) <= float(np.abs(upper_region - mixed_shirt_region).mean())


def test_prepare_clothing_cleanup_context_builds_geometry_envelope_without_body_mask() -> None:
    frame = np.full((32, 32, 3), 180, dtype=np.uint8)
    hair_mask = np.zeros((32, 32), dtype=np.uint8)
    hair_mask[18:30, 10:22] = 255
    user_row = {
        "face_bbox": {"x": 8, "y": 4, "w": 14, "h": 14},
        "anchors": {
            "lower_left": {"x": 11.0, "y": 17.0},
            "lower_right": {"x": 19.0, "y": 17.0},
            "neck_left": {"x": 11.0, "y": 19.0},
            "neck_right": {"x": 19.0, "y": 19.0},
        },
    }

    payload = overlay_postprocess_pipeline.prepare_clothing_cleanup_context(
        frame,
        user_row,
        hair_mask=hair_mask,
        body_mask=None,
    )

    clothing_mask = payload.get("_body_clothing_mask")
    assert isinstance(clothing_mask, np.ndarray)
    assert int(np.count_nonzero(clothing_mask)) > 0

    center_top = int(np.flatnonzero(clothing_mask[:, 16] > 0)[0])
    left_top = int(np.flatnonzero(clothing_mask[:, 8] > 0)[0])
    right_top = int(np.flatnonzero(clothing_mask[:, 24] > 0)[0])
    assert center_top >= left_top
    assert center_top >= right_top


def test_prepare_clothing_cleanup_context_skips_when_hair_does_not_reach_clothing_region() -> None:
    frame = np.full((32, 32, 3), 180, dtype=np.uint8)
    hair_mask = np.zeros((32, 32), dtype=np.uint8)
    hair_mask[2:10, 10:22] = 255
    user_row = {
        "face_bbox": {"x": 8, "y": 4, "w": 14, "h": 14},
        "anchors": {
            "lower_left": {"x": 11.0, "y": 17.0},
            "lower_right": {"x": 19.0, "y": 17.0},
            "neck_left": {"x": 11.0, "y": 19.0},
            "neck_right": {"x": 19.0, "y": 19.0},
        },
    }

    payload = overlay_postprocess_pipeline.prepare_clothing_cleanup_context(
        frame,
        user_row,
        hair_mask=hair_mask,
        body_mask=None,
    )

    assert payload == {}


def test_apply_overlay_postprocess_prefers_precomputed_body_clothing_field() -> None:
    runtime = build_runtime_stub()
    output = np.full((24, 24, 3), 50, dtype=np.uint8)
    base = np.full((24, 24, 3), np.array([220, 210, 200], dtype=np.uint8), dtype=np.uint8)
    hair_mask = np.zeros((24, 24), dtype=np.uint8)
    hair_mask[2:8, 5:19] = 255
    hair_mask[7:23, 4:9] = 255
    hair_mask[7:23, 15:20] = 255
    coverage = np.zeros((24, 24), dtype=np.uint8)
    coverage[2:10, 8:16] = 255
    body_clothing_mask = np.zeros((24, 24), dtype=np.uint8)
    body_clothing_mask[12:24, 1:23] = 255
    field_cols = np.arange(0, 24, dtype=np.int32)
    field_colors = np.empty((24, 3), dtype=np.float32)
    field_colors[:12] = np.array([30.0, 40.0, 230.0], dtype=np.float32)
    field_colors[12:] = np.array([20.0, 170.0, 80.0], dtype=np.float32)

    user_row = {
        "_hair_binary_mask": hair_mask,
        "_hair_background_color": np.array([220.0, 210.0, 200.0], dtype=np.float32),
        "_body_clothing_mask": body_clothing_mask,
        "_hair_clothing_color": np.array([40.0, 100.0, 150.0], dtype=np.float32),
        "_hair_clothing_field_cols": field_cols,
        "_hair_clothing_field_colors": field_colors,
    }

    postprocessed = runtime._apply_overlay_postprocess(
        output,
        base,
        user_row,
        renderer_name="bundle_render",
        coverage_mask=coverage,
    )

    lower_left_region = postprocessed[19:23, 4:9].astype(np.float32).mean(axis=(0, 1))
    lower_right_region = postprocessed[19:23, 15:20].astype(np.float32).mean(axis=(0, 1))
    assert float(np.abs(lower_left_region - field_colors[4]).mean()) < 40.0
    assert float(np.abs(lower_right_region - field_colors[15]).mean()) < 40.0


def test_apply_overlay_postprocess_routes_cleanup_overlapping_person_body_to_clothing() -> None:
    runtime = build_runtime_stub()
    output = np.full((24, 24, 3), 50, dtype=np.uint8)
    base = np.full((24, 24, 3), np.array([220, 210, 200], dtype=np.uint8), dtype=np.uint8)
    hair_mask = np.zeros((24, 24), dtype=np.uint8)
    hair_mask[2:8, 6:18] = 255
    hair_mask[7:23, 4:8] = 255
    coverage = np.zeros((24, 24), dtype=np.uint8)
    coverage[2:10, 8:16] = 255
    person_body_mask = np.zeros((24, 24), dtype=np.uint8)
    person_body_mask[14:24, 0:12] = 255
    body_clothing_mask = np.zeros((24, 24), dtype=np.uint8)
    body_clothing_mask[16:24, 0:12] = 255
    user_row = {
        "_hair_binary_mask": hair_mask,
        "_hair_background_color": np.array([220.0, 210.0, 200.0], dtype=np.float32),
        "_person_body_mask": person_body_mask,
        "_body_clothing_mask": body_clothing_mask,
        "_hair_clothing_color": np.array([30.0, 40.0, 230.0], dtype=np.float32),
    }

    postprocessed = runtime._apply_overlay_postprocess(
        output,
        base,
        user_row,
        renderer_name="bundle_render",
        coverage_mask=coverage,
    )

    lower_left_region = postprocessed[18:23, 4:8].astype(np.float32).mean(axis=(0, 1))
    background_region = np.array([220.0, 210.0, 200.0], dtype=np.float32)
    clothing_region = np.array([30.0, 40.0, 230.0], dtype=np.float32)
    assert float(np.abs(lower_left_region - clothing_region).mean()) < float(np.abs(lower_left_region - background_region).mean())


def test_apply_overlay_postprocess_backgroundizes_outer_side_fringe_residual() -> None:
    runtime = build_runtime_stub()
    output = np.full((24, 24, 3), 50, dtype=np.uint8)
    base = np.full((24, 24, 3), 30, dtype=np.uint8)
    base[:, :12] = np.array([220, 210, 200], dtype=np.uint8)
    base[:, 12:] = np.array([140, 170, 220], dtype=np.uint8)
    hair_mask = np.zeros((24, 24), dtype=np.uint8)
    hair_mask[2:10, 4:20] = 255
    fringe_mask = np.array(hair_mask, copy=True)
    coverage = np.zeros((24, 24), dtype=np.uint8)
    coverage[4:10, 9:15] = 255
    user_row = {
        "_hair_binary_mask": hair_mask,
        "_hair_fringe_mask": fringe_mask,
        "_hair_background_color": np.array([220.0, 210.0, 200.0], dtype=np.float32),
        "face_bbox": {"x": 7, "y": 6, "w": 10, "h": 10},
        "anchors": {
            "left_temple": {"x": 8.0, "y": 7.0},
            "right_temple": {"x": 15.0, "y": 7.0},
            "left_ear_root": {"x": 7.0, "y": 14.0},
            "right_ear_root": {"x": 16.0, "y": 14.0},
            "forehead_center": {"x": 11.5, "y": 6.0},
            "crown": {"x": 11.5, "y": 4.0},
        },
    }

    postprocessed = runtime._apply_overlay_postprocess(
        output,
        base,
        user_row,
        renderer_name="bundle_render",
        coverage_mask=coverage,
    )

    left_region = postprocessed[3:8, 4:8].astype(np.float32).mean(axis=(0, 1))
    right_region = postprocessed[3:8, 16:20].astype(np.float32).mean(axis=(0, 1))
    left_bg = base[3:8, 4:8].astype(np.float32).mean(axis=(0, 1))
    right_bg = base[3:8, 16:20].astype(np.float32).mean(axis=(0, 1))
    original_region = output[3:8, 4:8].astype(np.float32).mean(axis=(0, 1))

    assert float(np.abs(left_region - left_bg).mean()) < float(np.abs(original_region - left_bg).mean())
    assert float(np.abs(right_region - right_bg).mean()) < float(np.abs(original_region - right_bg).mean())


def test_outer_side_fringe_gate_narrows_side_seed_for_large_yaw() -> None:
    user_row_front = {
        "face_bbox": {"x": 40, "y": 30, "w": 80, "h": 110},
        "anchors": {
            "left_temple": {"x": 52.0, "y": 56.0},
            "right_temple": {"x": 108.0, "y": 56.0},
            "left_ear_root": {"x": 40.0, "y": 84.0},
            "right_ear_root": {"x": 120.0, "y": 84.0},
            "forehead_center": {"x": 80.0, "y": 38.0},
            "crown": {"x": 80.0, "y": 18.0},
        },
        "pose": {"yaw_float": 0.0},
    }
    user_row_side = {
        **user_row_front,
        "pose": {"yaw_float": 28.0},
    }

    front_seed_gate, front_keep_gate = overlay_postprocess_pipeline._build_outer_side_fringe_gates(
        user_row_front,
        (160, 160),
    )
    side_seed_gate, side_keep_gate = overlay_postprocess_pipeline._build_outer_side_fringe_gates(
        user_row_side,
        (160, 160),
    )

    assert front_seed_gate is not None
    assert side_seed_gate is not None
    assert front_keep_gate is not None
    assert side_keep_gate is not None
    assert int(np.count_nonzero(side_seed_gate)) < int(np.count_nonzero(front_seed_gate))
    assert int(np.count_nonzero(side_keep_gate)) > int(np.count_nonzero(front_keep_gate))


def test_apply_overlay_postprocess_preserves_central_face_attached_fringe_residual() -> None:
    runtime = build_runtime_stub()
    output = np.full((24, 24, 3), 50, dtype=np.uint8)
    base = np.full((24, 24, 3), 30, dtype=np.uint8)
    hair_mask = np.zeros((24, 24), dtype=np.uint8)
    hair_mask[2:10, 4:20] = 255
    fringe_mask = np.array(hair_mask, copy=True)
    coverage = np.zeros((24, 24), dtype=np.uint8)
    coverage[4:10, 9:15] = 255
    user_row = {
        "_hair_binary_mask": hair_mask,
        "_hair_fringe_mask": fringe_mask,
        "_hair_background_color": np.array([220.0, 210.0, 200.0], dtype=np.float32),
        "face_bbox": {"x": 7, "y": 6, "w": 10, "h": 10},
        "anchors": {
            "left_temple": {"x": 8.0, "y": 7.0},
            "right_temple": {"x": 15.0, "y": 7.0},
            "left_ear_root": {"x": 7.0, "y": 14.0},
            "right_ear_root": {"x": 16.0, "y": 14.0},
            "forehead_center": {"x": 11.5, "y": 6.0},
            "crown": {"x": 11.5, "y": 4.0},
        },
    }

    postprocessed = runtime._apply_overlay_postprocess(
        output,
        base,
        user_row,
        renderer_name="bundle_render",
        coverage_mask=coverage,
    )

    assert np.array_equal(postprocessed[2:4, 10:14], output[2:4, 10:14])


def test_apply_overlay_postprocess_adds_outer_n_ring_from_residual_seed_without_touching_face_interior() -> None:
    runtime = build_runtime_stub()
    output = np.full((24, 24, 3), 50, dtype=np.uint8)
    base = np.full((24, 24, 3), 30, dtype=np.uint8)
    base[:, :12] = np.array([220, 210, 200], dtype=np.uint8)
    base[:, 12:] = np.array([150, 170, 220], dtype=np.uint8)
    hair_mask = np.zeros((24, 24), dtype=np.uint8)
    hair_mask[3:6, 5:19] = 255
    hair_mask[6:18, 5:8] = 255
    hair_mask[6:18, 16:19] = 255
    coverage = np.array(hair_mask, copy=True)
    coverage[3:8, 5:19] = 0

    postprocessed = runtime._apply_overlay_postprocess(
        output,
        base,
        {
            "_hair_binary_mask": hair_mask,
            "_hair_background_color": np.array([220.0, 210.0, 200.0], dtype=np.float32),
            "face_bbox": {"x": 7, "y": 6, "w": 10, "h": 10},
            "anchors": {
                "left_temple": {"x": 8.0, "y": 7.0},
                "right_temple": {"x": 15.0, "y": 7.0},
                "left_ear_root": {"x": 7.0, "y": 14.0},
                "right_ear_root": {"x": 16.0, "y": 14.0},
                "forehead_center": {"x": 11.5, "y": 6.0},
                "crown": {"x": 11.5, "y": 4.0},
                "lower_left": {"x": 8.0, "y": 15.0},
                "lower_right": {"x": 15.0, "y": 15.0},
            },
        },
        renderer_name="bundle_render",
        coverage_mask=coverage,
    )

    assert not np.array_equal(postprocessed[0:3, 9:15], output[0:3, 9:15])
    assert not np.array_equal(postprocessed[4:8, 0:5], output[4:8, 0:5])
    assert not np.array_equal(postprocessed[4:8, 19:24], output[4:8, 19:24])
    assert np.array_equal(postprocessed[10:20, 0:5], output[10:20, 0:5])
    assert np.array_equal(postprocessed[10:20, 19:24], output[10:20, 19:24])
    assert np.array_equal(postprocessed[7:12, 10:14], output[7:12, 10:14])
    assert np.array_equal(postprocessed[9:15, 8:10], output[9:15, 8:10])


def test_apply_overlay_postprocess_merges_residual_and_outer_ring_into_single_cleanup_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = build_runtime_stub()
    output = np.full((24, 24, 3), 50, dtype=np.uint8)
    base = np.full((24, 24, 3), 30, dtype=np.uint8)
    hair_mask = np.zeros((24, 24), dtype=np.uint8)
    hair_mask[3:18, 5:19] = 255
    coverage = np.zeros((24, 24), dtype=np.uint8)
    coverage[5:15, 7:17] = 255
    user_row = {
        "_hair_binary_mask": hair_mask,
        "_hair_background_color": np.array([220.0, 210.0, 200.0], dtype=np.float32),
        "face_bbox": {"x": 7, "y": 6, "w": 10, "h": 10},
        "anchors": {
            "left_temple": {"x": 8.0, "y": 7.0},
            "right_temple": {"x": 15.0, "y": 7.0},
            "left_ear_root": {"x": 7.0, "y": 14.0},
            "right_ear_root": {"x": 16.0, "y": 14.0},
            "forehead_center": {"x": 11.5, "y": 6.0},
            "crown": {"x": 11.5, "y": 4.0},
            "lower_left": {"x": 8.0, "y": 15.0},
            "lower_right": {"x": 15.0, "y": 15.0},
        },
    }
    captured_masks: list[np.ndarray] = []
    original_backgroundize_mask = overlay_postprocess_pipeline._backgroundize_mask

    def capture_backgroundize_mask(
        output_frame_bgr: np.ndarray,
        base_frame_bgr: np.ndarray,
        hair_binary_mask: np.ndarray,
        cleanup_mask: np.ndarray,
        *,
        background_color: np.ndarray,
        alpha_scale: float = 1.0,
        external_background_mask: np.ndarray | None = None,
        use_local_background_field: bool = True,
        local_color_field: tuple[np.ndarray, np.ndarray] | None = None,
        feather_edges: bool = True,
    ) -> np.ndarray:
        _ = (
            base_frame_bgr,
            hair_binary_mask,
            background_color,
            alpha_scale,
            external_background_mask,
            use_local_background_field,
            local_color_field,
            feather_edges,
        )
        captured_masks.append(np.array(cleanup_mask, copy=True))
        return output_frame_bgr

    monkeypatch.setattr(
        overlay_postprocess_pipeline,
        "_backgroundize_mask",
        capture_backgroundize_mask,
    )

    try:
        runtime._apply_overlay_postprocess(
            output,
            base,
            user_row,
            renderer_name="bundle_render",
            coverage_mask=coverage,
        )
    finally:
        monkeypatch.setattr(
            overlay_postprocess_pipeline,
            "_backgroundize_mask",
            original_backgroundize_mask,
        )

    expected_residual_mask = cv2.bitwise_and(hair_mask, cv2.bitwise_not(coverage))
    expected_outer_ring_mask = overlay_postprocess_pipeline._build_outer_background_ring_mask(
        expected_residual_mask,
        hair_mask,
        user_row,
    )
    expected_cleanup_mask = cv2.bitwise_or(expected_residual_mask, expected_outer_ring_mask)

    assert len(captured_masks) >= 1
    merged_cleanup_mask = np.zeros_like(expected_cleanup_mask, dtype=np.uint8)
    for captured_mask in captured_masks:
        merged_cleanup_mask = cv2.bitwise_or(merged_cleanup_mask, captured_mask)
    assert np.array_equal(merged_cleanup_mask, expected_cleanup_mask)
