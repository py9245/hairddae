#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


COARSE_YAW = [-45, -30, -15, 0, 15, 30, 45]
COARSE_PITCH = [-45, -30, -15, 0, 15, 30, 45]
COARSE_ROLL = [-30, -15, 0, 15, 30]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build coarse-245 and dense-2000 pose targets.")
    parser.add_argument("--seed-meta", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--count", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--yaw-values", default="")
    parser.add_argument("--pitch-values", default="")
    parser.add_argument("--roll-values", default="")
    parser.add_argument("--dense-yaw-min", type=int, default=None)
    parser.add_argument("--dense-yaw-max", type=int, default=None)
    parser.add_argument("--dense-pitch-min", type=int, default=None)
    parser.add_argument("--dense-pitch-max", type=int, default=None)
    parser.add_argument("--dense-roll-min", type=int, default=None)
    parser.add_argument("--dense-roll-max", type=int, default=None)
    return parser.parse_args()


def parse_axis_values(raw: str, fallback: list[int]) -> list[int]:
    if not raw.strip():
        return fallback
    values = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        values.append(int(token))
    if not values:
        return fallback
    return sorted(set(values))


def pose_region(yaw: int, pitch: int, roll: int) -> str:
    if abs(yaw) <= 30 and abs(pitch) <= 30 and abs(roll) <= 15:
        return "core"
    if abs(yaw) >= 40 or abs(pitch) >= 40 or abs(roll) >= 25:
        return "outer"
    return "transition"


def build_reference245(
    yaw_values: list[int], pitch_values: list[int], roll_values: list[int]
) -> list[dict]:
    targets = []
    for pitch in pitch_values:
        for yaw in yaw_values:
            for roll in roll_values:
                targets.append(
                    {
                        "target_pitch": pitch,
                        "target_yaw": yaw,
                        "target_roll": roll,
                        "region": pose_region(yaw, pitch, roll),
                        "source": "coarse245",
                    }
                )
    return targets


def sample_dense_targets(
    total_count: int,
    rng: random.Random,
    yaw_values: list[int],
    pitch_values: list[int],
    roll_values: list[int],
    dense_yaw_min: int,
    dense_yaw_max: int,
    dense_pitch_min: int,
    dense_pitch_max: int,
    dense_roll_min: int,
    dense_roll_max: int,
) -> list[dict]:
    coarse = build_reference245(yaw_values, pitch_values, roll_values)
    coarse_set = {
        (item["target_pitch"], item["target_yaw"], item["target_roll"])
        for item in coarse
    }
    additional_needed = max(0, total_count - len(coarse))
    additional: list[dict] = []
    seen = set(coarse_set)

    core_candidates = []
    transition_candidates = []
    outer_candidates = []
    for pitch in range(dense_pitch_min, dense_pitch_max + 1):
        for yaw in range(dense_yaw_min, dense_yaw_max + 1):
            for roll in range(dense_roll_min, dense_roll_max + 1):
                key = (pitch, yaw, roll)
                if key in seen:
                    continue
                region = pose_region(yaw, pitch, roll)
                payload = {
                    "target_pitch": pitch,
                    "target_yaw": yaw,
                    "target_roll": roll,
                    "region": region,
                    "source": "dense2000",
                }
                if region == "core":
                    core_candidates.append(payload)
                elif region == "outer":
                    outer_candidates.append(payload)
                else:
                    transition_candidates.append(payload)

    rng.shuffle(core_candidates)
    rng.shuffle(transition_candidates)
    rng.shuffle(outer_candidates)

    core_quota = int(round(additional_needed * 0.60))
    outer_quota = int(round(additional_needed * 0.30))
    transition_quota = additional_needed - core_quota - outer_quota

    selected = (
        core_candidates[:core_quota]
        + outer_candidates[:outer_quota]
        + transition_candidates[:transition_quota]
    )
    if len(selected) < additional_needed:
        leftovers = (
            core_candidates[core_quota:]
            + transition_candidates[transition_quota:]
            + outer_candidates[outer_quota:]
        )
        selected.extend(leftovers[: additional_needed - len(selected)])

    return coarse + selected[:additional_needed]


def main() -> None:
    args = parse_args()
    seed_meta = json.loads(Path(args.seed_meta).read_text(encoding="utf-8"))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)
    yaw_values = parse_axis_values(args.yaw_values, COARSE_YAW)
    pitch_values = parse_axis_values(args.pitch_values, COARSE_PITCH)
    roll_values = parse_axis_values(args.roll_values, COARSE_ROLL)
    coarse = build_reference245(yaw_values, pitch_values, roll_values)
    dense = sample_dense_targets(
        args.count,
        rng,
        yaw_values,
        pitch_values,
        roll_values,
        args.dense_yaw_min if args.dense_yaw_min is not None else min(yaw_values),
        args.dense_yaw_max if args.dense_yaw_max is not None else max(yaw_values),
        args.dense_pitch_min if args.dense_pitch_min is not None else min(pitch_values),
        args.dense_pitch_max if args.dense_pitch_max is not None else max(pitch_values),
        args.dense_roll_min if args.dense_roll_min is not None else min(roll_values),
        args.dense_roll_max if args.dense_roll_max is not None else max(roll_values),
    )
    seed_pose = seed_meta["seed_pose_1deg"]

    def add_ref(targets: list[dict]) -> list[dict]:
        return [
            {
                **item,
                "reference_pitch": seed_pose["pitch"],
                "reference_yaw": seed_pose["yaw"],
                "reference_roll": seed_pose["roll"],
                "reference_file": "seed_512.png",
            }
            for item in targets
        ]

    coarse_payload = {
        "summary": {
            "count": len(coarse),
            "description": "7x7x5 coarse reference lattice",
        },
        "targets": add_ref(coarse),
    }
    dense_payload = {
        "summary": {
            "count": len(dense),
            "description": "2000-view dense sampled bank with coarse lattice included",
        },
        "targets": add_ref(dense),
    }

    (output_dir / "targets_245.json").write_text(
        json.dumps(coarse_payload, indent=2),
        encoding="utf-8",
    )
    (output_dir / "targets_2000.json").write_text(
        json.dumps(dense_payload, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "targets_245": len(coarse),
                "targets_2000": len(dense),
                "seed_pose_1deg": seed_pose,
                "yaw_values": yaw_values,
                "pitch_values": pitch_values,
                "roll_values": roll_values,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
