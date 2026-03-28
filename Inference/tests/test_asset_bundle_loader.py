from __future__ import annotations

import json
from pathlib import Path
import sys

import cv2
import numpy as np
import pytest

TOOLS_DIR = Path(__file__).resolve().parents[1] / "hairddae_tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import run_hair_overlay_poc as overlay_module


def write_png(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    assert cv2.imwrite(str(path), image)


def test_load_asset_bundle_uses_hair_rgba_when_rgb_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path
    metadata_path = root / "metadata" / "sample.json"
    anchors_path = root / "anchors" / "sample.json"
    hair_rgba_path = root / "hair_rgba" / "sample.png"

    rgba = np.zeros((2, 2, 4), dtype=np.uint8)
    rgba[:, :, 0] = 10
    rgba[:, :, 1] = 20
    rgba[:, :, 2] = 30
    rgba[:, :, 3] = 200
    write_png(hair_rgba_path, rgba)

    single_mask = np.array([[255, 0], [0, 0]], dtype=np.uint8)
    for relative_path in (
        "masks/hair/sample.png",
        "masks/face/sample.png",
        "masks/forehead/sample.png",
        "masks/ear_left/sample.png",
        "masks/ear_right/sample.png",
        "masks/neck_shoulder/sample.png",
        "masks/protect_face/sample.png",
    ):
        write_png(root / relative_path, single_mask)

    anchors_path.parent.mkdir(parents=True, exist_ok=True)
    anchors_path.write_text(json.dumps({"anchors": {}}), encoding="utf-8")

    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(
            {
                "anchors_path": "anchors/sample.json",
                "image_path": "rgb/missing.png",
                "alpha_path": "alpha/missing.png",
                "hair_mask_path": "masks/hair/sample.png",
                "face_mask_path": "masks/face/sample.png",
                "forehead_mask_path": "masks/forehead/sample.png",
                "ear_mask_left_path": "masks/ear_left/sample.png",
                "ear_mask_right_path": "masks/ear_right/sample.png",
                "neck_shoulder_mask_path": "masks/neck_shoulder/sample.png",
                "protect_face_mask_path": "masks/protect_face/sample.png",
                "hair_rgba_path": "hair_rgba/sample.png",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(overlay_module, "hair_bbox_from_mask", lambda hair_mask: (0, 0, 2, 2))
    monkeypatch.setattr(overlay_module, "expanded_hair_crop", lambda hair_bbox, width, height: (0, 0, 2, 2))
    monkeypatch.setattr(overlay_module, "build_mesh_source_points", lambda anchors, crop_box: [])
    monkeypatch.setattr(overlay_module, "build_dense_mesh_source_points", lambda anchors, crop_box: [])
    monkeypatch.setattr(overlay_module, "build_mesh_triangles", lambda points, width, height: [])

    bundle = overlay_module.load_asset_bundle(str(root), "metadata/sample.json")

    assert bundle["image"].shape == (2, 2, 3)
    assert bundle["alpha"].shape == (2, 2)
    assert int(bundle["alpha"][0, 0]) == 200


def test_load_asset_bundle_synthesizes_full_frame_rgb_when_bbox_metadata_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path
    metadata_path = root / "metadata" / "sample.json"
    anchors_path = root / "anchors" / "sample.json"
    hair_rgba_path = root / "hair_rgba" / "sample.png"

    rgba = np.zeros((6, 8, 4), dtype=np.uint8)
    rgba[:, :, 0] = 10
    rgba[:, :, 1] = 20
    rgba[:, :, 2] = 30
    rgba[:, :, 3] = 200
    write_png(hair_rgba_path, rgba)

    hair_mask = np.zeros((10, 12), dtype=np.uint8)
    hair_mask[1:7, 2:10] = 255
    write_png(root / "masks/hair/sample.png", hair_mask)
    for relative_path in (
        "masks/face/sample.png",
        "masks/forehead/sample.png",
        "masks/ear_left/sample.png",
        "masks/ear_right/sample.png",
        "masks/neck_shoulder/sample.png",
        "masks/protect_face/sample.png",
    ):
        write_png(root / relative_path, np.zeros((10, 12), dtype=np.uint8))

    anchors_path.parent.mkdir(parents=True, exist_ok=True)
    anchors_path.write_text(json.dumps({"anchors": {}}), encoding="utf-8")

    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(
            {
                "anchors_path": "anchors/sample.json",
                "image_path": "rgb/missing.png",
                "alpha_path": "alpha/missing.png",
                "hair_mask_path": "masks/hair/sample.png",
                "face_mask_path": "masks/face/sample.png",
                "forehead_mask_path": "masks/forehead/sample.png",
                "ear_mask_left_path": "masks/ear_left/sample.png",
                "ear_mask_right_path": "masks/ear_right/sample.png",
                "neck_shoulder_mask_path": "masks/neck_shoulder/sample.png",
                "protect_face_mask_path": "masks/protect_face/sample.png",
                "hair_rgba_path": "hair_rgba/sample.png",
                "hair_rgba_bbox": {"x": 2, "y": 1, "w": 8, "h": 6},
                "image_size": {"width": 12, "height": 10},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(overlay_module, "hair_bbox_from_mask", lambda mask: (2, 1, 8, 6))
    monkeypatch.setattr(overlay_module, "expanded_hair_crop", lambda hair_bbox, width, height: (2, 1, 10, 7))
    monkeypatch.setattr(overlay_module, "build_mesh_source_points", lambda anchors, crop_box: [])
    monkeypatch.setattr(overlay_module, "build_dense_mesh_source_points", lambda anchors, crop_box: [])
    monkeypatch.setattr(overlay_module, "build_mesh_triangles", lambda points, width, height: [])

    bundle = overlay_module.load_asset_bundle(str(root), "metadata/sample.json")

    assert bundle["image"].shape == (10, 12, 3)
    assert bundle["alpha"].shape == (10, 12)
    assert np.array_equal(bundle["image"][1:7, 2:10], rgba[:, :, :3])
    assert int(bundle["alpha"][1, 2]) == 200
    assert bundle["hair_luma"] is not None


def test_load_asset_bundle_legacy_profile_skips_unused_masks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path
    metadata_path = root / "metadata" / "sample.json"
    anchors_path = root / "anchors" / "sample.json"

    write_png(root / "rgb" / "sample.png", np.zeros((4, 4, 3), dtype=np.uint8))
    write_png(root / "alpha" / "sample.png", np.zeros((4, 4), dtype=np.uint8))
    write_png(root / "masks" / "hair" / "sample.png", np.zeros((4, 4), dtype=np.uint8))
    write_png(root / "masks" / "face" / "sample.png", np.zeros((4, 4), dtype=np.uint8))
    write_png(root / "masks" / "protect_face" / "sample.png", np.zeros((4, 4), dtype=np.uint8))

    anchors_path.parent.mkdir(parents=True, exist_ok=True)
    anchors_path.write_text(json.dumps({"anchors": {}}), encoding="utf-8")
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(
            {
                "anchors_path": "anchors/sample.json",
                "image_path": "rgb/sample.png",
                "alpha_path": "alpha/sample.png",
                "hair_mask_path": "masks/hair/sample.png",
                "face_mask_path": "masks/face/sample.png",
                "forehead_mask_path": "masks/forehead/missing.png",
                "ear_mask_left_path": "masks/ear_left/missing.png",
                "ear_mask_right_path": "masks/ear_right/missing.png",
                "neck_shoulder_mask_path": "masks/neck_shoulder/missing.png",
                "protect_face_mask_path": "masks/protect_face/sample.png",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(overlay_module, "hair_bbox_from_mask", lambda mask: (0, 0, 4, 4))
    monkeypatch.setattr(overlay_module, "expanded_hair_crop", lambda hair_bbox, width, height: (0, 0, 4, 4))

    bundle = overlay_module.load_asset_bundle(
        str(root),
        "metadata/sample.json",
        overlay_module.BUNDLE_PROFILE_LEGACY,
    )

    assert bundle["image"].shape == (4, 4, 3)
    assert bundle["forehead_mask"] is None
    assert bundle["ear_mask_left"] is None
    assert bundle["ear_mask_right"] is None
    assert bundle["neck_shoulder_mask"] is None
    assert bundle["bundle_profile"] == overlay_module.BUNDLE_PROFILE_LEGACY


def test_load_asset_bundle_prefers_packed_legacy_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path
    metadata_path = root / "metadata" / "sample.json"
    anchors_path = root / "anchors" / "sample.json"
    packed_path = root / "packed" / "legacy" / "sample-asset.npz"

    anchors = {"left_temple": {"x": 1.0, "y": 2.0}}
    anchors_path.parent.mkdir(parents=True, exist_ok=True)
    anchors_path.write_text(json.dumps({"anchors": anchors}), encoding="utf-8")
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(
            {
                "asset_id": "sample-asset",
                "anchors_path": "anchors/sample.json",
                "image_path": "rgb/missing.png",
                "alpha_path": "alpha/missing.png",
                "hair_mask_path": "masks/hair/missing.png",
                "face_mask_path": "masks/face/missing.png",
                "protect_face_mask_path": "masks/protect_face/missing.png",
            }
        ),
        encoding="utf-8",
    )
    packed_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        packed_path,
        anchors_json=np.array(json.dumps(anchors, ensure_ascii=True), dtype=np.str_),
        crop_box=np.array([0, 0, 4, 4], dtype=np.int32),
        hair_bbox=np.array([0, 0, 4, 4], dtype=np.int32),
        hair_luma=np.array([42.0], dtype=np.float32),
        image_size=np.array([4, 4], dtype=np.int32),
        packed_crop_only=np.array([1], dtype=np.uint8),
        image=np.full((4, 4, 3), 7, dtype=np.uint8),
        alpha=np.full((4, 4), 9, dtype=np.uint8),
        hair_mask=np.full((4, 4), 11, dtype=np.uint8),
        face_mask=np.full((4, 4), 13, dtype=np.uint8),
        protect_face_mask=np.full((4, 4), 15, dtype=np.uint8),
    )

    monkeypatch.setattr(overlay_module, "PACKED_BUNDLES_ENABLED", True)

    bundle = overlay_module.load_asset_bundle(
        str(root),
        "metadata/sample.json",
        overlay_module.BUNDLE_PROFILE_LEGACY,
    )

    assert bundle["bundle_profile"] == overlay_module.BUNDLE_PROFILE_LEGACY
    assert bundle["packed_bundle_path"].endswith("packed/legacy/sample-asset.npz")
    assert bundle["packed_crop_only"] is True
    assert bundle["anchors"] == anchors
    assert int(bundle["image"][0, 0, 0]) == 7
    assert int(bundle["alpha"][0, 0]) == 9
    assert int(bundle["hair_mask"][0, 0]) == 11
    assert int(bundle["face_mask"][0, 0]) == 13
    assert int(bundle["protect_face_mask"][0, 0]) == 15
    assert bundle["hair_luma"] == pytest.approx(42.0)


def test_build_legacy_overlay_layer_uses_opencv_warp_affine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[tuple[int, int], int]] = []
    debug_payload: dict[str, object] = {}

    def fake_warp(
        image: np.ndarray,
        matrix: np.ndarray,
        dsize: tuple[int, int],
        *,
        flags: int = cv2.INTER_LINEAR,
        **_: object,
    ) -> np.ndarray:
        calls.append((dsize, flags))
        width, height = dsize
        if image.ndim == 2:
            return np.zeros((height, width), dtype=image.dtype)
        return np.zeros((height, width, image.shape[2]), dtype=image.dtype)

    monkeypatch.setattr(overlay_module, "opencv_warp_affine", fake_warp)
    monkeypatch.setattr(overlay_module.cv2, "warpAffine", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("raw warpAffine should not be used")))
    monkeypatch.setattr(overlay_module, "apply_masked_rgb_gain", lambda rgb, hair, gain: rgb)
    monkeypatch.setattr(
        overlay_module,
        "build_effective_alpha",
        lambda alpha, hair, soft_sigma=1.8, alpha_gain=None, hair_sigma=2.2: np.ones(alpha.shape, dtype=np.float32),
    )
    monkeypatch.setattr(
        overlay_module,
        "apply_asset_skin_suppression_gain",
        lambda user_row, roi, effective_alpha, warped_face, warped_protect_face, warped_ear_left, warped_ear_right, **kwargs: effective_alpha,
    )

    anchors = {
        "left_temple": {"x": 8.0, "y": 8.0},
        "right_temple": {"x": 24.0, "y": 8.0},
        "forehead_center": {"x": 16.0, "y": 6.0},
        "crown": {"x": 16.0, "y": 2.0},
        "left_side": {"x": 6.0, "y": 14.0},
        "right_side": {"x": 26.0, "y": 14.0},
        "left_ear_root": {"x": 5.0, "y": 15.0},
        "right_ear_root": {"x": 27.0, "y": 15.0},
        "lower_left": {"x": 9.0, "y": 24.0},
        "lower_right": {"x": 23.0, "y": 24.0},
        "neck_left": {"x": 11.0, "y": 29.0},
        "neck_right": {"x": 21.0, "y": 29.0},
    }

    user_row = {
        "anchors": anchors,
        "face_bbox": {"w": 16.0, "h": 23.0},
        "pose": {"yaw_1deg": 0.0, "pitch_1deg": 0.0, "roll_1deg": 0.0},
        "candidate_face_count": 1,
    }
    user_image = np.zeros((32, 32, 3), dtype=np.uint8)
    asset_bundle = {
        "image": np.zeros((32, 32, 3), dtype=np.uint8),
        "alpha": np.zeros((32, 32), dtype=np.uint8),
        "hair_mask": np.zeros((32, 32), dtype=np.uint8),
        "face_mask": np.zeros((32, 32), dtype=np.uint8),
        "protect_face_mask": np.zeros((32, 32), dtype=np.uint8),
        "ear_mask_left": np.zeros((32, 32), dtype=np.uint8),
        "ear_mask_right": np.zeros((32, 32), dtype=np.uint8),
        "anchors": anchors,
        "crop_box": (0, 0, 32, 32),
        "hair_luma": None,
    }

    layer = overlay_module.build_legacy_overlay_layer(
        user_row,
        user_image,
        asset_bundle,
        user_mask_bundle=None,
        debug_payload=debug_payload,
    )

    assert layer is not None
    assert len(calls) == 4
    assert "warp_rgb_ms" in debug_payload
    assert "effective_alpha_ms" in debug_payload
    assert "legacy_layer_total_ms" in debug_payload
