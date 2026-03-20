from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from threading import Lock
from typing import Any

from app.config import Settings
from app.hairddae_adapter import (
    build_runtime_asset_rows,
    score_asset_for_feature,
    select_runtime_asset,
)
from app.models import FeatureMessageModel
from app.render import build_render_task


def _normalize_url(base_url: str, dataset_code: str, relative_path: str | None) -> str | None:
    if not relative_path:
        return None
    return f"{base_url}/{dataset_code}/{relative_path.lstrip('/')}"


@dataclass(frozen=True)
class AssetBundle:
    asset_id: str
    pose_key: str
    yaw_1deg: int
    pitch_1deg: int
    roll_1deg: int
    hair_rgba_path: Path | None
    hair_rgba_url: str | None
    hair_mask_url: str | None
    anchors_url: str | None
    metadata_url: str | None
    hair_bbox: dict[str, int] | None
    face_mask_url: str | None
    protect_face_mask_url: str | None
    render_task: dict[str, Any] | None
    revision: str
    score: float
    dataset_code: str | None = None
    asset_root_path: Path | None = None
    metadata_path: str | None = None
    asset_row: dict[str, Any] | None = None
    weighted_assets: tuple[tuple[dict[str, Any], float], ...] = ()

    def to_message(self) -> dict[str, Any]:
        return {
            "asset_bundle_schema_version": 1,
            "asset_id": self.asset_id,
            "pose_key": self.pose_key,
            "yaw_1deg": self.yaw_1deg,
            "pitch_1deg": self.pitch_1deg,
            "roll_1deg": self.roll_1deg,
            "hair_rgba_url": self.hair_rgba_url,
            "hair_mask_url": self.hair_mask_url,
            "anchors_url": self.anchors_url,
            "metadata_url": self.metadata_url,
            "hair_bbox": self.hair_bbox,
            "face_mask_url": self.face_mask_url,
            "protect_face_mask_url": self.protect_face_mask_url,
            "render_task": self.render_task,
            "revision": self.revision,
            "score": self.score,
        }


@dataclass(frozen=True)
class DatasetRecord:
    dataset_code: str
    asset_root_path: Path
    runtime_items: tuple[dict[str, Any], ...]
    items_by_id: dict[str, dict[str, Any]]
    metadata_cache: dict[str, dict[str, Any]]
    anchors_cache: dict[str, dict[str, Any]]


class AssetCatalog:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache: dict[str, DatasetRecord] = {}
        self._lock = Lock()

    def recommend(
        self,
        dataset_code: str,
        feature: FeatureMessageModel,
        representative_asset_id: str | None = None,
    ) -> AssetBundle:
        dataset = self._load_dataset(dataset_code)
        selection = select_runtime_asset(
            dataset.asset_root_path,
            list(dataset.runtime_items),
            feature,
            representative_asset_id=representative_asset_id,
        )
        return self._build_bundle(
            dataset,
            selection.selected_asset,
            feature,
            score=selection.score,
            weighted_assets=((selection.selected_asset, 1.0),),
        )

    def bundle_for_asset(
        self,
        dataset_code: str,
        asset_id: str,
        feature: FeatureMessageModel,
    ) -> AssetBundle:
        dataset = self._load_dataset(dataset_code)
        asset = dataset.items_by_id.get(asset_id)
        if asset is None:
            raise ValueError(f"unknown asset_id {asset_id} for dataset {dataset_code}")
        return self._build_bundle(
            dataset,
            asset,
            feature,
            score=score_asset_for_feature(feature, asset),
            weighted_assets=((asset, 1.0),),
        )

    def bundle_for_runtime_selection(
        self,
        dataset_code: str,
        asset_id: str,
        *,
        score: float | None = None,
    ) -> AssetBundle:
        dataset = self._load_dataset(dataset_code)
        asset = dataset.items_by_id.get(asset_id)
        if asset is None:
            raise ValueError(f"unknown asset_id {asset_id} for dataset {dataset_code}")
        return self._build_runtime_bundle(
            dataset,
            asset,
            score=0.0 if score is None else float(score),
        )

    def _build_bundle(
        self,
        dataset: DatasetRecord,
        asset: dict[str, Any],
        feature: FeatureMessageModel,
        *,
        score: float,
        weighted_assets: tuple[tuple[dict[str, Any], float], ...],
    ) -> AssetBundle:
        metadata = self._load_metadata(dataset, asset)
        anchors_payload = self._load_anchors(dataset, asset)
        render_task = build_render_task(
            feature=feature,
            asset_anchors_payload=anchors_payload,
            metadata=metadata,
        )
        hair_rgba_path = metadata.get("hair_rgba_path")
        return AssetBundle(
            asset_id=str(asset["asset_id"]),
            pose_key=str(asset["pose_key"]),
            yaw_1deg=int(asset.get("yaw_1deg", 0)),
            pitch_1deg=int(asset.get("pitch_1deg", 0)),
            roll_1deg=int(asset.get("roll_1deg", 0)),
            hair_rgba_path=(
                None
                if hair_rgba_path in (None, "")
                else dataset.asset_root_path / str(hair_rgba_path)
            ),
            hair_rgba_url=_normalize_url(
                self._settings.static_base_url,
                dataset.dataset_code,
                None if hair_rgba_path in (None, "") else str(hair_rgba_path),
            ),
            hair_mask_url=_normalize_url(
                self._settings.static_base_url,
                dataset.dataset_code,
                None if asset.get("hair_mask_path") in (None, "") else str(asset["hair_mask_path"]),
            ),
            anchors_url=_normalize_url(
                self._settings.static_base_url,
                dataset.dataset_code,
                str(asset["anchors_path"]),
            ),
            metadata_url=_normalize_url(
                self._settings.static_base_url,
                dataset.dataset_code,
                str(asset["metadata_path"]),
            ),
            hair_bbox=metadata.get("hair_rgba_bbox"),
            face_mask_url=_normalize_url(
                self._settings.static_base_url,
                dataset.dataset_code,
                metadata.get("face_mask_path"),
            ),
            protect_face_mask_url=_normalize_url(
                self._settings.static_base_url,
                dataset.dataset_code,
                metadata.get("protect_face_mask_path"),
            ),
            render_task=None if render_task is None else render_task.to_message(),
            revision=f"{dataset.dataset_code}:{asset['asset_id']}",
            score=float(score),
            dataset_code=dataset.dataset_code,
            asset_root_path=dataset.asset_root_path,
            metadata_path=str(asset["metadata_path"]),
            asset_row=asset,
            weighted_assets=weighted_assets,
        )

    def _build_runtime_bundle(
        self,
        dataset: DatasetRecord,
        asset: dict[str, Any],
        *,
        score: float,
    ) -> AssetBundle:
        metadata = self._load_metadata(dataset, asset)
        hair_rgba_path = metadata.get("hair_rgba_path")
        return AssetBundle(
            asset_id=str(asset["asset_id"]),
            pose_key=str(asset["pose_key"]),
            yaw_1deg=int(asset.get("yaw_1deg", 0)),
            pitch_1deg=int(asset.get("pitch_1deg", 0)),
            roll_1deg=int(asset.get("roll_1deg", 0)),
            hair_rgba_path=(
                None
                if hair_rgba_path in (None, "")
                else dataset.asset_root_path / str(hair_rgba_path)
            ),
            hair_rgba_url=_normalize_url(
                self._settings.static_base_url,
                dataset.dataset_code,
                None if hair_rgba_path in (None, "") else str(hair_rgba_path),
            ),
            hair_mask_url=_normalize_url(
                self._settings.static_base_url,
                dataset.dataset_code,
                None if asset.get("hair_mask_path") in (None, "") else str(asset["hair_mask_path"]),
            ),
            anchors_url=_normalize_url(
                self._settings.static_base_url,
                dataset.dataset_code,
                str(asset["anchors_path"]),
            ),
            metadata_url=_normalize_url(
                self._settings.static_base_url,
                dataset.dataset_code,
                str(asset["metadata_path"]),
            ),
            hair_bbox=metadata.get("hair_rgba_bbox"),
            face_mask_url=_normalize_url(
                self._settings.static_base_url,
                dataset.dataset_code,
                metadata.get("face_mask_path"),
            ),
            protect_face_mask_url=_normalize_url(
                self._settings.static_base_url,
                dataset.dataset_code,
                metadata.get("protect_face_mask_path"),
            ),
            render_task=None,
            revision=f"{dataset.dataset_code}:{asset['asset_id']}",
            score=float(score),
            dataset_code=dataset.dataset_code,
            asset_root_path=dataset.asset_root_path,
            metadata_path=str(asset["metadata_path"]),
            asset_row=asset,
            weighted_assets=((asset, 1.0),),
        )

    def _load_dataset(self, dataset_code: str) -> DatasetRecord:
        with self._lock:
            dataset = self._cache.get(dataset_code)
            if dataset is not None:
                return dataset

            asset_root_path = self._settings.static_root / dataset_code
            asset_index_path = asset_root_path / "manifests" / "asset_index_v0.json"
            payload = json.loads(asset_index_path.read_text(encoding="utf-8"))
            items = [
                dict(item)
                for item in payload.get("items", [])
                if isinstance(item, dict) and str(item.get("asset_id") or "")
            ]
            runtime_items = tuple(build_runtime_asset_rows(asset_root_path, items))
            dataset = DatasetRecord(
                dataset_code=dataset_code,
                asset_root_path=asset_root_path,
                runtime_items=runtime_items,
                items_by_id={str(item["asset_id"]): item for item in items},
                metadata_cache={},
                anchors_cache={},
            )
            self._cache[dataset_code] = dataset
            return dataset

    def _load_metadata(self, dataset: DatasetRecord, asset: dict[str, Any]) -> dict[str, Any]:
        asset_id = str(asset["asset_id"])
        if asset_id in dataset.metadata_cache:
            return dataset.metadata_cache[asset_id]
        metadata_path = dataset.asset_root_path / str(asset["metadata_path"])
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        dataset.metadata_cache[asset_id] = metadata
        return metadata

    def _load_anchors(self, dataset: DatasetRecord, asset: dict[str, Any]) -> dict[str, Any]:
        asset_id = str(asset["asset_id"])
        if asset_id in dataset.anchors_cache:
            return dataset.anchors_cache[asset_id]
        anchors_path = dataset.asset_root_path / str(asset["anchors_path"])
        anchors_payload = json.loads(anchors_path.read_text(encoding="utf-8"))
        dataset.anchors_cache[asset_id] = anchors_payload
        return anchors_payload
