#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a representative smoke subset from a pose bank selected_pose.json."
    )
    parser.add_argument("--pose-json", required=True, help="selected_pose.json path")
    parser.add_argument("--output-dir", required=True, help="Output directory for the smoke subset")
    parser.add_argument("--link-mode", choices=["copy", "symlink"], default="copy")
    parser.add_argument("--target-count", type=int, default=96)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def sanitize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for row in rows:
        if not row.get("selected_frame_path"):
            continue
        if not row.get("angles_1deg"):
            continue
        sanitized.append(row)
    return sanitized


def pose_bucket(row: dict[str, Any]) -> str:
    angles = row["angles_1deg"]
    yaw = int(angles["yaw"])
    pitch = int(angles["pitch"])
    roll = int(angles["roll"])
    abs_yaw = abs(yaw)
    abs_roll = abs(roll)

    if pitch >= 24 and abs_yaw <= 10:
        return "down_extreme"
    if pitch >= 16 and abs_yaw <= 12:
        return "down_mid"
    if pitch <= -16 and abs_yaw <= 12:
        return "up_extreme"
    if pitch <= -10 and abs_yaw <= 12:
        return "up_mid"
    if yaw <= -30:
        return "left_extreme"
    if yaw <= -18:
        return "left_side"
    if yaw >= 30:
        return "right_extreme"
    if yaw >= 18:
        return "right_side"
    if abs_roll >= 10:
        return "roll_heavy"
    return "frontal"


def row_score(row: dict[str, Any]) -> tuple[float, float, float]:
    metrics = row.get("quality_metrics") or {}
    score = float(metrics.get("pose_selection_score") or 0.0)
    sharpness = float(metrics.get("sharpness") or 0.0)
    face_ratio = float(row.get("face_ratio") or 0.0)
    return (score, sharpness, face_ratio)


def link_or_copy(src: Path, dst: Path, mode: str) -> None:
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    if mode == "copy":
        shutil.copy2(src, dst)
    else:
        dst.symlink_to(src)


def write_subset(output_dir: Path, rows: list[dict[str, Any]], summary: dict[str, Any], link_mode: str) -> None:
    selected_dir = output_dir / "selected_frames"
    selected_dir.mkdir(parents=True, exist_ok=True)

    output_rows: list[dict[str, Any]] = []
    for row in rows:
        src = Path(row["selected_frame_path"]).resolve()
        dst = selected_dir / src.name
        link_or_copy(src, dst, link_mode)
        subset_row = dict(row)
        subset_row["selected_frame_path"] = str(dst.resolve())
        output_rows.append(subset_row)

    (output_dir / "selected_pose.json").write_text(
        json.dumps({"summary": summary, "items": output_rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    pose_json_path = Path(args.pose_json).resolve()
    output_dir = Path(args.output_dir).resolve()

    if output_dir.exists():
        if not args.overwrite:
            raise SystemExit(f"Output dir already exists: {output_dir}. Use --overwrite to replace it.")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = json.loads(pose_json_path.read_text(encoding="utf-8"))
    rows = sanitize_rows(payload.get("items", []))
    if not rows:
        raise SystemExit("No valid rows found in pose json.")

    bucketed: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        bucketed[pose_bucket(row)].append(row)

    for bucket_rows in bucketed.values():
        bucket_rows.sort(key=row_score, reverse=True)

    preferred_order = [
        "frontal",
        "left_side",
        "right_side",
        "left_extreme",
        "right_extreme",
        "down_mid",
        "down_extreme",
        "up_mid",
        "up_extreme",
        "roll_heavy",
    ]

    selected: list[dict[str, Any]] = []
    selected_keys: set[tuple[int, int, int]] = set()

    # Round-robin over representative pose buckets to preserve coverage.
    progress = True
    while progress and len(selected) < args.target_count:
        progress = False
        for bucket_name in preferred_order:
            bucket_rows = bucketed.get(bucket_name, [])
            while bucket_rows:
                candidate = bucket_rows.pop(0)
                angles = candidate["angles_1deg"]
                pose_key = (int(angles["yaw"]), int(angles["pitch"]), int(angles["roll"]))
                if pose_key in selected_keys:
                    continue
                selected.append(candidate)
                selected_keys.add(pose_key)
                progress = True
                break
            if len(selected) >= args.target_count:
                break

    if len(selected) < args.target_count:
        remaining = sorted(rows, key=row_score, reverse=True)
        for candidate in remaining:
            if len(selected) >= args.target_count:
                break
            angles = candidate["angles_1deg"]
            pose_key = (int(angles["yaw"]), int(angles["pitch"]), int(angles["roll"]))
            if pose_key in selected_keys:
                continue
            selected.append(candidate)
            selected_keys.add(pose_key)

    selected.sort(key=lambda row: int(row.get("frame_index", 0)))
    bucket_counts: dict[str, int] = defaultdict(int)
    for row in selected:
        bucket_counts[pose_bucket(row)] += 1

    source_summary = payload.get("summary", {})
    summary = {
        "source_pose_json": str(pose_json_path),
        "source_video": source_summary.get("video"),
        "target_count": args.target_count,
        "selected_frames": len(selected),
        "link_mode": args.link_mode,
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "coverage": {
            "yaw_min": min(int(row["angles_1deg"]["yaw"]) for row in selected),
            "yaw_max": max(int(row["angles_1deg"]["yaw"]) for row in selected),
            "pitch_min": min(int(row["angles_1deg"]["pitch"]) for row in selected),
            "pitch_max": max(int(row["angles_1deg"]["pitch"]) for row in selected),
            "roll_min": min(int(row["angles_1deg"]["roll"]) for row in selected),
            "roll_max": max(int(row["angles_1deg"]["roll"]) for row in selected),
        },
        "selection_strategy": "round_robin_pose_bucket_with_quality_ranking",
    }

    write_subset(output_dir, selected, summary, args.link_mode)
    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "selected_frames": len(selected),
                "bucket_counts": dict(sorted(bucket_counts.items())),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
