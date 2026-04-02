from __future__ import annotations

from typing import Any, Callable


def _pose_axis_gap(user_value: int, asset_value: int) -> int:
    return abs(int(user_value) - int(asset_value))


def _pose_sign(value: int) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def angle_priority_candidate_key(
    user_row: dict[str, Any],
    asset_row: dict[str, Any],
    *,
    base_score: float,
    crop_risk: float,
) -> tuple[float | int | str, ...]:
    user_pose = user_row.get("pose") or {}
    user_yaw = int(user_pose.get("yaw_1deg") or 0)
    user_pitch = int(user_pose.get("pitch_1deg") or 0)
    user_roll = int(user_pose.get("roll_1deg") or 0)
    asset_yaw = int(asset_row.get("yaw_1deg") or 0)
    asset_pitch = int(asset_row.get("pitch_1deg") or 0)
    asset_roll = int(asset_row.get("roll_1deg") or 0)

    user_abs_yaw = abs(user_yaw)
    asset_abs_yaw = abs(asset_yaw)
    yaw_gap = _pose_axis_gap(user_yaw, asset_yaw)
    pitch_gap = _pose_axis_gap(user_pitch, asset_pitch)
    roll_gap = _pose_axis_gap(user_roll, asset_roll)

    side_view = user_abs_yaw >= 10
    user_sign = _pose_sign(user_yaw)
    asset_sign = _pose_sign(asset_yaw)
    sign_mismatch = 0
    if side_view and user_sign != 0 and asset_sign not in {0, user_sign}:
        sign_mismatch = 1

    if side_view:
        min_abs_asset_yaw = max(8, user_abs_yaw - 6)
        frontal_deficit = max(0, min_abs_asset_yaw - asset_abs_yaw)
    elif user_abs_yaw >= 6:
        frontal_deficit = max(0, asset_abs_yaw - (user_abs_yaw + 6))
    else:
        frontal_deficit = 0

    yaw_bucket = max(0, yaw_gap - (3 if side_view else 2))
    if abs(user_pitch) >= 12:
        pitch_bucket = max(0, pitch_gap - 2)
    elif abs(user_pitch) >= 6:
        pitch_bucket = max(0, pitch_gap - 3)
    else:
        pitch_bucket = max(0, pitch_gap - 4)

    return (
        sign_mismatch,
        frontal_deficit,
        yaw_bucket,
        pitch_bucket,
        yaw_gap,
        pitch_gap,
        roll_gap,
        float(base_score),
        float(crop_risk),
        str(asset_row.get("asset_id") or ""),
    )


def rank_assets_by_angle_priority(
    user_row: dict[str, Any],
    candidate_assets: list[dict[str, Any]],
    *,
    limit: int,
    asset_score_fn: Callable[[dict[str, Any], dict[str, Any]], float],
    asset_crop_risk_fn: Callable[[dict[str, Any]], float],
) -> list[tuple[dict[str, Any], float]]:
    ranked_assets: list[tuple[tuple[float | int | str, ...], dict[str, Any], float]] = []
    for asset_row in candidate_assets:
        base_score = float(asset_score_fn(user_row, asset_row))
        ranked_assets.append(
            (
                angle_priority_candidate_key(
                    user_row,
                    asset_row,
                    base_score=base_score,
                    crop_risk=float(asset_crop_risk_fn(asset_row)),
                ),
                asset_row,
                base_score,
            )
        )
    ranked_assets.sort(key=lambda item: item[0])
    return [(asset_row, score) for _, asset_row, score in ranked_assets[:limit]]


def shortlist_assets_by_angle_priority(
    user_row: dict[str, Any],
    candidate_assets: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    ranked_assets = sorted(
        candidate_assets,
        key=lambda asset_row: angle_priority_candidate_key(
            user_row,
            asset_row,
            base_score=0.0,
            crop_risk=0.0,
        ),
    )
    return ranked_assets[:limit]


def should_release_current_asset(
    angle_priority_enabled: bool,
    user_row: dict[str, Any],
    current_asset: dict[str, Any],
    best_asset: dict[str, Any],
) -> bool:
    if not angle_priority_enabled:
        return False

    user_pose = user_row.get("pose") or {}
    user_yaw = int(user_pose.get("yaw_1deg") or 0)
    if abs(user_yaw) < 10:
        return False

    current_yaw_gap = _pose_axis_gap(user_yaw, int(current_asset.get("yaw_1deg") or 0))
    best_yaw_gap = _pose_axis_gap(user_yaw, int(best_asset.get("yaw_1deg") or 0))
    if best_yaw_gap + 2 <= current_yaw_gap:
        return True

    user_pitch = int(user_pose.get("pitch_1deg") or 0)
    current_pitch_gap = _pose_axis_gap(user_pitch, int(current_asset.get("pitch_1deg") or 0))
    best_pitch_gap = _pose_axis_gap(user_pitch, int(best_asset.get("pitch_1deg") or 0))
    return abs(user_yaw) >= 18 and best_yaw_gap + 1 <= current_yaw_gap and best_pitch_gap <= current_pitch_gap + 2


def is_angle_priority_pose_compatible(
    angle_priority_enabled: bool,
    user_row: dict[str, Any],
    best_asset: dict[str, Any],
    candidate_asset: dict[str, Any],
) -> bool:
    if not angle_priority_enabled:
        return True

    user_pose = user_row.get("pose") or {}
    user_yaw = int(user_pose.get("yaw_1deg") or 0)
    user_pitch = int(user_pose.get("pitch_1deg") or 0)
    user_abs_yaw = abs(user_yaw)
    side_view = user_abs_yaw >= 10

    best_yaw = int(best_asset.get("yaw_1deg") or 0)
    candidate_yaw = int(candidate_asset.get("yaw_1deg") or 0)
    best_pitch = int(best_asset.get("pitch_1deg") or 0)
    candidate_pitch = int(candidate_asset.get("pitch_1deg") or 0)

    best_yaw_gap = _pose_axis_gap(user_yaw, best_yaw)
    candidate_yaw_gap = _pose_axis_gap(user_yaw, candidate_yaw)
    best_pitch_gap = _pose_axis_gap(user_pitch, best_pitch)
    candidate_pitch_gap = _pose_axis_gap(user_pitch, candidate_pitch)

    user_sign = _pose_sign(user_yaw)
    candidate_sign = _pose_sign(candidate_yaw)
    if side_view and user_sign != 0 and candidate_sign not in {0, user_sign}:
        return False

    if side_view:
        allowed_extra_yaw_gap = 1 if user_abs_yaw >= 18 else 2
        if candidate_yaw_gap > best_yaw_gap + allowed_extra_yaw_gap:
            return False
        min_abs_asset_yaw = max(8, user_abs_yaw - 8)
        if abs(candidate_yaw) < min_abs_asset_yaw <= abs(best_yaw):
            return False
    elif candidate_yaw_gap > best_yaw_gap + 3:
        return False

    allowed_extra_pitch_gap = 2 if abs(user_pitch) >= 12 else 3 if side_view else 5
    if candidate_pitch_gap > best_pitch_gap + allowed_extra_pitch_gap:
        return False

    return True
