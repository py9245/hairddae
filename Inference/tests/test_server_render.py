from __future__ import annotations

import numpy as np
from PIL import Image

from app.catalog import AssetBundle
from app.server_render import compose_bundle_frame


def test_compose_bundle_frame_restores_uncovered_base_roi(tmp_path) -> None:
    rgba = np.zeros((4, 4, 4), dtype=np.uint8)
    rgba[1:3, 1:3, :3] = np.array([18, 28, 220], dtype=np.uint8)
    rgba[1:3, 1:3, 3] = 255
    hair_path = tmp_path / "hair.png"
    Image.fromarray(rgba, mode="RGBA").save(hair_path)

    bundle = AssetBundle(
        asset_id="asset-a",
        pose_key="0_0_0",
        yaw_1deg=0,
        pitch_1deg=0,
        roll_1deg=0,
        hair_rgba_path=hair_path,
        hair_rgba_url=None,
        hair_mask_url=None,
        anchors_url=None,
        metadata_url=None,
        hair_bbox={"x": 0, "y": 0, "w": 4, "h": 4},
        face_mask_url=None,
        protect_face_mask_url=None,
        render_task={
            "destination_roi": {"x": 0, "y": 0, "w": 4, "h": 4},
            "matrix": {"a": 1.0, "b": 0.0, "c": 0.0, "d": 1.0, "e": 0.0, "f": 0.0},
        },
        revision="r1",
        score=1.0,
    )

    suppressed_frame = Image.fromarray(np.full((4, 4, 3), 190, dtype=np.uint8), mode="RGB")
    original_frame = Image.fromarray(np.full((4, 4, 3), 24, dtype=np.uint8), mode="RGB")

    output = compose_bundle_frame(
        suppressed_frame,
        bundle,
        original_frame_image=original_frame,
        coverage_feather_px=0,
    )

    output_bgr = np.asarray(output, dtype=np.uint8)
    uncovered_pixel = output_bgr[0, 0]
    covered_pixel = output_bgr[1, 1]

    assert np.allclose(uncovered_pixel, np.array([24, 24, 24], dtype=np.uint8), atol=2)
    assert int(covered_pixel[2]) > int(uncovered_pixel[2])


def test_compose_bundle_frame_replaces_asset_skin_with_base_skin(tmp_path) -> None:
    rgba = np.zeros((4, 4, 4), dtype=np.uint8)
    rgba[1:3, 1:3, :3] = np.array([220, 200, 190], dtype=np.uint8)
    rgba[1:3, 1:3, 3] = 255
    rgba[1, 1, :3] = np.array([10, 10, 10], dtype=np.uint8)
    hair_path = tmp_path / "hair.png"
    Image.fromarray(rgba, mode="RGBA").save(hair_path)

    face_mask = np.zeros((4, 4), dtype=np.uint8)
    face_mask[1:3, 1:3] = 255
    face_mask_path = tmp_path / "face.png"
    Image.fromarray(face_mask, mode="L").save(face_mask_path)

    bundle = AssetBundle(
        asset_id="asset-a",
        pose_key="0_0_0",
        yaw_1deg=0,
        pitch_1deg=0,
        roll_1deg=0,
        hair_rgba_path=hair_path,
        hair_rgba_url=None,
        hair_mask_url=None,
        anchors_url=None,
        metadata_url=None,
        hair_bbox={"x": 0, "y": 0, "w": 4, "h": 4},
        face_mask_url=None,
        protect_face_mask_url=None,
        render_task={
            "destination_roi": {"x": 0, "y": 0, "w": 4, "h": 4},
            "matrix": {"a": 1.0, "b": 0.0, "c": 0.0, "d": 1.0, "e": 0.0, "f": 0.0},
        },
        revision="r1",
        score=1.0,
        face_mask_path=face_mask_path,
    )

    base = np.full((4, 4, 3), 120, dtype=np.uint8)
    output = compose_bundle_frame(
        Image.fromarray(base, mode="RGB"),
        bundle,
        preserve_uncovered_base=False,
    )

    output_rgb = np.asarray(output, dtype=np.uint8)
    replaced_pixel = output_rgb[2, 2].astype(np.float32)
    base_pixel = np.array([120, 120, 120], dtype=np.float32)
    asset_pixel = np.array([220, 200, 190], dtype=np.float32)
    assert np.mean(np.abs(replaced_pixel - base_pixel)) < np.mean(np.abs(replaced_pixel - asset_pixel))
    assert int(output_rgb[1, 1, 0]) < 40


def test_compose_bundle_frame_prefers_explicit_skin_replacement_color(tmp_path) -> None:
    rgba = np.zeros((4, 4, 4), dtype=np.uint8)
    rgba[1:3, 1:3, :3] = np.array([220, 200, 190], dtype=np.uint8)
    rgba[1:3, 1:3, 3] = 255
    hair_path = tmp_path / "hair.png"
    Image.fromarray(rgba, mode="RGBA").save(hair_path)

    face_mask = np.zeros((4, 4), dtype=np.uint8)
    face_mask[1:3, 1:3] = 255
    face_mask_path = tmp_path / "face.png"
    Image.fromarray(face_mask, mode="L").save(face_mask_path)

    bundle = AssetBundle(
        asset_id="asset-a",
        pose_key="0_0_0",
        yaw_1deg=0,
        pitch_1deg=0,
        roll_1deg=0,
        hair_rgba_path=hair_path,
        hair_rgba_url=None,
        hair_mask_url=None,
        anchors_url=None,
        metadata_url=None,
        hair_bbox={"x": 0, "y": 0, "w": 4, "h": 4},
        face_mask_url=None,
        protect_face_mask_url=None,
        render_task={
            "destination_roi": {"x": 0, "y": 0, "w": 4, "h": 4},
            "matrix": {"a": 1.0, "b": 0.0, "c": 0.0, "d": 1.0, "e": 0.0, "f": 0.0},
        },
        revision="r1",
        score=1.0,
        face_mask_path=face_mask_path,
    )

    base = np.full((4, 4, 3), 120, dtype=np.uint8)
    replacement_color = np.array([168, 144, 132], dtype=np.float32)
    output = compose_bundle_frame(
        Image.fromarray(base, mode="RGB"),
        bundle,
        preserve_uncovered_base=False,
        skin_replacement_color_rgb=replacement_color,
    )

    output_rgb = np.asarray(output, dtype=np.uint8)
    replaced_pixel = output_rgb[2, 2].astype(np.float32)
    asset_pixel = np.array([220, 200, 190], dtype=np.float32)
    assert np.allclose(replaced_pixel, replacement_color, atol=1.0)
    assert np.mean(np.abs(replaced_pixel - replacement_color)) < np.mean(np.abs(replaced_pixel - asset_pixel))
    assert np.mean(np.abs(replaced_pixel - replacement_color)) < np.mean(np.abs(replaced_pixel - base[2, 2].astype(np.float32)))


def test_compose_bundle_frame_replaces_bright_fringe_connected_to_face_mask(tmp_path) -> None:
    rgba = np.zeros((6, 6, 4), dtype=np.uint8)
    rgba[1:5, 2:4, :3] = np.array([226, 204, 196], dtype=np.uint8)
    rgba[1:5, 2:4, 3] = 255
    rgba[1:5, 4, :3] = np.array([220, 198, 192], dtype=np.uint8)
    rgba[1:5, 4, 3] = 18
    hair_path = tmp_path / "hair.png"
    Image.fromarray(rgba, mode="RGBA").save(hair_path)

    face_mask = np.zeros((6, 6), dtype=np.uint8)
    face_mask[1:5, 2:4] = 255
    face_mask_path = tmp_path / "face.png"
    Image.fromarray(face_mask, mode="L").save(face_mask_path)

    bundle = AssetBundle(
        asset_id="asset-a",
        pose_key="0_0_0",
        yaw_1deg=0,
        pitch_1deg=0,
        roll_1deg=0,
        hair_rgba_path=hair_path,
        hair_rgba_url=None,
        hair_mask_url=None,
        anchors_url=None,
        metadata_url=None,
        hair_bbox={"x": 0, "y": 0, "w": 6, "h": 6},
        face_mask_url=None,
        protect_face_mask_url=None,
        render_task={
            "destination_roi": {"x": 0, "y": 0, "w": 6, "h": 6},
            "matrix": {"a": 1.0, "b": 0.0, "c": 0.0, "d": 1.0, "e": 0.0, "f": 0.0},
        },
        revision="r1",
        score=1.0,
        face_mask_path=face_mask_path,
    )

    base = np.full((6, 6, 3), 118, dtype=np.uint8)
    output = compose_bundle_frame(
        Image.fromarray(base, mode="RGB"),
        bundle,
        preserve_uncovered_base=False,
    )

    output_rgb = np.asarray(output, dtype=np.uint8)
    fringe_pixel = output_rgb[3, 4].astype(np.float32)
    base_pixel = np.array([118, 118, 118], dtype=np.float32)
    asset_pixel = np.array([220, 198, 192], dtype=np.float32)
    assert np.mean(np.abs(fringe_pixel - base_pixel)) < np.mean(np.abs(fringe_pixel - asset_pixel))


def test_compose_bundle_frame_populates_debug_timings(tmp_path) -> None:
    rgba = np.zeros((4, 4, 4), dtype=np.uint8)
    rgba[1:3, 1:3, :3] = np.array([64, 96, 180], dtype=np.uint8)
    rgba[1:3, 1:3, 3] = 255
    hair_path = tmp_path / "hair.png"
    Image.fromarray(rgba, mode="RGBA").save(hair_path)

    bundle = AssetBundle(
        asset_id="asset-a",
        pose_key="0_0_0",
        yaw_1deg=0,
        pitch_1deg=0,
        roll_1deg=0,
        hair_rgba_path=hair_path,
        hair_rgba_url=None,
        hair_mask_url=None,
        anchors_url=None,
        metadata_url=None,
        hair_bbox={"x": 0, "y": 0, "w": 4, "h": 4},
        face_mask_url=None,
        protect_face_mask_url=None,
        render_task={
            "destination_roi": {"x": 0, "y": 0, "w": 4, "h": 4},
            "matrix": {"a": 1.0, "b": 0.0, "c": 0.0, "d": 1.0, "e": 0.0, "f": 0.0},
        },
        revision="r1",
        score=1.0,
    )

    debug_payload: dict[str, object] = {}
    output = compose_bundle_frame(
        Image.fromarray(np.full((4, 4, 3), 24, dtype=np.uint8), mode="RGB"),
        bundle,
        debug_payload=debug_payload,
    )

    assert output.size == (4, 4)
    assert "coverage_mask" in debug_payload
    timings_ms = debug_payload["timings_ms"]
    assert timings_ms["rgba_load_ms"] >= 0.0
    assert timings_ms["warp_patch_ms"] >= 0.0
    assert timings_ms["alpha_composite_ms"] >= 0.0
    assert timings_ms["total_ms"] >= 0.0
