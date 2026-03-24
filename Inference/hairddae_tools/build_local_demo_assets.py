#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from local_demo_paths import ensure_runtime_dirs, generated_root, static_root


def sanitize_tag(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value).strip()).strip("_")
    return sanitized or "dataset"


def default_output_paths(video_path: Path, dataset_tag: str | None) -> tuple[Path, Path]:
    tag = sanitize_tag(dataset_tag or video_path.stem)
    return (
        generated_root() / f"base_pose_bank_{tag}",
        generated_root() / f"asset_factory_{tag}",
    )


def ensure_empty_or_missing(path: Path, label: str, overwrite: bool) -> None:
    if not path.exists():
        return
    if overwrite:
        return
    if path.is_file():
        raise SystemExit(f"{label} must be a directory: {path}")
    if any(path.iterdir()):
        raise SystemExit(
            f"{label} is not empty: {path}. Use a new versioned path or pass --overwrite explicitly."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build all local demo assets from a single base video.")
    parser.add_argument(
        "--video",
        default=str(static_root() / "new_base_de_vedio" / "dandy2.mp4"),
    )
    parser.add_argument("--dataset-tag", default=None, help="Dataset tag used for derived output directories.")
    parser.add_argument("--pose-bank-dir", default=None)
    parser.add_argument("--asset-root", default=None)
    parser.add_argument("--start-sec", type=float, default=0.0)
    parser.add_argument("--end-sec", type=float, default=None)
    parser.add_argument("--frame-step", type=int, default=1)
    parser.add_argument("--crop-center-width", type=int, default=None)
    parser.add_argument("--crop-center-height", type=int, default=None)
    parser.add_argument("--dedupe-rounded-pose", action="store_true")
    parser.add_argument(
        "--best-per-rounded-pose",
        dest="best_per_rounded_pose",
        action="store_true",
        default=True,
        help="Select the best-quality frame for each rounded pose bin. Enabled by default.",
    )
    parser.add_argument(
        "--disable-best-per-rounded-pose",
        dest="best_per_rounded_pose",
        action="store_false",
        help="Disable best-per-rounded-pose and keep the extractor default behavior.",
    )
    parser.add_argument("--skip-existing-rounded-pose", action="store_true")
    parser.add_argument("--existing-selected-pose-json", default=None)
    parser.add_argument("--landmarker-delegate", choices=["cpu", "gpu"], default="gpu")
    parser.add_argument("--num-faces", type=int, default=3)
    parser.add_argument("--link-mode", choices=["symlink", "copy"], default="symlink")
    parser.add_argument("--mask-device", default="cuda")
    parser.add_argument("--mask-batch-size", type=int, default=32)
    parser.add_argument("--mask-pipeline-version", default="bisenet_mask_v3")
    parser.add_argument("--anchor-pipeline-version", default="mediapipe_face_anchor_v1")
    parser.add_argument("--min-face-ratio", type=float, default=0.03)
    parser.add_argument("--max-center-bias", type=float, default=0.28)
    parser.add_argument("--min-sharpness", type=float, default=6.0)
    parser.add_argument("--high-pitch-threshold", type=int, default=16)
    parser.add_argument("--high-pitch-min-face-ratio", type=float, default=0.04)
    parser.add_argument("--high-pitch-max-center-bias", type=float, default=0.18)
    parser.add_argument("--high-pitch-min-sharpness", type=float, default=12.0)
    parser.add_argument("--extreme-pitch-threshold", type=int, default=24)
    parser.add_argument("--extreme-pitch-min-face-ratio", type=float, default=0.045)
    parser.add_argument("--extreme-pitch-max-center-bias", type=float, default=0.16)
    parser.add_argument("--extreme-pitch-min-sharpness", type=float, default=14.0)
    parser.add_argument("--feature-root", default=None)
    parser.add_argument("--feature-limit", type=int, default=0)
    parser.add_argument("--skip-existing-features", action="store_true")
    parser.add_argument("--skip-existing-naturalness", action="store_true")
    parser.add_argument("--skip-missing-features", action="store_true")
    parser.add_argument("--run-audit", action="store_true", default=True)
    parser.add_argument("--skip-audit", dest="run_audit", action="store_false")
    parser.add_argument("--run-validation", action="store_true", default=True)
    parser.add_argument("--skip-validation", dest="run_validation", action="store_false")
    parser.add_argument("--generate-runtime-blacklist", action="store_true")
    parser.add_argument("--blacklist-max-face-overlap-ratio", type=float, default=0.004)
    parser.add_argument("--blacklist-max-naturalness-risk", type=float, default=0.09)
    parser.add_argument("--blacklist-max-assets", type=int, default=200)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def run_step(step_name: str, command: list[str]) -> None:
    print(f"[local-demo] {step_name}")
    print(" ".join(command))
    subprocess.run(command, check=True)


def main() -> None:
    args = parse_args()
    ensure_runtime_dirs()

    video_path = Path(args.video).resolve()
    default_pose_bank_dir, default_asset_root = default_output_paths(video_path, args.dataset_tag)
    pose_bank_dir = Path(args.pose_bank_dir).resolve() if args.pose_bank_dir else default_pose_bank_dir.resolve()
    asset_root = Path(args.asset_root).resolve() if args.asset_root else default_asset_root.resolve()
    feature_root = Path(args.feature_root).resolve() if args.feature_root else (pose_bank_dir / "comprehensive_feature_v1").resolve()
    tools_dir = Path(__file__).resolve().parent

    if not video_path.is_file():
        raise FileNotFoundError(f"Base video not found: {video_path}")

    if args.overwrite:
        for path in [pose_bank_dir, asset_root, feature_root]:
            if path.exists():
                shutil.rmtree(path)
    else:
        ensure_empty_or_missing(pose_bank_dir, "pose bank dir", args.overwrite)
        ensure_empty_or_missing(asset_root, "asset root", args.overwrite)
        ensure_empty_or_missing(feature_root, "feature root", args.overwrite)

    pose_bank_dir.parent.mkdir(parents=True, exist_ok=True)
    asset_root.parent.mkdir(parents=True, exist_ok=True)
    feature_root.parent.mkdir(parents=True, exist_ok=True)

    pose_command = [
        sys.executable,
        str(tools_dir / "extract_pose_frames_from_video.py"),
        "--video",
        str(video_path),
        "--output-dir",
        str(pose_bank_dir),
        "--frame-step",
        str(args.frame_step),
        "--start-sec",
        str(args.start_sec),
        "--delegate",
        args.landmarker_delegate,
        "--num-faces",
        str(args.num_faces),
        "--min-face-ratio",
        str(args.min_face_ratio),
        "--max-center-bias",
        str(args.max_center_bias),
        "--min-sharpness",
        str(args.min_sharpness),
        "--high-pitch-threshold",
        str(args.high_pitch_threshold),
        "--high-pitch-min-face-ratio",
        str(args.high_pitch_min_face_ratio),
        "--high-pitch-max-center-bias",
        str(args.high_pitch_max_center_bias),
        "--high-pitch-min-sharpness",
        str(args.high_pitch_min_sharpness),
        "--extreme-pitch-threshold",
        str(args.extreme_pitch_threshold),
        "--extreme-pitch-min-face-ratio",
        str(args.extreme_pitch_min_face_ratio),
        "--extreme-pitch-max-center-bias",
        str(args.extreme_pitch_max_center_bias),
        "--extreme-pitch-min-sharpness",
        str(args.extreme_pitch_min_sharpness),
    ]
    if args.crop_center_width is not None:
        pose_command.extend(["--crop-center-width", str(args.crop_center_width)])
    if args.crop_center_height is not None:
        pose_command.extend(["--crop-center-height", str(args.crop_center_height)])
    if args.dedupe_rounded_pose:
        pose_command.append("--dedupe-rounded-pose")
    if args.best_per_rounded_pose:
        pose_command.append("--best-per-rounded-pose")
    if args.skip_existing_rounded_pose:
        pose_command.append("--skip-existing-rounded-pose")
    if args.existing_selected_pose_json:
        pose_command.extend(["--existing-selected-pose-json", str(Path(args.existing_selected_pose_json).resolve())])
    if args.end_sec is not None:
        pose_command.extend(["--end-sec", str(args.end_sec)])
    run_step("step 1/7 pose bank", pose_command)

    run_step(
        "step 2/7 asset factory scaffold",
        [
            sys.executable,
            str(tools_dir / "init_asset_factory_from_pose_bank.py"),
            "--pose-json",
            str(pose_bank_dir / "selected_pose.json"),
            "--output-dir",
            str(asset_root),
            "--source-type",
            "captured_base_video",
            "--generation-stage",
            "captured_seed_bank",
            "--link-mode",
            args.link_mode,
            "--mask-pipeline-version",
            args.mask_pipeline_version,
            "--anchor-pipeline-version",
            args.anchor_pipeline_version,
        ],
    )

    run_step(
        "step 3/7 anchor extraction",
        [
            sys.executable,
            str(tools_dir / "extract_asset_face_anchors.py"),
            "--asset-root",
            str(asset_root),
            "--delegate",
            args.landmarker_delegate,
            "--num-faces",
            str(args.num_faces),
            "--anchor-pipeline-version",
            args.anchor_pipeline_version,
        ],
    )

    run_step(
        "step 4/7 parsing masks",
        [
            sys.executable,
            str(tools_dir / "extract_asset_parsing_masks.py"),
            "--asset-root",
            str(asset_root),
            "--device",
            args.mask_device,
            "--batch-size",
            str(args.mask_batch_size),
            "--mask-pipeline-version",
            args.mask_pipeline_version,
        ],
    )

    run_step(
        "step 5/7 comprehensive features",
        [
            sys.executable,
            str(tools_dir / "extract_comprehensive_frame_features.py"),
            "--pose-bank-dir",
            str(pose_bank_dir),
            "--output-dir",
            str(feature_root),
            "--landmarker-delegate",
            args.landmarker_delegate,
            "--face-parsing-device",
            args.mask_device,
        ]
        + (["--skip-existing"] if args.skip_existing_features else [])
        + (["--limit", str(args.feature_limit)] if args.feature_limit > 0 else []),
    )

    run_step(
        "step 6/7 naturalness scoring",
        [
            sys.executable,
            str(tools_dir / "score_asset_naturalness_from_comprehensive_features.py"),
            "--asset-root",
            str(asset_root),
            "--feature-root",
            str(feature_root),
            "--write-back-metadata",
        ]
        + (["--skip-existing"] if args.skip_existing_naturalness else [])
        + (["--skip-missing-features"] if args.skip_missing_features else []),
    )

    run_step(
        "step 7/7 retrieval index",
        [
            sys.executable,
            str(tools_dir / "build_asset_retrieval_index.py"),
            "--asset-root",
            str(asset_root),
            "--write-back-metadata",
        ],
    )

    audit_path = asset_root / "manifests" / "asset_index_audit_v1.json"
    validation_path = asset_root / "manifests" / "dataset_readiness_v1.json"
    runtime_blacklist_path = asset_root / "manifests" / "runtime_asset_blacklist.generated.json"

    if args.run_audit:
        run_step(
            "step 8/10 asset audit",
            [
                sys.executable,
                str(tools_dir / "audit_asset_index.py"),
                "--asset-root",
                str(asset_root),
                "--output-json",
                str(audit_path),
            ],
        )

    if args.run_validation:
        run_step(
            "step 9/10 dataset readiness validation",
            [
                sys.executable,
                str(tools_dir / "validate_asset_dataset.py"),
                "--asset-root",
                str(asset_root),
                "--output-json",
                str(validation_path),
            ],
        )

    if args.generate_runtime_blacklist:
        run_step(
            "step 10/10 runtime blacklist generation",
            [
                sys.executable,
                str(tools_dir / "generate_runtime_asset_blacklist.py"),
                "--asset-root",
                str(asset_root),
                "--output-json",
                str(runtime_blacklist_path),
                "--max-face-overlap-ratio",
                str(args.blacklist_max_face_overlap_ratio),
                "--max-naturalness-risk",
                str(args.blacklist_max_naturalness_risk),
                "--max-assets",
                str(args.blacklist_max_assets),
            ],
        )

    build_recipe = {
        "video": str(video_path),
        "dataset_tag": sanitize_tag(args.dataset_tag or video_path.stem),
        "pose_bank_dir": str(pose_bank_dir),
        "asset_root": str(asset_root),
        "feature_root": str(feature_root),
        "landmarker_delegate": args.landmarker_delegate,
        "num_faces": args.num_faces,
        "mask_device": args.mask_device,
        "mask_batch_size": args.mask_batch_size,
        "best_per_rounded_pose": args.best_per_rounded_pose,
        "quality_filters": {
            "min_face_ratio": args.min_face_ratio,
            "max_center_bias": args.max_center_bias,
            "min_sharpness": args.min_sharpness,
            "high_pitch_threshold": args.high_pitch_threshold,
            "high_pitch_min_face_ratio": args.high_pitch_min_face_ratio,
            "high_pitch_max_center_bias": args.high_pitch_max_center_bias,
            "high_pitch_min_sharpness": args.high_pitch_min_sharpness,
            "extreme_pitch_threshold": args.extreme_pitch_threshold,
            "extreme_pitch_min_face_ratio": args.extreme_pitch_min_face_ratio,
            "extreme_pitch_max_center_bias": args.extreme_pitch_max_center_bias,
            "extreme_pitch_min_sharpness": args.extreme_pitch_min_sharpness,
        },
        "pipeline_versions": {
            "anchor_pipeline_version": args.anchor_pipeline_version,
            "mask_pipeline_version": args.mask_pipeline_version,
            "naturalness_version": "v1",
        },
        "post_build": {
            "run_audit": args.run_audit,
            "run_validation": args.run_validation,
            "generate_runtime_blacklist": args.generate_runtime_blacklist,
            "audit_path": str(audit_path) if args.run_audit else None,
            "validation_path": str(validation_path) if args.run_validation else None,
            "runtime_blacklist_path": str(runtime_blacklist_path) if args.generate_runtime_blacklist else None,
        },
    }
    build_recipe_path = asset_root / "manifests" / "build_recipe.json"
    build_recipe_path.write_text(json.dumps(build_recipe, indent=2, ensure_ascii=True), encoding="utf-8")

    print(f"[local-demo] complete asset_root={asset_root}")


if __name__ == "__main__":
    main()
