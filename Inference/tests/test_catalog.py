from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.catalog import AssetCatalog
from app.config import Settings
from app.http_runtime import _load_dataset_summary
from conftest import apply_test_env


def _write_dataset(root: Path, dataset_code: str, manifest_relpath: str) -> str:
    asset_root = root / dataset_code
    manifest_path = asset_root / manifest_relpath
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    asset_id = "sample_asset"
    metadata_relpath = "metadata/sample_asset.json"
    anchors_relpath = "anchors/sample_asset.json"

    payload = {
        "summary": {"asset_count": 1},
        "items": [
            {
                "asset_id": asset_id,
                "pose_key": "yaw+01_pitch+02_roll+03",
                "image_path": "rgb/sample_asset.png",
                "metadata_path": metadata_relpath,
                "anchors_path": anchors_relpath,
                "quality_status": "pending_asset_qc",
            }
        ],
    }
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    metadata = {
        "asset_id": asset_id,
        "pose_key": "yaw+01_pitch+02_roll+03",
        "image_path": "rgb/sample_asset.png",
        "alpha_path": "alpha/sample_asset.png",
        "hair_rgba_path": "hair_rgba/sample_asset.png",
        "hair_mask_path": "masks/hair/sample_asset.png",
        "face_mask_path": "masks/face/sample_asset.png",
        "protect_face_mask_path": "masks/protect_face/sample_asset.png",
        "anchors_path": anchors_relpath,
        "yaw_1deg": 1,
        "pitch_1deg": 2,
        "roll_1deg": 3,
        "approved": False,
        "quality_score": 0.73,
        "hair_mean_confidence": 0.81,
        "hair_rgba_bbox": {"x": 10, "y": 20, "w": 30, "h": 40},
    }
    metadata_path = asset_root / metadata_relpath
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    anchors_path = asset_root / anchors_relpath
    anchors_path.parent.mkdir(parents=True, exist_ok=True)
    anchors_path.write_text(json.dumps({"anchors": {}}), encoding="utf-8")

    return asset_id


def _settings_for_root(monkeypatch: pytest.MonkeyPatch, static_root: Path) -> Settings:
    apply_test_env(monkeypatch, INFERENCE_STATIC_ROOT=str(static_root))
    return Settings.from_env()


def test_catalog_accepts_manifest_json_and_enriches_items(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset_id = _write_dataset(tmp_path, "0009", "manifests/manifest.json")
    settings = _settings_for_root(monkeypatch, tmp_path)
    catalog = AssetCatalog(settings)

    assert catalog.dataset_exists("0009") is True

    bundle = catalog.bundle_for_runtime_selection("0009", asset_id, score=1.5)

    assert bundle.asset_id == asset_id
    assert bundle.yaw_1deg == 1
    assert bundle.pitch_1deg == 2
    assert bundle.roll_1deg == 3
    assert bundle.hair_rgba_url == "/static/0009/hair_rgba/sample_asset.png"
    assert bundle.hair_mask_url == "/static/0009/masks/hair/sample_asset.png"
    assert bundle.face_mask_url == "/static/0009/masks/face/sample_asset.png"
    assert bundle.protect_face_mask_url == "/static/0009/masks/protect_face/sample_asset.png"


def test_catalog_and_http_summary_accept_asset_manifest_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset_id = _write_dataset(tmp_path, "0010", "indices/asset_manifest.json")
    settings = _settings_for_root(monkeypatch, tmp_path)
    catalog = AssetCatalog(settings)

    assert catalog.dataset_exists("0010") is True

    bundle = catalog.bundle_for_runtime_selection("0010", asset_id, score=0.0)
    assert bundle.asset_id == asset_id

    summary = _load_dataset_summary(tmp_path, "0010")
    assert summary["dataset_code"] == "0010"
    assert summary["asset_index_exists"] is True
    assert summary["asset_count"] == 1
    assert str(summary["asset_index_path"]).endswith("indices/asset_manifest.json")
