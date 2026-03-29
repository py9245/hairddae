from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parents[0]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from forced_gpu_cv2 import patch_all

import benchmark_native_e2e as native


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark near-native E2E with GPU-forced OpenCV wrappers in gputest")
    parser.add_argument("--image", default=str(REPO_ROOT / "testimage" / "긴머리_test.png"))
    parser.add_argument("--stage", default="576x1024")
    parser.add_argument("--dataset-code", default="0009")
    parser.add_argument("--hair-id", type=int, default=3)
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--process-dim", action="append", type=int, help="Repeatable process max dimension profile")
    parser.add_argument("--prefer-latency", action="store_true", default=True)
    parser.add_argument("--output-json", default="")
    args = parser.parse_args()

    patched_modules = patch_all()
    native.load_env_file(REPO_ROOT / ".env.server")
    settings = native.Settings.from_env()
    claims = native.make_claims(args.hair_id, args.dataset_code)

    image_path = Path(args.image).expanduser().resolve()
    frame_bgr = native.cv2.imread(str(image_path), native.cv2.IMREAD_COLOR)
    if frame_bgr is None:
        raise FileNotFoundError(f"failed to load image: {image_path}")

    stage_width, stage_height = native.parse_stage(args.stage)
    base_frame_bgr = native.cv2.resize(frame_bgr, (stage_width, stage_height), interpolation=native.cv2.INTER_AREA)
    dims = args.process_dim or [max(stage_width, stage_height)]

    results = []
    for process_dim in dims:
        profile_name = f"forced_gpu_process_max_dimension_{process_dim}"
        print(
            f"[gputest] running {profile_name} on stage {stage_width}x{stage_height} iterations={args.iterations}",
            flush=True,
        )
        results.append(
            native.run_profile(
                profile_name=profile_name,
                base_frame_bgr=base_frame_bgr,
                process_max_dimension=process_dim,
                iterations=args.iterations,
                prefer_latency=args.prefer_latency,
                settings=settings,
                claims=claims,
                dataset_code=args.dataset_code,
                representative_asset_id=None,
            )
        )

    payload = {
        "mode": "forced_gpu_wrappers",
        "patched_modules": patched_modules,
        "image": str(image_path),
        "stage": {"width": stage_width, "height": stage_height},
        "dataset_code": args.dataset_code,
        "hair_id": args.hair_id,
        "results": results,
    }
    if args.output_json:
        output_path = Path(args.output_json).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
