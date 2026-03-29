from __future__ import annotations

from app.angle_priority_selection import (
    is_angle_priority_pose_compatible,
    rank_assets_by_angle_priority,
    shortlist_assets_by_angle_priority,
    should_release_current_asset,
)


def build_asset(
    asset_id: str,
    *,
    yaw: int,
    pitch: int = 0,
    roll: int = 0,
) -> dict[str, int | str]:
    return {
        "asset_id": asset_id,
        "yaw_1deg": yaw,
        "pitch_1deg": pitch,
        "roll_1deg": roll,
    }


def test_rank_assets_by_angle_priority_prefers_closer_yaw_over_base_score() -> None:
    user_row = {"pose": {"yaw_1deg": -22, "pitch_1deg": 1, "roll_1deg": 0}}
    closer_asset = build_asset("closer", yaw=-20, pitch=0)
    wrong_sign_asset = build_asset("wrong-sign", yaw=18, pitch=1)

    ranked_assets = rank_assets_by_angle_priority(
        user_row,
        [wrong_sign_asset, closer_asset],
        limit=2,
        asset_score_fn=lambda _user_row, asset_row: 0.1 if asset_row["asset_id"] == "wrong-sign" else 4.0,
        asset_crop_risk_fn=lambda _asset_row: 0.0,
    )

    assert [asset_row["asset_id"] for asset_row, _ in ranked_assets] == ["closer", "wrong-sign"]


def test_should_release_current_asset_for_meaningful_yaw_improvement() -> None:
    user_row = {"pose": {"yaw_1deg": 20, "pitch_1deg": 8, "roll_1deg": 0}}
    current_asset = build_asset("current", yaw=8, pitch=7)
    best_asset = build_asset("best", yaw=19, pitch=9)

    assert should_release_current_asset(True, user_row, current_asset, best_asset) is True


def test_should_release_current_asset_stays_disabled_without_flag() -> None:
    user_row = {"pose": {"yaw_1deg": 20, "pitch_1deg": 8, "roll_1deg": 0}}
    current_asset = build_asset("current", yaw=8, pitch=7)
    best_asset = build_asset("best", yaw=19, pitch=9)

    assert should_release_current_asset(False, user_row, current_asset, best_asset) is False


def test_angle_priority_pose_compatibility_rejects_safer_but_wrong_pitch_side_asset() -> None:
    user_row = {"pose": {"yaw_1deg": -33, "pitch_1deg": 5, "roll_1deg": -8}}
    best_asset = build_asset("best", yaw=-31, pitch=6, roll=-8)
    wrong_pitch_asset = build_asset("wrong-pitch", yaw=-31, pitch=-15, roll=10)

    assert is_angle_priority_pose_compatible(True, user_row, best_asset, wrong_pitch_asset) is False


def test_angle_priority_pose_compatibility_accepts_nearby_side_candidate() -> None:
    user_row = {"pose": {"yaw_1deg": -28, "pitch_1deg": 6, "roll_1deg": -5}}
    best_asset = build_asset("best", yaw=-28, pitch=6, roll=-5)
    safe_candidate = build_asset("safe", yaw=-27, pitch=8, roll=-4)

    assert is_angle_priority_pose_compatible(True, user_row, best_asset, safe_candidate) is True


def test_shortlist_assets_by_angle_priority_prefers_pose_matches_over_input_order() -> None:
    user_row = {"pose": {"yaw_1deg": -29, "pitch_1deg": 5, "roll_1deg": -7}}
    wrong_pitch_assets = [
        build_asset(f"wrong-{index}", yaw=-29, pitch=-15, roll=10)
        for index in range(12)
    ]
    good_asset = build_asset("good", yaw=-30, pitch=6, roll=-8)

    shortlist = shortlist_assets_by_angle_priority(
        user_row,
        wrong_pitch_assets + [good_asset],
        limit=5,
    )

    assert shortlist[0]["asset_id"] == "good"
