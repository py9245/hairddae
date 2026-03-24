from __future__ import annotations

import json
import threading
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("cv2")
pytest.importorskip("mediapipe")
pytest.importorskip("torch")
pytest.importorskip("torchvision")

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
    runtime.bundle_render_enabled = True
    runtime.bundle_render_latency_only = True
    runtime.bundle_render_render_cost_ratio = 0.098
    runtime.bundle_render_allow_transition = True
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
        lambda asset_row: RuntimeBundleRenderEntry(
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
        lambda asset_row: RuntimeBundleRenderEntry(
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


def test_compose_single_bundle_render_frame_passes_tone_gain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = build_runtime_stub()
    captured: dict[str, object] = {"rgb_gain": None, "original_frame_image": None}

    monkeypatch.setattr(
        runtime,
        "_bundle_render_entry_for_asset",
        lambda asset_row: RuntimeBundleRenderEntry(
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
        return frame_image

    monkeypatch.setattr("app.hairddae_runtime.compose_bundle_frame", fake_compose_bundle_frame)

    frame = np.full((8, 8, 3), 28, dtype=np.uint8)
    output, coverage_mask = runtime._compose_single_bundle_render_frame(
        {
            "image_size": {"width": 8, "height": 8},
            "pose": {"yaw_1deg": 0, "pitch_1deg": 0, "roll_1deg": 0},
            "face_bbox": {"x": 0.1, "y": 0.1, "w": 0.4, "h": 0.4},
            "anchors": {},
            "_hair_tone": {"mean_luma": 86.0, "coverage": 0.12},
        },
        frame,
        {"asset_id": "asset-a"},
        source_frame_bgr=np.full_like(frame, 16),
    )

    assert np.array_equal(output, frame)
    assert coverage_mask is None
    assert captured["rgb_gain"] is not None
    assert float(captured["rgb_gain"]) > 1.0
    assert captured["original_frame_image"] is not None


def test_apply_overlay_postprocess_ignores_non_upper_residual_hair() -> None:
    runtime = build_runtime_stub()
    output = np.full((6, 6, 3), 40, dtype=np.uint8)
    base = np.full((6, 6, 3), 30, dtype=np.uint8)
    coverage = np.zeros((6, 6), dtype=np.uint8)
    coverage[2:4, 2:4] = 255
    hair_mask = np.zeros((6, 6), dtype=np.uint8)
    hair_mask[1:5, 1:5] = 255

    postprocessed = runtime._apply_overlay_postprocess(
        output,
        base,
        {
            "_hair_binary_mask": hair_mask,
            "_hair_background_color": np.array([200.0, 180.0, 160.0], dtype=np.float32),
        },
        renderer_name="bundle_render",
        coverage_mask=coverage,
    )

    assert np.array_equal(postprocessed, output)


def test_apply_overlay_postprocess_backgroundizes_upper_residual_more_aggressively() -> None:
    runtime = build_runtime_stub()
    output = np.full((8, 8, 3), 50, dtype=np.uint8)
    base = np.full((8, 8, 3), 30, dtype=np.uint8)
    coverage = np.zeros((8, 8), dtype=np.uint8)
    coverage[3:7, 2:6] = 255
    hair_mask = np.zeros((8, 8), dtype=np.uint8)
    hair_mask[1:7, 1:7] = 255
    upper_mask = np.zeros((8, 8), dtype=np.uint8)
    upper_mask[1:4, 1:7] = 255

    postprocessed = runtime._apply_overlay_postprocess(
        output,
        base,
        {
            "_hair_binary_mask": hair_mask,
            "_hair_upper_region_mask": upper_mask,
            "_hair_background_color": np.array([220.0, 210.0, 200.0], dtype=np.float32),
        },
        renderer_name="bundle_render",
        coverage_mask=coverage,
    )

    assert int(postprocessed[1, 3, 0]) > int(postprocessed[5, 3, 0])
    assert np.array_equal(postprocessed[4, 3], output[4, 3])


def test_apply_overlay_postprocess_limits_backgroundization_to_upper_arch() -> None:
    runtime = build_runtime_stub()
    output = np.full((8, 8, 3), 50, dtype=np.uint8)
    base = np.full((8, 8, 3), 30, dtype=np.uint8)
    coverage = np.zeros((8, 8), dtype=np.uint8)
    coverage[3:7, 2:6] = 255
    hair_mask = np.zeros((8, 8), dtype=np.uint8)
    hair_mask[1:7, 1:7] = 255
    upper_mask = np.zeros((8, 8), dtype=np.uint8)
    upper_mask[1:3, 1:7] = 255

    postprocessed = runtime._apply_overlay_postprocess(
        output,
        base,
        {
            "_hair_binary_mask": hair_mask,
            "_hair_upper_region_mask": upper_mask,
            "_hair_background_color": np.array([220.0, 210.0, 200.0], dtype=np.float32),
        },
        renderer_name="bundle_render",
        coverage_mask=coverage,
    )

    assert int(postprocessed[1, 3, 0]) > int(output[1, 3, 0])
    assert np.array_equal(postprocessed[3, 1], output[3, 1])
    assert np.array_equal(postprocessed[5, 3], output[5, 3])


def test_apply_overlay_postprocess_preserves_face_protect_region() -> None:
    runtime = build_runtime_stub()
    output = np.full((8, 8, 3), 50, dtype=np.uint8)
    base = np.full((8, 8, 3), 30, dtype=np.uint8)
    coverage = np.zeros((8, 8), dtype=np.uint8)
    coverage[3:7, 2:6] = 255
    hair_mask = np.zeros((8, 8), dtype=np.uint8)
    hair_mask[1:7, 1:7] = 255
    upper_mask = np.zeros((8, 8), dtype=np.uint8)
    upper_mask[1:4, 1:7] = 255
    face_protect = np.zeros((8, 8), dtype=np.uint8)
    face_protect[2:5, 2:6] = 255

    postprocessed = runtime._apply_overlay_postprocess(
        output,
        base,
        {
            "_hair_binary_mask": hair_mask,
            "_hair_upper_region_mask": upper_mask,
            "_hair_face_protect_mask": face_protect,
            "_hair_background_color": np.array([220.0, 210.0, 200.0], dtype=np.float32),
        },
        renderer_name="bundle_render",
        coverage_mask=coverage,
    )

    assert np.array_equal(postprocessed[2, 3], output[2, 3])
    assert int(postprocessed[1, 3, 0]) > int(output[1, 3, 0])
