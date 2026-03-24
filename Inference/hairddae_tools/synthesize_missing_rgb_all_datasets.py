#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from local_demo_paths import static_root
from synthesize_missing_rgb_from_hair_rgba import process_asset_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synthesize missing rgb assets for all static datasets."
    )
    parser.add_argument(
        "--static-root",
        default=str(static_root()),
        help="Static root that contains dataset directories.",
    )
    parser.add_argument(
        "--dataset-code",
        action="append",
        default=[],
        help="Specific dataset code(s) to process. Default: all detected datasets.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Rewrite rgb files even if they already exist.",
    )
    parser.add_argument(
        "--limit-per-dataset",
        type=int,
        default=0,
        help="Process at most N assets per dataset. 0 means no limit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be created without writing files.",
    )
    return parser.parse_args()


def _iter_dataset_roots(static_root_path: Path, requested_codes: list[str]) -> Iterable[Path]:
    if requested_codes:
        for dataset_code in requested_codes:
            candidate = (static_root_path / dataset_code).resolve()
            if candidate.is_dir():
                yield candidate
        return

    for child in sorted(static_root_path.iterdir()):
        if not child.is_dir():
            continue
        if (child / "manifests" / "asset_index_v0.json").is_file():
            yield child.resolve()


def main() -> None:
    args = parse_args()
    root = Path(args.static_root).resolve()
    dataset_roots = list(_iter_dataset_roots(root, [code.strip() for code in args.dataset_code if code.strip()]))

    summaries: list[dict[str, object]] = []
    total_created = 0
    total_processed = 0
    total_errors = 0

    for dataset_root in dataset_roots:
        print(f"[dataset] {dataset_root.name}")
        summary = process_asset_root(
            asset_root=dataset_root,
            overwrite=bool(args.overwrite),
            limit=int(args.limit_per_dataset),
            dry_run=bool(args.dry_run),
            verbose=True,
        )
        summaries.append(summary)
        total_created += int(summary["created"])
        total_processed += int(summary["processed"])
        total_errors += int(summary["errors"])

    print(
        json.dumps(
            {
                "static_root": str(root),
                "dataset_count": len(dataset_roots),
                "processed": total_processed,
                "created": total_created,
                "errors": total_errors,
                "dry_run": bool(args.dry_run),
                "datasets": summaries,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
