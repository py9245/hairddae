#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize asset index quality and pose-bin coverage.")
    parser.add_argument("--asset-root", required=True)
    parser.add_argument("--output-json", default=None)
    parser.add_argument("--top-k", type=int, default=25)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asset_root = Path(args.asset_root).resolve()
    index_path = asset_root / "manifests" / "asset_index_v0.json"
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    items: list[dict[str, Any]] = payload.get("items", [])

    status_counts = Counter(str(item.get("quality_status") or "unknown") for item in items)
    naturalness_counts: Counter[str] = Counter()
    failure_counts: Counter[str] = Counter()
    pose_bins: dict[str, dict[str, int]] = defaultdict(lambda: {"approved": 0, "approved_strict": 0, "borderline": 0, "rejected": 0})

    suspicious_approved: list[dict[str, Any]] = []
    fallback_bins: list[dict[str, Any]] = []
    suspicious_approved_by_tag: Counter[str] = Counter()

    for item in items:
        quality_status = str(item.get("quality_status") or "")
        pose_key = str(item.get("pose_key") or "")
        pose_bins[pose_key][quality_status] += 1
        if item.get("approved_strict"):
            pose_bins[pose_key]["approved_strict"] += 1

        for tag in item.get("naturalness_failure_tags_v1") or []:
            naturalness_counts[str(tag)] += 1
        for tag in item.get("failure_tags") or []:
            failure_counts[str(tag)] += 1

        if quality_status == "approved":
            failure_tags = [str(tag) for tag in item.get("failure_tags") or []]
            naturalness_tags = [str(tag) for tag in item.get("naturalness_failure_tags_v1") or []]
            non_wispy_failure_tags = [tag for tag in failure_tags if tag != "wispy_loss_risk"]
            face_overlap_ratio = float(item.get("face_overlap_ratio") or 0.0)
            suspicious = bool(non_wispy_failure_tags) or bool(naturalness_tags) or face_overlap_ratio > 0.003
            if suspicious:
                for tag in non_wispy_failure_tags:
                    suspicious_approved_by_tag[str(tag)] += 1
                for tag in naturalness_tags:
                    suspicious_approved_by_tag[f"naturalness::{tag}"] += 1
                if not non_wispy_failure_tags and not naturalness_tags:
                    suspicious_approved_by_tag["untagged_visual_risk"] += 1
                suspicious_approved.append(
                    {
                        "asset_id": item.get("asset_id"),
                        "pose_key": pose_key,
                        "failure_tags": failure_tags,
                        "naturalness_failure_tags_v1": naturalness_tags,
                        "naturalness_risk_v1": item.get("naturalness_risk_v1"),
                        "face_overlap_ratio": face_overlap_ratio,
                        "quality_score": item.get("quality_score"),
                    }
                )

    for pose_key, bucket in pose_bins.items():
        if bucket["approved"] <= 0 and bucket["borderline"] > 0:
            fallback_bins.append({"pose_key": pose_key, **bucket})

    suspicious_approved.sort(
        key=lambda item: (
            -len(item.get("failure_tags") or []),
            -(float(item.get("face_overlap_ratio") or 0.0)),
            -(float(item.get("naturalness_risk_v1") or 0.0)),
            str(item.get("asset_id") or ""),
        )
    )
    fallback_bins.sort(key=lambda item: str(item["pose_key"]))

    summary = {
        "asset_root": str(asset_root),
        "total_assets": len(items),
        "status_counts": dict(status_counts),
        "naturalness_failure_tag_counts": dict(naturalness_counts),
        "failure_tag_counts": dict(failure_counts),
        "pose_bins_total": len(pose_bins),
        "pose_bins_without_approved_but_with_borderline": len(fallback_bins),
        "suspicious_approved_count": len(suspicious_approved),
        "suspicious_approved_tag_counts": dict(suspicious_approved_by_tag),
        "top_suspicious_approved": suspicious_approved[: args.top_k],
        "top_fallback_pose_bins": fallback_bins[: args.top_k],
    }

    if args.output_json:
        output_path = Path(args.output_json).resolve()
        output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
