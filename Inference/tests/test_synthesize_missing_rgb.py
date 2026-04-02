from __future__ import annotations

import json
from pathlib import Path
import sys

import cv2
import numpy as np

TOOLS_DIR = Path(__file__).resolve().parents[1] / "hairddae_tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from synthesize_missing_rgb_from_hair_rgba import process_asset_root


def write_png(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    assert cv2.imwrite(str(path), image)


def test_process_asset_root_replaces_broken_rgb_symlink(tmp_path: Path) -> None:
    root = tmp_path
    asset_index_path = root / "manifests" / "asset_index_v0.json"
    metadata_path = root / "metadata" / "sample.json"
    hair_rgba_path = root / "hair_rgba" / "sample.png"
    image_path = root / "rgb" / "sample.png"

    rgba = np.zeros((2, 3, 4), dtype=np.uint8)
    rgba[:, :, 0] = 10
    rgba[:, :, 1] = 20
    rgba[:, :, 2] = 30
    rgba[:, :, 3] = 200
    write_png(hair_rgba_path, rgba)

    asset_index_path.parent.mkdir(parents=True, exist_ok=True)
    asset_index_path.write_text(
        json.dumps({"items": [{"asset_id": "sample", "metadata_path": "metadata/sample.json"}]}),
        encoding="utf-8",
    )

    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(
            {
                "image_path": "rgb/sample.png",
                "hair_rgba_path": "hair_rgba/sample.png",
                "image_size": {"width": 8, "height": 6},
                "hair_rgba_bbox": {"x": 2, "y": 1, "w": 3, "h": 2},
            }
        ),
        encoding="utf-8",
    )

    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.symlink_to("/tmp/missing-sample.png")
    assert image_path.is_symlink()
    assert not image_path.exists()

    summary = process_asset_root(asset_root=root, verbose=False)

    assert summary["created"] == 1
    assert summary["errors"] == 0
    assert image_path.is_file()
    assert not image_path.is_symlink()

    restored = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    assert restored is not None
    assert restored.shape == (6, 8, 3)
    assert np.array_equal(restored[1:3, 2:5], rgba[:, :, :3])
