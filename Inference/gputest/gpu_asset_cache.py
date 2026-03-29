from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from hairddae_tools.run_hair_overlay_poc import BUNDLE_PROFILE_LEGACY, load_asset_bundle

try:
    from .gpu_tensor_ops import image_to_tensor, mask_to_tensor
except ImportError:  # pragma: no cover
    from gpu_tensor_ops import image_to_tensor, mask_to_tensor


@dataclass
class GpuLegacyAsset:
    asset_id: str
    anchors: dict[str, Any]
    crop_box: tuple[int, int, int, int]
    hair_luma: float | None
    rgb: Any
    alpha: Any
    hair: Any
    face: Any
    protect_face: Any


class GpuLegacyAssetCache:
    def __init__(self, *, max_items: int = 24) -> None:
        self.max_items = max(4, int(max_items))
        self._cache: OrderedDict[str, GpuLegacyAsset] = OrderedDict()

    def clear(self) -> None:
        self._cache.clear()

    def _make_key(self, asset_root: Path, asset_row: dict[str, Any]) -> str:
        asset_id = str(asset_row.get("asset_id") or asset_row.get("metadata_path") or "").strip()
        return f"{asset_root.resolve()}::{asset_id}"

    @staticmethod
    def _crop_source(bundle: dict[str, Any], key: str) -> np.ndarray:
        image = np.asarray(bundle.get(key), dtype=np.uint8)
        src_x0, src_y0, src_x1, src_y1 = bundle["crop_box"]
        if bool(bundle.get("packed_crop_only")):
            return image
        return image[src_y0:src_y1, src_x0:src_x1]

    def get(self, asset_root: Path, asset_row: dict[str, Any]) -> GpuLegacyAsset:
        key = self._make_key(asset_root, asset_row)
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return cached

        bundle = load_asset_bundle(str(asset_root), asset_row["metadata_path"], BUNDLE_PROFILE_LEGACY)
        rgb = self._crop_source(bundle, "image")
        alpha = self._crop_source(bundle, "alpha")
        hair = self._crop_source(bundle, "hair_mask")
        face = self._crop_source(bundle, "face_mask") if bundle.get("face_mask") is not None else np.zeros_like(alpha)
        protect_face = (
            self._crop_source(bundle, "protect_face_mask")
            if bundle.get("protect_face_mask") is not None
            else np.zeros_like(alpha)
        )

        asset = GpuLegacyAsset(
            asset_id=str(asset_row.get("asset_id") or bundle.get("metadata_path") or ""),
            anchors=dict(bundle["anchors"]),
            crop_box=tuple(int(value) for value in bundle["crop_box"]),
            hair_luma=bundle.get("hair_luma"),
            rgb=image_to_tensor(rgb),
            alpha=mask_to_tensor(alpha),
            hair=mask_to_tensor(hair),
            face=mask_to_tensor(face),
            protect_face=mask_to_tensor(protect_face),
        )
        self._cache[key] = asset
        self._cache.move_to_end(key)
        while len(self._cache) > self.max_items:
            self._cache.popitem(last=False)
        return asset
