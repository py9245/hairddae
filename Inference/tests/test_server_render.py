from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from app.catalog import AssetBundle
from app.server_render import compose_bundle_frame, compose_bundle_frame_rgb


def _build_bundle(image_path: str) -> AssetBundle:
    return AssetBundle(
        asset_id="asset-1",
        pose_key="pose-1",
        yaw_1deg=0,
        pitch_1deg=0,
        roll_1deg=0,
        hair_rgba_path=None if not image_path else Path(image_path),
        hair_rgba_url=None,
        hair_mask_url=None,
        anchors_url=None,
        metadata_url=None,
        hair_bbox={"x": 0, "y": 0, "w": 4, "h": 4},
        face_mask_url=None,
        protect_face_mask_url=None,
        render_task={
            "matrix": {"a": 1.0, "b": 0.0, "c": 0.0, "d": 1.0, "e": 3.0, "f": 4.0},
            "destination_roi": {"x": 3, "y": 4, "w": 4, "h": 4},
        },
        revision="test",
        score=0.0,
    )


def test_compose_bundle_frame_rgb_blends_overlay_without_mutating_input(tmp_path) -> None:
    overlay_rgba = np.zeros((4, 4, 4), dtype=np.uint8)
    overlay_rgba[:, :, 0] = 200
    overlay_rgba[:, :, 1] = 10
    overlay_rgba[:, :, 2] = 10
    overlay_rgba[:, :, 3] = 128
    overlay_path = tmp_path / "overlay.png"
    Image.fromarray(overlay_rgba).save(overlay_path)

    frame_rgb = np.full((12, 12, 3), 20, dtype=np.uint8)
    original = frame_rgb.copy()
    bundle = _build_bundle(str(overlay_path))

    rendered = compose_bundle_frame_rgb(frame_rgb, bundle)

    assert np.array_equal(frame_rgb, original)
    assert rendered.shape == frame_rgb.shape

    expected_roi = (
        (
            overlay_rgba[:, :, :3].astype(np.uint16) * 128
            + original[4:8, 3:7].astype(np.uint16) * 127
            + 127
        )
        // 255
    ).astype(np.uint8)
    assert np.array_equal(rendered[4:8, 3:7], expected_roi)
    assert np.array_equal(rendered[:4, :, :], original[:4, :, :])


def test_compose_bundle_frame_wrapper_matches_rgb_path(tmp_path) -> None:
    overlay_rgba = np.zeros((4, 4, 4), dtype=np.uint8)
    overlay_rgba[:, :, 1] = 180
    overlay_rgba[:, :, 3] = 255
    overlay_path = tmp_path / "overlay.png"
    Image.fromarray(overlay_rgba).save(overlay_path)

    frame_rgb = np.full((12, 12, 3), 40, dtype=np.uint8)
    bundle = _build_bundle(str(overlay_path))

    rendered_rgb = compose_bundle_frame_rgb(frame_rgb, bundle)
    rendered_image = compose_bundle_frame(Image.fromarray(frame_rgb), bundle)

    assert np.array_equal(rendered_rgb, np.asarray(rendered_image))
