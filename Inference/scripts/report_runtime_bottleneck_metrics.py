#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import re
import statistics
from pathlib import Path


DATASET_PREFIXES = {
    "0001": "base_pose_bank__",
    "0004": "shorthair_short_hair_pose_full_final__",
    "0009": "base_pose_bank_H_bundlehair_0001__",
    "0010": "H_shortperm_0001_pose_bank__",
}


PERF_RE = re.compile(
    r"rtc perf: seq=(\d+) total=([0-9.]+).*?"
    r"attenuation=([0-9.]+).*?"
    r"hair_total=([0-9.]+).*?"
    r"hair_overlay=([0-9.]+).*?"
    r"hair_parse=([0-9.]+).*?"
    r"asset=([^ ]+) .*?"
    r"status=([^ ]+)"
)
FAIL_RE = re.compile(r"hair runtime render failure: .*asset_ids=\[(.*?)\]")
FALLBACK_RE = re.compile(r"rtc bundle render fallback applied: asset=([^ ]+)")
ASSET_BUNDLE_FAIL_RE = re.compile(r"rtc asset bundle build failed: .*asset_id ([^ ]+) for dataset ([0-9]{4})")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize runtime bottleneck metrics from inference-server logs."
    )
    parser.add_argument(
        "--log-file",
        required=True,
        help="Path to captured docker logs.",
    )
    parser.add_argument(
        "--steady-max-total-ms",
        type=float,
        default=1000.0,
        help="Steady-state cutoff for total latency.",
    )
    return parser.parse_args()


def dataset_code_for_asset(asset_id: str) -> str | None:
    for dataset_code, prefix in DATASET_PREFIXES.items():
        if asset_id.startswith(prefix):
            return dataset_code
    return None


def p95(values: list[float]) -> float:
    if not values:
        raise ValueError("p95 requires at least one value")
    ordered = sorted(values)
    index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return ordered[index]


def format_triplet(values: list[float]) -> str:
    return f"{sum(values) / len(values):.1f} / {statistics.median(values):.1f} / {p95(values):.1f} ms"


def format_statuses(statuses: dict[str, int]) -> str:
    if not statuses:
        return "-"
    return ", ".join(f"{key}: {value}" for key, value in sorted(statuses.items()))


def main() -> None:
    args = parse_args()
    lines = Path(args.log_file).read_text(encoding="utf-8", errors="replace").splitlines()

    metrics = {
        dataset_code: {
            "total": [],
            "overlay": [],
            "attenuation": [],
            "parse": [],
            "statuses": {},
        }
        for dataset_code in DATASET_PREFIXES
    }
    render_failures = {dataset_code: 0 for dataset_code in DATASET_PREFIXES}
    fallbacks = {dataset_code: 0 for dataset_code in DATASET_PREFIXES}
    asset_bundle_failures = {dataset_code: 0 for dataset_code in DATASET_PREFIXES}

    for line in lines:
        perf_match = PERF_RE.search(line)
        if perf_match:
            total = float(perf_match.group(2))
            if total < float(args.steady_max_total_ms):
                dataset_code = dataset_code_for_asset(perf_match.group(7))
                if dataset_code is not None:
                    row = metrics[dataset_code]
                    row["total"].append(total)
                    row["attenuation"].append(float(perf_match.group(3)))
                    row["overlay"].append(float(perf_match.group(5)))
                    row["parse"].append(float(perf_match.group(6)))
                    status = perf_match.group(8)
                    row["statuses"][status] = row["statuses"].get(status, 0) + 1
            continue

        failure_match = FAIL_RE.search(line)
        if failure_match:
            asset_ids = [
                token.strip().strip("'\"")
                for token in failure_match.group(1).split(",")
                if token.strip()
            ]
            if asset_ids:
                dataset_code = dataset_code_for_asset(asset_ids[0])
                if dataset_code is not None:
                    render_failures[dataset_code] += 1
            continue

        fallback_match = FALLBACK_RE.search(line)
        if fallback_match:
            dataset_code = dataset_code_for_asset(fallback_match.group(1))
            if dataset_code is not None:
                fallbacks[dataset_code] += 1
            continue

        asset_bundle_match = ASSET_BUNDLE_FAIL_RE.search(line)
        if asset_bundle_match:
            dataset_code = asset_bundle_match.group(2)
            if dataset_code in asset_bundle_failures:
                asset_bundle_failures[dataset_code] += 1

    print("| 헤어 | perf 샘플 수 | steady total avg / p50 / p95 | steady overlay avg / p50 / p95 | attenuation p50 | parse p50 | render failure | fallback | 상태 |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for dataset_code in ("0001", "0004", "0009", "0010"):
        row = metrics[dataset_code]
        sample_count = len(row["total"])
        if sample_count == 0:
            total_cell = "-"
            overlay_cell = "-"
            attenuation_cell = "-"
            parse_cell = "-"
        else:
            total_cell = f"`{format_triplet(row['total'])}`"
            overlay_cell = f"`{format_triplet(row['overlay'])}`"
            attenuation_cell = f"`{statistics.median(row['attenuation']):.1f} ms`"
            parse_cell = f"`{statistics.median(row['parse']):.1f} ms`"
        print(
            f"| `{dataset_code}` | {sample_count} | {total_cell} | {overlay_cell} | "
            f"{attenuation_cell} | {parse_cell} | {render_failures[dataset_code]} | "
            f"{fallbacks[dataset_code]} | {format_statuses(row['statuses'])} |"
        )

    print()
    print("## 잔여 이슈")
    for dataset_code in ("0001", "0004", "0009", "0010"):
        print(
            f"- `{dataset_code}` asset bundle build failed: {asset_bundle_failures[dataset_code]}"
        )


if __name__ == "__main__":
    main()
