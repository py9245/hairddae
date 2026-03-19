#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate dataset readiness for runtime use.")
    parser.add_argument("--asset-root", required=True)
    parser.add_argument("--output-json", default=None)
    parser.add_argument("--min-approved-ratio", type=float, default=0.55)
    parser.add_argument("--max-rejected-ratio", type=float, default=0.04)
    parser.add_argument("--max-hole-assets", type=int, default=80)
    parser.add_argument("--max-suspicious-approved-ratio", type=float, default=0.06)
    parser.add_argument("--max-fallback-bin-ratio", type=float, default=0.45)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def classify(metric_name: str, ok: bool, value: Any, threshold: Any) -> dict[str, Any]:
    return {
        "metric": metric_name,
        "status": "pass" if ok else "warn",
        "value": value,
        "threshold": threshold,
    }


def main() -> None:
    args = parse_args()
    asset_root = Path(args.asset_root).resolve()
    manifests_dir = asset_root / "manifests"
    index_summary = load_json(manifests_dir / "asset_index_summary.json")
    audit_summary = load_json(manifests_dir / "asset_index_audit_v1.json")
    mask_summary = load_json(manifests_dir / "mask_extraction_summary.json")

    total_assets = int(index_summary.get("total_assets") or 0)
    approved_assets = int(index_summary.get("approved_assets") or 0)
    rejected_assets = int(index_summary.get("rejected_assets") or 0)
    approved_ratio = float(index_summary.get("approved_ratio") or 0.0)
    rejected_ratio = (rejected_assets / total_assets) if total_assets else 0.0

    failure_tag_counts = index_summary.get("failure_tag_counts") or {}
    hole_assets = int(failure_tag_counts.get("internal_hole_risk") or 0)
    suspicious_approved_count = int(audit_summary.get("suspicious_approved_count") or 0)
    suspicious_approved_ratio = (suspicious_approved_count / approved_assets) if approved_assets else 0.0

    pose_bins_total = int(audit_summary.get("pose_bins_total") or 0)
    fallback_bins = int(audit_summary.get("pose_bins_without_approved_but_with_borderline") or 0)
    fallback_bin_ratio = (fallback_bins / pose_bins_total) if pose_bins_total else 0.0

    mask_processed = int(mask_summary.get("processed_rows") or 0)
    mask_failed = int(mask_summary.get("failed_rows") or 0)

    checks = [
        classify("approved_ratio", approved_ratio >= args.min_approved_ratio, round(approved_ratio, 6), {"min": args.min_approved_ratio}),
        classify("rejected_ratio", rejected_ratio <= args.max_rejected_ratio, round(rejected_ratio, 6), {"max": args.max_rejected_ratio}),
        classify("hole_assets", hole_assets <= args.max_hole_assets, hole_assets, {"max": args.max_hole_assets}),
        classify(
            "suspicious_approved_ratio",
            suspicious_approved_ratio <= args.max_suspicious_approved_ratio,
            round(suspicious_approved_ratio, 6),
            {"max": args.max_suspicious_approved_ratio},
        ),
        classify(
            "fallback_bin_ratio",
            fallback_bin_ratio <= args.max_fallback_bin_ratio,
            round(fallback_bin_ratio, 6),
            {"max": args.max_fallback_bin_ratio},
        ),
        classify("mask_failed_rows", mask_failed == 0, mask_failed, {"expected": 0}),
    ]

    overall_status = "ready" if all(check["status"] == "pass" for check in checks) else "needs_review"
    summary = {
        "asset_root": str(asset_root),
        "overall_status": overall_status,
        "totals": {
            "total_assets": total_assets,
            "approved_assets": approved_assets,
            "rejected_assets": rejected_assets,
            "pose_bins_total": pose_bins_total,
            "fallback_pose_bins": fallback_bins,
            "processed_masks": mask_processed,
            "failed_masks": mask_failed,
            "hole_assets": hole_assets,
            "suspicious_approved_count": suspicious_approved_count,
        },
        "ratios": {
            "approved_ratio": round(approved_ratio, 6),
            "rejected_ratio": round(rejected_ratio, 6),
            "fallback_bin_ratio": round(fallback_bin_ratio, 6),
            "suspicious_approved_ratio": round(suspicious_approved_ratio, 6),
        },
        "checks": checks,
    }

    if args.output_json:
        output_path = Path(args.output_json).resolve()
        output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
