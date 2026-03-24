#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a runtime blacklist from suspicious approved assets.")
    parser.add_argument("--asset-root", required=True)
    parser.add_argument("--output-json", default=None)
    parser.add_argument("--max-face-overlap-ratio", type=float, default=0.004)
    parser.add_argument("--max-naturalness-risk", type=float, default=0.09)
    parser.add_argument("--max-assets", type=int, default=200)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    args = parse_args()
    asset_root = Path(args.asset_root).resolve()
    manifests_dir = asset_root / "manifests"
    index_payload = load_json(manifests_dir / "asset_index_v0.json")
    items: list[dict[str, Any]] = index_payload.get("items", [])

    candidates: list[dict[str, Any]] = []
    for item in items:
        if str(item.get("quality_status") or "") != "approved":
            continue
        face_overlap_ratio = float(item.get("face_overlap_ratio") or 0.0)
        naturalness_risk = float(item.get("naturalness_risk_v1") or 0.0)
        failure_tags = list(item.get("failure_tags") or [])
        naturalness_tags = list(item.get("naturalness_failure_tags_v1") or [])

        if (
            face_overlap_ratio > args.max_face_overlap_ratio
            or naturalness_risk > args.max_naturalness_risk
            or failure_tags
            or any(tag in {"face_skin_overlap_risk", "downward_face_cover_risk", "hole_shape_risk", "fringe_deformation_risk"} for tag in naturalness_tags)
        ):
            candidates.append(
                {
                    "asset_id": str(item.get("asset_id") or ""),
                    "pose_key": str(item.get("pose_key") or ""),
                    "face_overlap_ratio": face_overlap_ratio,
                    "naturalness_risk_v1": naturalness_risk,
                    "failure_tags": failure_tags,
                    "naturalness_failure_tags_v1": naturalness_tags,
                }
            )

    candidates.sort(
        key=lambda item: (
            -len(item["failure_tags"]),
            -len(item["naturalness_failure_tags_v1"]),
            -float(item["face_overlap_ratio"]),
            -float(item["naturalness_risk_v1"]),
            item["asset_id"],
        )
    )
    candidates = candidates[: args.max_assets]

    payload = {
        "asset_root": str(asset_root),
        "asset_ids": [item["asset_id"] for item in candidates if item["asset_id"]],
        "entries": candidates,
        "thresholds": {
            "max_face_overlap_ratio": args.max_face_overlap_ratio,
            "max_naturalness_risk": args.max_naturalness_risk,
            "max_assets": args.max_assets,
        },
    }

    output_path = Path(args.output_json).resolve() if args.output_json else (manifests_dir / "runtime_asset_blacklist.generated.json")
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output_json": str(output_path), "blacklisted_assets": len(payload["asset_ids"])}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
