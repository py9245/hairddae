from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any

from app.models import FeatureMessageModel


HAIRDDAE_TOOLS_DIR = Path(__file__).resolve().parents[1] / "hairddae_tools"
if str(HAIRDDAE_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(HAIRDDAE_TOOLS_DIR))

from run_hair_overlay_poc import (  # type: ignore[import-not-found]
    asset_crop_edge_risk,
    asset_rank_score,
    compose_overlay_blend_frame,
    pose_distance,
    select_best_assets,
)


@dataclass(frozen=True)
class HairddaeSelectionResult:
    selected_asset: dict[str, Any]
    score: float
    ranked_assets: tuple[tuple[dict[str, Any], float], ...]


def feature_to_user_row(feature: FeatureMessageModel) -> dict[str, Any]:
    image_size = feature.image_size.model_dump()
    face_bbox = feature.face_bbox.model_dump()
    image_area = max(1, int(image_size["width"]) * int(image_size["height"]))
    return {
        "pose": feature.pose.model_dump(),
        "anchors": {
            name: point.model_dump()
            for name, point in feature.anchors.items()
        },
        "image_size": image_size,
        "face_bbox": face_bbox,
        "face_ratio": (float(face_bbox["w"]) * float(face_bbox["h"])) / float(image_area),
    }


def score_asset_for_feature(feature: FeatureMessageModel, asset_row: dict[str, Any]) -> float:
    return float(asset_rank_score(feature_to_user_row(feature), asset_row))


def _asset_preference_key(asset_row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        0 if asset_row.get("approved") else 1,
        -float(asset_row.get("quality_score") or 0.0),
        float(asset_row.get("naturalness_risk_v1") or 0.0),
        len(asset_row.get("naturalness_failure_tags_v1") or []),
        len(asset_row.get("critical_failure_tags") or []),
        len(asset_row.get("failure_tags") or []),
        -float(asset_row.get("hair_mean_confidence") or 0.0),
        str(asset_row.get("asset_id") or ""),
    )


def _crop_risk_bucket(risk_score: float) -> int:
    if risk_score <= 0.18:
        return 0
    if risk_score <= 0.30:
        return 1
    if risk_score <= 0.45:
        return 2
    return 3


def _asset_crop_risk(asset_root: Path, asset_row: dict[str, Any]) -> float:
    cached_risk = asset_row.get("_crop_edge_risk")
    if cached_risk is not None:
        return float(cached_risk)

    metadata_path = str(asset_row.get("metadata_path") or "")
    if not metadata_path:
        asset_row["_crop_edge_risk"] = 0.0
        return 0.0

    try:
        risk_score = float(asset_crop_edge_risk(str(asset_root), metadata_path))
    except Exception:
        risk_score = 0.0
    asset_row["_crop_edge_risk"] = round(risk_score, 6)
    return float(asset_row["_crop_edge_risk"])


def _choose_pose_representative(asset_root: Path, pose_rows: list[dict[str, Any]]) -> dict[str, Any]:
    ranked_rows = sorted(pose_rows, key=_asset_preference_key)
    if len(ranked_rows) <= 1:
        return ranked_rows[0]

    top_rows = ranked_rows[: min(len(ranked_rows), 4)]
    top_row = top_rows[0]
    top_risk = _asset_crop_risk(asset_root, top_row)
    top_bucket = _crop_risk_bucket(top_risk)
    if top_bucket <= 1:
        return top_row

    safer_candidates: list[tuple[int, float, int, float, dict[str, Any]]] = []
    for index, row in enumerate(top_rows[1:], start=1):
        risk_score = _asset_crop_risk(asset_root, row)
        risk_bucket = _crop_risk_bucket(risk_score)
        if risk_bucket >= top_bucket:
            continue
        if risk_score > top_risk - 0.08:
            continue
        safer_candidates.append(
            (
                risk_bucket,
                risk_score,
                index,
                -float(row.get("quality_score") or 0.0),
                row,
            )
        )

    if not safer_candidates:
        return top_row

    safer_candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3], str(item[4].get("asset_id") or "")))
    return safer_candidates[0][4]


def _pose_representatives(asset_root: Path, asset_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_pose_key: dict[str, list[dict[str, Any]]] = {}
    for row in asset_rows:
        pose_key = str(row.get("pose_key") or "")
        if not pose_key:
            continue
        by_pose_key.setdefault(pose_key, []).append(row)

    representatives = [
        _choose_pose_representative(asset_root, pose_rows)
        for pose_rows in by_pose_key.values()
    ]
    return sorted(
        representatives,
        key=lambda row: (
            int(row.get("pitch_1deg") or 0),
            int(row.get("yaw_1deg") or 0),
            int(row.get("roll_1deg") or 0),
            str(row.get("asset_id") or ""),
        ),
    )


def _is_extreme_downward_face_overlap_asset(asset_row: dict[str, Any]) -> bool:
    pitch_value = int(asset_row.get("pitch_1deg") or 0)
    naturalness_risk = float(asset_row.get("naturalness_risk_v1") or 0.0)
    face_overlap_ratio = float(asset_row.get("face_overlap_ratio") or 0.0)
    naturalness_tags = set(asset_row.get("naturalness_failure_tags_v1") or [])
    quality_status = str(asset_row.get("quality_status") or "")
    if pitch_value < 16:
        return False
    if "face_skin_overlap_risk" in naturalness_tags or "downward_face_cover_risk" in naturalness_tags:
        return True
    if pitch_value >= 24:
        if quality_status != "approved":
            return True
        return naturalness_risk >= 0.05 or face_overlap_ratio >= 0.01
    if pitch_value >= 20:
        if quality_status != "approved" and (naturalness_risk >= 0.04 or face_overlap_ratio >= 0.008):
            return True
        return naturalness_risk >= 0.055 or face_overlap_ratio >= 0.012
    if quality_status != "approved" and (naturalness_risk >= 0.05 or face_overlap_ratio >= 0.01):
        return True
    return False


def build_runtime_asset_rows(asset_root: Path, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blacklisted_asset_ids: set[str] = set()
    blacklist_path = asset_root / "manifests" / "runtime_asset_blacklist.json"
    if blacklist_path.is_file():
        payload = json.loads(blacklist_path.read_text(encoding="utf-8"))
        blacklisted_asset_ids = {
            str(asset_id).strip()
            for asset_id in payload.get("asset_ids", [])
            if str(asset_id).strip()
        }

    all_assets = [
        dict(item)
        for item in items
        if isinstance(item, dict) and str(item.get("asset_id") or "")
    ]
    if blacklisted_asset_ids:
        all_assets = [
            row
            for row in all_assets
            if str(row.get("asset_id") or "") not in blacklisted_asset_ids
        ]

    runtime_source = [
        row
        for row in all_assets
        if str(row.get("quality_status") or "") != "rejected"
        and not bool(row.get("has_critical_failures"))
        and not bool(row.get("has_critical_naturalness_failures"))
        and not _is_extreme_downward_face_overlap_asset(row)
    ]
    if not runtime_source:
        runtime_source = all_assets
    return _pose_representatives(asset_root, runtime_source)


def _prefer_representative_candidate(
    representative_asset_id: str | None,
    ranked_assets: list[tuple[dict[str, Any], float]],
    best_asset: dict[str, Any],
    best_score: float,
) -> tuple[dict[str, Any], float]:
    if not representative_asset_id:
        return best_asset, best_score

    for asset_row, score in ranked_assets[:8]:
        if str(asset_row.get("asset_id") or "") != representative_asset_id:
            continue
        if float(score) <= best_score + 2.0:
            return asset_row, float(score)
        break
    return best_asset, best_score


def _prefer_frontal_safe_candidate(
    user_row: dict[str, Any],
    ranked_assets: list[tuple[dict[str, Any], float]],
    best_asset: dict[str, Any],
    best_score: float,
) -> tuple[dict[str, Any], float]:
    user_yaw = int(user_row["pose"]["yaw_1deg"])
    user_abs_yaw = abs(user_yaw)
    if user_abs_yaw > 12:
        return best_asset, best_score

    best_abs_yaw = abs(int(best_asset.get("yaw_1deg") or 0))
    best_yaw_gap = abs(user_yaw - int(best_asset.get("yaw_1deg") or 0))
    if best_abs_yaw <= 10 and best_yaw_gap <= 5:
        return best_asset, best_score

    allowed_gap = 3.2
    max_asset_abs_yaw = min(10, user_abs_yaw + 4)
    safer_candidates: list[tuple[int, int, float, float, dict[str, Any]]] = []
    for asset_row, score in ranked_assets[:8]:
        asset_yaw = int(asset_row.get("yaw_1deg") or 0)
        asset_abs_yaw = abs(asset_yaw)
        yaw_gap = abs(user_yaw - asset_yaw)
        if asset_abs_yaw > max_asset_abs_yaw or yaw_gap > 6:
            continue
        if float(score) > best_score + allowed_gap:
            continue
        safer_candidates.append(
            (
                asset_abs_yaw,
                yaw_gap,
                float(score),
                float(pose_distance(user_row["pose"], asset_row)),
                asset_row,
            )
        )

    if not safer_candidates:
        return best_asset, best_score

    safer_candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3], str(item[4].get("asset_id") or "")))
    chosen_candidate = safer_candidates[0]
    return chosen_candidate[4], chosen_candidate[2]


def _prefer_render_safe_candidate(
    asset_root: Path,
    user_row: dict[str, Any],
    ranked_assets: list[tuple[dict[str, Any], float]],
    best_asset: dict[str, Any],
    best_score: float,
) -> tuple[dict[str, Any], float]:
    best_risk = _asset_crop_risk(asset_root, best_asset)
    best_bucket = _crop_risk_bucket(best_risk)
    if best_bucket <= 0:
        return best_asset, best_score

    allowed_gap = 3.8
    if best_bucket >= 2:
        allowed_gap += 1.0

    safer_candidates: list[tuple[int, float, float, float, dict[str, Any]]] = []
    for asset_row, score in ranked_assets[:5]:
        risk_score = _asset_crop_risk(asset_root, asset_row)
        risk_bucket = _crop_risk_bucket(risk_score)
        if risk_bucket >= best_bucket:
            continue
        if float(score) > best_score + allowed_gap:
            continue
        if risk_bucket > 0 and risk_score > best_risk - 0.08:
            continue
        safer_candidates.append(
            (
                risk_bucket,
                risk_score,
                float(score),
                float(pose_distance(user_row["pose"], asset_row)),
                asset_row,
            )
        )

    if not safer_candidates:
        return best_asset, best_score

    safer_candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3], str(item[4].get("asset_id") or "")))
    chosen_candidate = safer_candidates[0]
    return chosen_candidate[4], chosen_candidate[2]


def select_runtime_asset(
    asset_root: Path,
    asset_rows: list[dict[str, Any]],
    feature: FeatureMessageModel,
    representative_asset_id: str | None = None,
) -> HairddaeSelectionResult:
    user_row = feature_to_user_row(feature)
    ranked_assets = list(select_best_assets(user_row, asset_rows, limit=10))
    if not ranked_assets:
        raise RuntimeError(f"No candidate assets available in {asset_root}")

    best_asset, best_score = ranked_assets[0]
    best_asset, best_score = _prefer_representative_candidate(
        representative_asset_id,
        ranked_assets,
        best_asset,
        float(best_score),
    )
    best_asset, best_score = _prefer_frontal_safe_candidate(
        user_row,
        ranked_assets,
        best_asset,
        float(best_score),
    )
    best_asset, best_score = _prefer_render_safe_candidate(
        asset_root,
        user_row,
        ranked_assets,
        best_asset,
        float(best_score),
    )
    return HairddaeSelectionResult(
        selected_asset=best_asset,
        score=float(best_score),
        ranked_assets=tuple((asset_row, float(score)) for asset_row, score in ranked_assets),
    )
