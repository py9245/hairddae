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
