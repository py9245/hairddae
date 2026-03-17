from __future__ import annotations

from dataclasses import dataclass
import json
from math import hypot
from pathlib import Path
from threading import Lock
from typing import Any

from app.config import Settings
from app.models import FeatureMessageModel
from app.render import build_render_task


def _normalize_url(base_url: str, dataset_code: str, relative_path: str | None) -> str | None:
    if not relative_path:
        return None
    return f"{base_url}/{dataset_code}/{relative_path.lstrip('/')}"


def _point_distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    return float(hypot(float(a["x"]) - float(b["x"]), float(a["y"]) - float(b["y"])))


def _derive_geom(feature: FeatureMessageModel) -> dict[str, float]:
    bbox_width = max(1.0, float(feature.face_bbox.w))
    bbox_height = max(1.0, float(feature.face_bbox.h))
    anchors = {name: point.model_dump() for name, point in feature.anchors.items()}
    return {
        "temple_span_norm": _point_distance(anchors["left_temple"], anchors["right_temple"]) / bbox_width,
        "lower_span_norm": _point_distance(anchors["lower_left"], anchors["lower_right"]) / bbox_width,
        "crown_offset_norm": abs(float(anchors["forehead_center"]["y"]) - float(anchors["crown"]["y"])) / bbox_height,
        "face_ratio": (float(feature.face_bbox.w) * float(feature.face_bbox.h))
        / float(feature.image_size.width * feature.image_size.height),
    }


def _retrieval_score(
    feature: FeatureMessageModel,
    asset: "AssetRecord",
    geom: dict[str, float] | None = None,
) -> float:
    resolved_geom = geom if geom is not None else _derive_geom(feature)
    pose = feature.pose
    pose_score = (
        2.6 * abs(pose.yaw_1deg - asset.yaw_1deg)
        + 1.8 * abs(pose.pitch_1deg - asset.pitch_1deg)
        + 1.2 * abs(pose.roll_1deg - asset.roll_1deg)
    )
    geom_score = (
        40.0 * abs(resolved_geom["temple_span_norm"] - asset.temple_span_ratio)
        + 25.0 * abs(resolved_geom["lower_span_norm"] - asset.lower_span_ratio)
        + 18.0 * abs(resolved_geom["crown_offset_norm"] - asset.crown_offset_ratio)
        + 18.0 * abs(resolved_geom["face_ratio"] - asset.face_ratio)
    )
    return round(pose_score + geom_score, 6)


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
class AssetRecord:
    asset_id: str
    pose_key: str
    metadata_path: str
    anchors_path: str
    hair_mask_path: str | None
    yaw_1deg: int
    pitch_1deg: int
    roll_1deg: int
    face_ratio: float
    temple_span_ratio: float
    lower_span_ratio: float
    crown_offset_ratio: float
    approved: bool


@dataclass(frozen=True)
class DatasetRecord:
    dataset_code: str
    items: tuple[AssetRecord, ...]
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
        candidates = [item for item in dataset.items if item.approved] or list(dataset.items)
        if not candidates:
            raise ValueError(f"no selectable assets for dataset {dataset_code}")

        geom = _derive_geom(feature)
        best_asset = min(candidates, key=lambda item: _retrieval_score(feature, item, geom))
        return self._build_bundle(dataset_code, dataset, best_asset, feature, geom=geom)

    def bundle_for_asset(
        self,
        dataset_code: str,
        asset_id: str,
        feature: FeatureMessageModel,
    ) -> AssetBundle:
        dataset = self._load_dataset(dataset_code)
        asset = next((item for item in dataset.items if item.asset_id == asset_id), None)
        if asset is None:
            raise ValueError(f"unknown asset_id {asset_id} for dataset {dataset_code}")
        return self._build_bundle(dataset_code, dataset, asset, feature)

    def _build_bundle(
        self,
        dataset_code: str,
        dataset: DatasetRecord,
        asset: AssetRecord,
        feature: FeatureMessageModel,
        *,
        geom: dict[str, float] | None = None,
    ) -> AssetBundle:
        score = _retrieval_score(feature, asset, geom)
        metadata = self._load_metadata(dataset, asset)
        anchors_payload = self._load_anchors(dataset, asset)
        render_task = build_render_task(
            feature=feature,
            asset_anchors_payload=anchors_payload,
            metadata=metadata,
        )
        return AssetBundle(
            asset_id=asset.asset_id,
            pose_key=asset.pose_key,
            yaw_1deg=asset.yaw_1deg,
            pitch_1deg=asset.pitch_1deg,
            roll_1deg=asset.roll_1deg,
            hair_rgba_path=(
                None
                if metadata.get("hair_rgba_path") in (None, "")
                else self._settings.static_root / dataset_code / str(metadata["hair_rgba_path"])
            ),
            hair_rgba_url=_normalize_url(
                self._settings.static_base_url,
                dataset_code,
                metadata.get("hair_rgba_path"),
            ),
            hair_mask_url=_normalize_url(
                self._settings.static_base_url,
                dataset_code,
                asset.hair_mask_path,
            ),
            anchors_url=_normalize_url(
                self._settings.static_base_url,
                dataset_code,
                asset.anchors_path,
            ),
            metadata_url=_normalize_url(
                self._settings.static_base_url,
                dataset_code,
                asset.metadata_path,
            ),
            hair_bbox=metadata.get("hair_rgba_bbox"),
            face_mask_url=_normalize_url(
                self._settings.static_base_url,
                dataset_code,
                metadata.get("face_mask_path"),
            ),
            protect_face_mask_url=_normalize_url(
                self._settings.static_base_url,
                dataset_code,
                metadata.get("protect_face_mask_path"),
            ),
            render_task=None if render_task is None else render_task.to_message(),
            revision=f"{dataset_code}:{asset.asset_id}",
            score=score,
        )

    def _load_dataset(self, dataset_code: str) -> DatasetRecord:
        with self._lock:
            dataset = self._cache.get(dataset_code)
            if dataset is not None:
                return dataset

            asset_index_path = self._settings.static_root / dataset_code / "manifests" / "asset_index_v0.json"
            payload = json.loads(asset_index_path.read_text())
            items: list[AssetRecord] = []
            for item in payload.get("items", []):
                items.append(
                    AssetRecord(
                        asset_id=str(item["asset_id"]),
                        pose_key=str(item["pose_key"]),
                        metadata_path=str(item["metadata_path"]),
                        anchors_path=str(item["anchors_path"]),
                        hair_mask_path=(
                            None if item.get("hair_mask_path") in (None, "") else str(item["hair_mask_path"])
                        ),
                        yaw_1deg=int(item.get("yaw_1deg", 0)),
                        pitch_1deg=int(item.get("pitch_1deg", 0)),
                        roll_1deg=int(item.get("roll_1deg", 0)),
                        face_ratio=float(item.get("face_ratio", 0.0)),
                        temple_span_ratio=float(item.get("temple_span_ratio", 0.0)),
                        lower_span_ratio=float(item.get("lower_span_ratio", 0.0)),
                        crown_offset_ratio=float(item.get("crown_offset_ratio", 0.0)),
                        approved=bool(item.get("approved", False)),
                    )
                )
            dataset = DatasetRecord(
                dataset_code=dataset_code,
                items=tuple(items),
                metadata_cache={},
                anchors_cache={},
            )
            self._cache[dataset_code] = dataset
            return dataset

    def _load_metadata(self, dataset: DatasetRecord, asset: AssetRecord) -> dict[str, Any]:
        if asset.asset_id in dataset.metadata_cache:
            return dataset.metadata_cache[asset.asset_id]
        metadata_path = self._settings.static_root / dataset.dataset_code / asset.metadata_path
        metadata = json.loads(metadata_path.read_text())
        dataset.metadata_cache[asset.asset_id] = metadata
        return metadata

    def _load_anchors(self, dataset: DatasetRecord, asset: AssetRecord) -> dict[str, Any]:
        if asset.asset_id in dataset.anchors_cache:
            return dataset.anchors_cache[asset.asset_id]
        anchors_path = self._settings.static_root / dataset.dataset_code / asset.anchors_path
        anchors_payload = json.loads(anchors_path.read_text())
        dataset.anchors_cache[asset.asset_id] = anchors_payload
        return anchors_payload
