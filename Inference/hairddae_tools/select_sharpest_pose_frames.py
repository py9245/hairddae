#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path

import cv2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Select the sharpest frames inside each rounded yaw/pitch/roll pose bucket."
    )
    parser.add_argument("--selected-pose-json", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--top-k", type=int, default=1)
    return parser.parse_args()


def sharpness_score(image_path: Path) -> float:
    image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Failed to read image: {image_path}")
    return float(cv2.Laplacian(image, cv2.CV_64F).var())


def pose_name(item: dict) -> str:
    angles = item["angles_1deg"]
    return f"yaw{angles['yaw']:+03d}_pitch{angles['pitch']:+03d}_roll{angles['roll']:+03d}"


def main() -> None:
    args = parse_args()
    selected_pose_json = Path(args.selected_pose_json)
    output_dir = Path(args.output_dir)
    top_k = args.top_k

    data = json.loads(selected_pose_json.read_text(encoding="utf-8"))
    buckets: dict[str, list[dict]] = defaultdict(list)
    for item in data["items"]:
        buckets[pose_name(item)].append(item)

    output_dir.mkdir(parents=True, exist_ok=True)
    selected_dir = output_dir / "images"
    selected_dir.mkdir(parents=True, exist_ok=True)

    summary_items = []
    total_selected = 0
    for bucket_name, items in buckets.items():
        scored = []
        for item in items:
            image_path = Path(item["selected_frame_path"])
            score = sharpness_score(image_path)
            scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)

        bucket_dir = selected_dir / bucket_name
        bucket_dir.mkdir(parents=True, exist_ok=True)
        kept = []
        for rank, (score, item) in enumerate(scored[:top_k], start=1):
            src = Path(item["selected_frame_path"])
            dst = bucket_dir / src.name
            if not dst.exists():
                os.link(src, dst)
            kept.append(
                {
                    "rank": rank,
                    "sharpness": round(score, 4),
                    "frame_index": item["frame_index"],
                    "file": item["file"],
                    "selected_frame_path": item["selected_frame_path"],
                }
            )
            total_selected += 1

        summary_items.append(
            {
                "pose": bucket_name,
                "count_in_bucket": len(items),
                "kept": kept,
            }
        )

    summary_items.sort(key=lambda x: x["pose"])
    summary = {
        "pose_bucket_count": len(summary_items),
        "top_k": top_k,
        "selected_images": total_selected,
    }
    (output_dir / "summary.json").write_text(
        json.dumps({"summary": summary, "items": summary_items}, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"summary": summary, "output_dir": str(output_dir.resolve())}, ensure_ascii=False))


if __name__ == "__main__":
    main()
