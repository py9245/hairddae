#!/usr/bin/env python3
"""Initialize an asset-factory scaffold from a pose-bank JSON."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path

from local_demo_paths import write_manifest_outputs


MASK_SUBDIRS = [
    "hair",
    "face",
    "ear_left",
    "ear_right",
    "forehead",
    "neck_shoulder",
    "overlap_suppression",
    "protect_face",
    "suppress_prior",
]


def format_signed(value: int) -> str:
    return f"{value:+03d}"


def sanitize_style_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")


def ensure_dirs(output_dir: Path) -> None:
    dirs = [
        output_dir / "rgb",
        output_dir / "alpha",
        output_dir / "hair_rgba",
        output_dir / "parsing",
        output_dir / "confidence" / "hair",
        output_dir / "anchors",
        output_dir / "metadata",
        output_dir / "manifests",
        output_dir / "indices",
        output_dir / "qa" / "pending_asset_qc",
        output_dir / "qa" / "anchor_preview",
        output_dir / "qa" / "mask_preview",
        output_dir / "qa" / "failure_types",
        output_dir / "qa" / "approved",
        output_dir / "qa" / "borderline",
        output_dir / "qa" / "rejected",
    ]
    dirs.extend(output_dir / "masks" / subdir for subdir in MASK_SUBDIRS)
    for directory in dirs:
        directory.mkdir(parents=True, exist_ok=True)


def link_or_copy(src: Path, dst: Path, mode: str) -> None:
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    if mode == "copy":
        shutil.copy2(src, dst)
        return
    dst.symlink_to(src)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pose-json", required=True, help="selected_pose.json path")
    parser.add_argument("--output-dir", required=True, help="output asset factory directory")
    parser.add_argument("--style-id", default=None, help="style identifier; defaults to source dirname")
    parser.add_argument(
        "--source-type",
        default="captured_base_video",
        choices=[
            "captured_base_video",
            "captured_photo",
            "generated_core",
            "generated_reference",
            "generated_dense",
        ],
    )
    parser.add_argument(
        "--generation-stage",
        default="captured_seed_bank",
        choices=[
            "captured_seed_bank",
            "validated_core",
            "reference_245",
            "dense_2000",
            "service_export",
        ],
    )
    parser.add_argument("--link-mode", default="symlink", choices=["symlink", "copy"])
    parser.add_argument("--preprocessing-version", default="center430x1080_pose1deg_firstonly_v1")
    parser.add_argument("--mask-pipeline-version", default="bisenet_mask_v3")
    parser.add_argument("--anchor-pipeline-version", default="mediapipe_face_anchor_v1")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pose_json_path = Path(args.pose_json).resolve()
    output_dir = Path(args.output_dir).resolve()

    with pose_json_path.open("r", encoding="utf-8") as handle:
        pose_bank = json.load(handle)

    summary = pose_bank["summary"]
    items = pose_bank["items"]
    style_id = sanitize_style_id(args.style_id or pose_json_path.parent.name)

    ensure_dirs(output_dir)

    manifest_items = []
    pose_index: dict[str, list[str]] = defaultdict(list)

    for item in items:
        angles = item["angles"]
        rounded = item["angles_1deg"]
        frame_index = item["frame_index"]
        pose_key = (
            f"yaw{format_signed(rounded['yaw'])}_"
            f"pitch{format_signed(rounded['pitch'])}_"
            f"roll{format_signed(rounded['roll'])}"
        )
        asset_id = (
            f"{style_id}__{pose_key}_frame{frame_index:06d}"
        )

        src_rgb = Path(item["selected_frame_path"]).resolve()
        dst_rgb = output_dir / "rgb" / f"{asset_id}.png"
        link_or_copy(src_rgb, dst_rgb, args.link_mode)

        alpha_path = Path("alpha") / f"{asset_id}.png"
        parsing_path = Path("parsing") / f"{asset_id}.png"
        hair_confidence_path = Path("confidence") / "hair" / f"{asset_id}.png"
        anchors_path = Path("anchors") / f"{asset_id}.json"
        metadata_path = Path("metadata") / f"{asset_id}.json"
        qa_preview_path = Path("qa") / "pending_asset_qc" / f"{asset_id}.png"
        qa_mask_preview_path = Path("qa") / "mask_preview" / f"{asset_id}.png"
        link_or_copy(dst_rgb, output_dir / qa_preview_path, "symlink")

        mask_paths = {
            subdir: Path("masks") / subdir / f"{asset_id}.png"
            for subdir in MASK_SUBDIRS
        }

        metadata = {
            "asset_id": asset_id,
            "style_id": style_id,
            "source_type": args.source_type,
            "generation_stage": args.generation_stage,
            "image_path": str(Path("rgb") / f"{asset_id}.png"),
            "alpha_path": str(alpha_path),
            "parsing_path": str(parsing_path),
            "hair_confidence_path": str(hair_confidence_path),
            "hair_rgba_path": str(Path("hair_rgba") / f"{asset_id}.png"),
            "hair_mask_path": str(mask_paths["hair"]),
            "face_mask_path": str(mask_paths["face"]),
            "ear_mask_left_path": str(mask_paths["ear_left"]),
            "ear_mask_right_path": str(mask_paths["ear_right"]),
            "forehead_mask_path": str(mask_paths["forehead"]),
            "neck_shoulder_mask_path": str(mask_paths["neck_shoulder"]),
            "overlap_suppression_mask_path": str(mask_paths["overlap_suppression"]),
            "protect_face_mask_path": str(mask_paths["protect_face"]),
            "suppress_prior_mask_path": str(mask_paths["suppress_prior"]),
            "anchors_path": str(anchors_path),
            "qa_preview_path": str(qa_preview_path),
            "qa_mask_preview_path": str(qa_mask_preview_path),
            "yaw_float": angles["yaw"],
            "pitch_float": angles["pitch"],
            "roll_float": angles["roll"],
            "yaw_1deg": rounded["yaw"],
            "pitch_1deg": rounded["pitch"],
            "roll_1deg": rounded["roll"],
            "pose_key": pose_key,
            "face_bbox": item.get("face_bbox"),
            "face_ratio": item.get("face_ratio"),
            "image_size": item.get("image_size"),
            "face_index": item.get("face_index"),
            "candidate_face_count": item.get("candidate_face_count"),
            "hair_rgba_bbox": None,
            "hair_width_ratio": None,
            "hair_height_ratio": None,
            "forehead_visible_ratio": None,
            "ear_visibility_left": None,
            "ear_visibility_right": None,
            "hair_area_ratio": None,
            "alpha_area_ratio": None,
            "face_overlap_ratio": None,
            "overlap_suppression_ratio": None,
            "mask_component_count": None,
            "hair_mean_confidence": None,
            "hair_p90_confidence": None,
            "mask_roi": None,
            "boundary_touches": {},
            "failure_tags": [],
            "part_side": "unknown",
            "bang_type": "unknown",
            "length_class": "unknown",
            "silhouette_type": "unknown",
            "quality_score": None,
            "pose_error_score": 0.0,
            "identity_score": None,
            "edge_score": None,
            "matte_score": None,
            "naturalness_score": None,
            "quality_status": "pending_asset_qc",
            "approved": False,
            "lineage": {
                "source_video_path": summary.get("video"),
                "source_frame_index": frame_index,
                "source_selected_frame_path": item.get("selected_frame_path"),
                "parent_asset_id": None,
                "parent_slot_id": None,
                "preprocessing_version": args.preprocessing_version,
                "mask_pipeline_version": args.mask_pipeline_version,
                "anchor_pipeline_version": args.anchor_pipeline_version,
                "notes": "",
            },
            "source_quality_metrics": item.get("quality_metrics"),
        }

        anchors_stub = {
            "asset_id": asset_id,
            "image_path": str(Path("rgb") / f"{asset_id}.png"),
            "image_size": item.get("image_size"),
            "seed_face_bbox": item.get("face_bbox"),
            "seed_face_index": item.get("face_index"),
            "seed_candidate_face_count": item.get("candidate_face_count"),
            "seed_quality_metrics": item.get("quality_metrics"),
            "points": {
                "forehead_center": None,
                "left_temple": None,
                "right_temple": None,
                "crown": None,
                "left_ear_root": None,
                "right_ear_root": None,
                "left_side": None,
                "right_side": None,
                "lower_left": None,
                "lower_right": None,
                "neck_left": None,
                "neck_right": None,
            },
        }

        with (output_dir / metadata_path).open("w", encoding="utf-8") as handle:
            json.dump(metadata, handle, ensure_ascii=False, indent=2)
        with (output_dir / anchors_path).open("w", encoding="utf-8") as handle:
            json.dump(anchors_stub, handle, ensure_ascii=False, indent=2)

        manifest_items.append(
            {
                "asset_id": asset_id,
                "pose_key": pose_key,
                "image_path": str(Path("rgb") / f"{asset_id}.png"),
                "metadata_path": str(metadata_path),
                "anchors_path": str(anchors_path),
                "quality_status": "pending_asset_qc",
            }
        )
        pose_index[pose_key].append(asset_id)

    manifest = {
        "schema_name": "asset_factory_manifest_v0",
        "source_pose_json": str(pose_json_path),
        "style_id": style_id,
        "source_type": args.source_type,
        "generation_stage": args.generation_stage,
        "summary": {
            "asset_count": len(manifest_items),
            "unique_pose_keys": len(pose_index),
            "source_video": summary.get("video"),
            "fps": summary.get("fps"),
            "start_sec": summary.get("start_sec"),
            "end_sec": summary.get("end_sec"),
            "crop_center_width": summary.get("crop_center_width"),
            "crop_center_height": summary.get("crop_center_height"),
            "link_mode": args.link_mode,
        },
        "items": manifest_items,
    }

    pose_index_payload = {
        "schema_name": "asset_pose_index_v0",
        "style_id": style_id,
        "pose_index": dict(sorted(pose_index.items())),
    }

    write_manifest_outputs(output_dir, manifest)
    with (output_dir / "indices" / "pose_index.json").open("w", encoding="utf-8") as handle:
        json.dump(pose_index_payload, handle, ensure_ascii=False, indent=2)

    readme = output_dir / "README_asset_factory_v0.txt"
    readme.write_text(
        "\n".join(
            [
                f"style_id={style_id}",
                f"asset_count={len(manifest_items)}",
                f"unique_pose_keys={len(pose_index)}",
                "next_steps=",
                "- fill masks/*",
                "- fill anchors/*.json",
                "- update metadata/*.json with geometry/classification/quality fields",
                "- move approved assets from qa/pending_asset_qc to qa/approved via status update",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Initialized asset factory at: {output_dir}")
    print(f"Asset count: {len(manifest_items)}")
    print(f"Unique pose keys: {len(pose_index)}")


if __name__ == "__main__":
    main()
