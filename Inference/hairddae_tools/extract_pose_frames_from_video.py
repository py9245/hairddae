#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
from pathlib import Path

import cv2

from face_feature_utils import build_landmarker, extract_feature_from_frame_bgr
from local_demo_paths import default_face_landmarker_model_path


SELECTED_FRAME_RE = re.compile(
    r"^yaw(?P<yaw>[+-]\d+)_pitch(?P<pitch>[+-]\d+)_roll(?P<roll>[+-]\d+)_frame(?P<frame>\d+)\.(?:png|jpg|jpeg)$"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract all video frames, estimate face pose with MediaPipe, and save "
            "frames whose rounded angles fall within configured yaw/pitch/roll ranges."
        )
    )
    parser.add_argument("--video", required=True, help="Input video path.")
    parser.add_argument("--output-dir", required=True, help="Output directory root.")
    parser.add_argument(
        "--model-path",
        default=str(default_face_landmarker_model_path()),
        help="MediaPipe face landmarker task path.",
    )
    parser.add_argument("--delegate", choices=["cpu", "gpu"], default="gpu")
    parser.add_argument("--num-faces", type=int, default=3, help="Maximum faces to detect per frame.")
    parser.add_argument("--yaw-min", type=int, default=-45)
    parser.add_argument("--yaw-max", type=int, default=45)
    parser.add_argument("--pitch-min", type=int, default=-15)
    parser.add_argument("--pitch-max", type=int, default=30)
    parser.add_argument("--roll-min", type=int, default=-20)
    parser.add_argument("--roll-max", type=int, default=20)
    parser.add_argument(
        "--frame-step",
        type=int,
        default=1,
        help="Process every Nth frame. 1 means all frames.",
    )
    parser.add_argument("--start-sec", type=float, default=0.0, help="Start time in seconds.")
    parser.add_argument("--end-sec", type=float, default=None, help="End time in seconds.")
    parser.add_argument("--crop-center-width", type=int, default=None)
    parser.add_argument("--crop-center-height", type=int, default=None)
    parser.add_argument(
        "--dedupe-rounded-pose",
        action="store_true",
        help="Keep only the first frame for each rounded yaw/pitch/roll triplet.",
    )
    parser.add_argument(
        "--best-per-rounded-pose",
        action="store_true",
        help="Select the best-quality frame for each rounded yaw/pitch/roll triplet.",
    )
    parser.add_argument(
        "--skip-existing-rounded-pose",
        action="store_true",
        help=(
            "Skip selected-frame export for rounded pose keys that already exist in "
            "selected_pose.json or selected_frames/."
        ),
    )
    parser.add_argument(
        "--existing-selected-pose-json",
        default=None,
        help="Optional selected_pose.json used to seed already-covered rounded pose keys.",
    )
    parser.add_argument(
        "--jpeg-quality",
        type=int,
        default=95,
        help="JPEG quality for saved frames when extension is .jpg",
    )
    parser.add_argument(
        "--min-face-ratio",
        type=float,
        default=0.03,
        help="Reject frames whose selected face box is too small relative to the frame.",
    )
    parser.add_argument(
        "--max-center-bias",
        type=float,
        default=0.28,
        help="Reject frames whose selected face center is too far from frame center.",
    )
    parser.add_argument(
        "--min-sharpness",
        type=float,
        default=6.0,
        help="Optional hard floor for head-crop sharpness; 0 keeps all and only uses sharpness for ranking.",
    )
    parser.add_argument("--high-pitch-threshold", type=int, default=16)
    parser.add_argument("--high-pitch-min-face-ratio", type=float, default=0.04)
    parser.add_argument("--high-pitch-max-center-bias", type=float, default=0.18)
    parser.add_argument("--high-pitch-min-sharpness", type=float, default=12.0)
    parser.add_argument("--extreme-pitch-threshold", type=int, default=24)
    parser.add_argument("--extreme-pitch-min-face-ratio", type=float, default=0.045)
    parser.add_argument("--extreme-pitch-max-center-bias", type=float, default=0.16)
    parser.add_argument("--extreme-pitch-min-sharpness", type=float, default=14.0)
    return parser.parse_args()


def ensure_dirs(output_dir: Path) -> tuple[Path, Path]:
    all_frames_dir = output_dir / "all_frames"
    selected_dir = output_dir / "selected_frames"
    all_frames_dir.mkdir(parents=True, exist_ok=True)
    selected_dir.mkdir(parents=True, exist_ok=True)
    return all_frames_dir, selected_dir


def save_frame(path: Path, frame, jpeg_quality: int) -> None:
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        cv2.imwrite(str(path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])
    else:
        cv2.imwrite(str(path), frame)


def crop_center(frame, crop_width: int | None, crop_height: int | None):
    if crop_width is None and crop_height is None:
        return frame
    height, width = frame.shape[:2]
    target_width = crop_width or width
    target_height = crop_height or height
    if target_width > width or target_height > height:
        raise ValueError(
            f"Requested crop {target_width}x{target_height} exceeds frame size {width}x{height}"
        )
    x0 = (width - target_width) // 2
    y0 = (height - target_height) // 2
    return frame[y0 : y0 + target_height, x0 : x0 + target_width]


def bbox_center(bbox: dict[str, int]) -> tuple[float, float]:
    return (
        float(bbox["x"]) + float(bbox["w"]) * 0.5,
        float(bbox["y"]) + float(bbox["h"]) * 0.5,
    )


def expanded_head_roi_from_bbox(frame, bbox: dict[str, int]) -> tuple[int, int, int, int]:
    height, width = frame.shape[:2]
    x = float(bbox["x"])
    y = float(bbox["y"])
    w = max(1.0, float(bbox["w"]))
    h = max(1.0, float(bbox["h"]))
    x0 = max(0, int(round(x - w * 0.45)))
    y0 = max(0, int(round(y - h * 0.65)))
    x1 = min(width, int(round(x + w * 1.45)))
    y1 = min(height, int(round(y + h * 1.10)))
    if x1 <= x0 or y1 <= y0:
        return 0, 0, width, height
    return x0, y0, x1 - x0, y1 - y0


def compute_sharpness(frame, bbox: dict[str, int]) -> float:
    x0, y0, roi_w, roi_h = expanded_head_roi_from_bbox(frame, bbox)
    roi = frame[y0 : y0 + roi_h, x0 : x0 + roi_w]
    if roi.size == 0:
        roi = frame
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_32F).var())


def compute_center_bias(bbox: dict[str, int], width: int, height: int) -> float:
    center_x, center_y = bbox_center(bbox)
    return max(
        abs(center_x - float(width) * 0.5) / max(1.0, float(width)),
        abs(center_y - float(height) * 0.5) / max(1.0, float(height)),
    )


def quality_terms(
    frame,
    feature: dict[str, object],
) -> dict[str, float]:
    image_size = feature["image_size"]
    bbox = feature["face_bbox"]
    face_ratio = float(feature["face_ratio"])
    sharpness = compute_sharpness(frame, bbox)
    center_bias = compute_center_bias(bbox, image_size["width"], image_size["height"])
    sharpness_term = min(sharpness / 160.0, 1.0)
    face_ratio_term = max(0.0, 1.0 - min(abs(face_ratio - 0.085) / 0.065, 1.0))
    center_term = max(0.0, 1.0 - min(center_bias / 0.40, 1.0))
    score = round(0.48 * sharpness_term + 0.32 * face_ratio_term + 0.20 * center_term, 6)
    return {
        "sharpness": round(sharpness, 6),
        "center_bias": round(center_bias, 6),
        "sharpness_term": round(sharpness_term, 6),
        "face_ratio_term": round(face_ratio_term, 6),
        "center_term": round(center_term, 6),
        "pose_selection_score": score,
    }


def resolved_quality_thresholds(args: argparse.Namespace, pitch_1deg: int) -> dict[str, float]:
    if int(pitch_1deg) >= int(args.extreme_pitch_threshold):
        return {
            "min_face_ratio": float(args.extreme_pitch_min_face_ratio),
            "max_center_bias": float(args.extreme_pitch_max_center_bias),
            "min_sharpness": float(args.extreme_pitch_min_sharpness),
        }
    if int(pitch_1deg) >= int(args.high_pitch_threshold):
        return {
            "min_face_ratio": float(args.high_pitch_min_face_ratio),
            "max_center_bias": float(args.high_pitch_max_center_bias),
            "min_sharpness": float(args.high_pitch_min_sharpness),
        }
    return {
        "min_face_ratio": float(args.min_face_ratio),
        "max_center_bias": float(args.max_center_bias),
        "min_sharpness": float(args.min_sharpness),
    }


def materialize_selected_frames(
    selected_rows: list[dict[str, object]],
    selected_dir: Path,
) -> None:
    for row in selected_rows:
        selected_path = Path(row["selected_frame_path"])
        selected_path.parent.mkdir(parents=True, exist_ok=True)
        source_path = Path(row["all_frame_path"])
        if selected_path.exists():
            selected_path.unlink()
        shutil.copy2(source_path, selected_path)


def selected_pose_key(item: dict[str, object]) -> tuple[int, int, int] | None:
    angles = item.get("angles_1deg")
    if not isinstance(angles, dict):
        return None
    try:
        return (
            int(angles["yaw"]),
            int(angles["pitch"]),
            int(angles["roll"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def build_seed_row_from_selected_frame(image_path: Path, output_dir: Path) -> dict[str, object] | None:
    match = SELECTED_FRAME_RE.match(image_path.name)
    if not match:
        return None

    yaw_i = int(match.group("yaw"))
    pitch_i = int(match.group("pitch"))
    roll_i = int(match.group("roll"))
    frame_index = int(match.group("frame"))
    all_name = f"frame_{frame_index:06d}.png"
    all_frame_path = output_dir / "all_frames" / all_name
    return {
        "frame_index": frame_index,
        "file": all_name,
        "all_frame_path": str(all_frame_path.resolve()) if all_frame_path.is_file() else None,
        "ok": True,
        "angles": {"pitch": float(pitch_i), "yaw": float(yaw_i), "roll": float(roll_i)},
        "angles_1deg": {"pitch": pitch_i, "yaw": yaw_i, "roll": roll_i},
        "selected": True,
        "duplicate_rounded_pose": False,
        "existing_rounded_pose": True,
        "selected_frame_path": str(image_path.resolve()),
        "seed_source": "selected_frames_scan",
    }


def merge_seed_row(
    rows_by_path: dict[str, dict[str, object]],
    pose_keys: set[tuple[int, int, int]],
    row: dict[str, object],
) -> None:
    pose_key = selected_pose_key(row)
    selected_frame_path = row.get("selected_frame_path")
    if pose_key is None or not isinstance(selected_frame_path, str):
        return
    rows_by_path[str(Path(selected_frame_path).resolve())] = row
    pose_keys.add(pose_key)


def load_existing_selected_rows(
    output_dir: Path,
    explicit_json_path: Path | None,
    enabled: bool,
) -> tuple[list[dict[str, object]], set[tuple[int, int, int]], dict[str, object]]:
    if not enabled:
        return [], set(), {"json_path": None, "json_rows": 0, "scanned_frame_rows": 0}

    rows_by_path: dict[str, dict[str, object]] = {}
    pose_keys: set[tuple[int, int, int]] = set()
    seed_info = {"json_path": None, "json_rows": 0, "scanned_frame_rows": 0}

    json_candidates: list[Path] = []
    if explicit_json_path is not None:
        json_candidates.append(explicit_json_path)
    default_json_path = output_dir / "selected_pose.json"
    if default_json_path not in json_candidates:
        json_candidates.append(default_json_path)

    for json_path in json_candidates:
        if not json_path.is_file():
            continue
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        for item in payload.get("items", []):
            if isinstance(item, dict):
                merge_seed_row(rows_by_path, pose_keys, item)
        seed_info["json_path"] = str(json_path.resolve())
        seed_info["json_rows"] = len(rows_by_path)
        break

    selected_dir = output_dir / "selected_frames"
    if selected_dir.is_dir():
        for image_path in sorted(path for path in selected_dir.iterdir() if path.is_file()):
            row = build_seed_row_from_selected_frame(image_path, output_dir)
            if row is None:
                continue
            selected_frame_path = str(image_path.resolve())
            if selected_frame_path in rows_by_path:
                continue
            merge_seed_row(rows_by_path, pose_keys, row)
            seed_info["scanned_frame_rows"] += 1

    rows = sorted(
        rows_by_path.values(),
        key=lambda item: (int(item.get("frame_index", 0)), str(item.get("selected_frame_path", ""))),
    )
    return rows, pose_keys, seed_info


def main() -> None:
    args = parse_args()
    video_path = Path(args.video)
    output_dir = Path(args.output_dir)
    model_path = Path(args.model_path)

    if not video_path.is_file():
        raise SystemExit(f"Video file does not exist: {video_path}")
    if not model_path.is_file():
        raise SystemExit(f"Model file does not exist: {model_path}")
    if args.frame_step < 1:
        raise SystemExit("--frame-step must be >= 1")
    if args.num_faces < 1:
        raise SystemExit("--num-faces must be >= 1")
    if args.start_sec < 0:
        raise SystemExit("--start-sec must be >= 0")
    if args.end_sec is not None and args.end_sec <= args.start_sec:
        raise SystemExit("--end-sec must be greater than --start-sec")

    all_frames_dir, selected_dir = ensure_dirs(output_dir)
    explicit_selected_pose_json = (
        Path(args.existing_selected_pose_json).resolve() if args.existing_selected_pose_json else None
    )
    seeded_selected_rows, existing_pose_keys, seed_info = load_existing_selected_rows(
        output_dir=output_dir,
        explicit_json_path=explicit_selected_pose_json,
        enabled=args.skip_existing_rounded_pose,
    )
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise SystemExit(f"Failed to open video: {video_path}")
    fps = capture.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        raise SystemExit("Failed to read FPS from video")
    start_frame = int(math.floor(args.start_sec * fps))
    end_frame = None if args.end_sec is None else int(math.floor(args.end_sec * fps))
    capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    landmarker = build_landmarker(model_path, delegate=args.delegate, num_faces=args.num_faces)
    all_rows: list[dict[str, object]] = []
    selected_rows_by_path: dict[str, dict[str, object]] = {}
    selected_rows_by_pose: dict[tuple[int, int, int], dict[str, object]] = {}
    for row in seeded_selected_rows:
        selected_rows_by_path[str(Path(row["selected_frame_path"]).resolve())] = row
    seen_pose: set[tuple[int, int, int]] = set()
    known_pose_keys = set(existing_pose_keys)
    new_selected_count = 0
    reference_face_bbox: dict[str, object] | None = None

    frame_index = start_frame
    processed_count = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if end_frame is not None and frame_index > end_frame:
                break
            current_frame_index = frame_index
            frame_index += 1
            if current_frame_index % args.frame_step != 0:
                continue

            processed_count += 1
            frame = crop_center(frame, args.crop_center_width, args.crop_center_height)
            all_name = f"frame_{current_frame_index:06d}.png"
            all_path = all_frames_dir / all_name
            if not all_path.is_file():
                save_frame(all_path, frame, args.jpeg_quality)

            row: dict[str, object] = {
                "frame_index": current_frame_index,
                "file": all_name,
                "all_frame_path": str(all_path.resolve()),
                "ok": False,
            }

            feature = extract_feature_from_frame_bgr(
                frame,
                landmarker,
                file_name=all_name,
                reference_face_bbox=reference_face_bbox,
            )

            if feature.get("ok"):
                pose = feature["pose"]
                pitch = float(pose["pitch_float"])
                yaw = float(pose["yaw_float"])
                roll = float(pose["roll_float"])
                pitch_i = int(pose["pitch_1deg"])
                yaw_i = int(pose["yaw_1deg"])
                roll_i = int(pose["roll_1deg"])
                metrics = quality_terms(frame, feature)
                quality_gate = resolved_quality_thresholds(args, pitch_i)
                quality_ok = (
                    float(feature["face_ratio"]) >= quality_gate["min_face_ratio"]
                    and metrics["center_bias"] <= quality_gate["max_center_bias"]
                    and metrics["sharpness"] >= quality_gate["min_sharpness"]
                )
                reference_ok = (
                    float(feature["face_ratio"]) >= min(float(args.min_face_ratio), quality_gate["min_face_ratio"])
                    and metrics["center_bias"] <= max(float(args.max_center_bias), quality_gate["max_center_bias"] + 0.06)
                )
                if reference_ok:
                    reference_face_bbox = feature["face_bbox"]
                in_range = (
                    args.yaw_min <= yaw_i <= args.yaw_max
                    and args.pitch_min <= pitch_i <= args.pitch_max
                    and args.roll_min <= roll_i <= args.roll_max
                )
                pose_key = (yaw_i, pitch_i, roll_i)
                is_duplicate_pose = (args.dedupe_rounded_pose or args.best_per_rounded_pose) and pose_key in seen_pose
                is_existing_pose = args.skip_existing_rounded_pose and pose_key in known_pose_keys
                row.update(
                    {
                        "ok": True,
                        "image_size": feature["image_size"],
                        "angles": {"pitch": pitch, "yaw": yaw, "roll": roll},
                        "angles_1deg": {"pitch": pitch_i, "yaw": yaw_i, "roll": roll_i},
                        "selected": False,
                        "duplicate_rounded_pose": is_duplicate_pose,
                        "existing_rounded_pose": is_existing_pose,
                        "quality_ok": quality_ok,
                        "face_bbox": feature["face_bbox"],
                        "face_ratio": feature["face_ratio"],
                        "face_index": feature["face_index"],
                        "candidate_face_count": feature["candidate_face_count"],
                        "anchors": feature["anchors"],
                        "quality_metrics": metrics,
                        "quality_gate": quality_gate,
                    }
                )

                if in_range and quality_ok and not is_existing_pose:
                    selected_name = (
                        f"yaw{yaw_i:+03d}_pitch{pitch_i:+03d}_roll{roll_i:+03d}_"
                        f"frame{current_frame_index:06d}.png"
                    )
                    candidate_row = dict(row)
                    candidate_row["selected_frame_path"] = str((selected_dir / selected_name).resolve())
                    if args.best_per_rounded_pose:
                        existing_row = selected_rows_by_pose.get(pose_key)
                        candidate_score = float(metrics["pose_selection_score"])
                        existing_score = (
                            float(existing_row["quality_metrics"]["pose_selection_score"])
                            if existing_row is not None
                            else -1.0
                        )
                        if (
                            existing_row is None
                            or candidate_score > existing_score
                            or (
                                math.isclose(candidate_score, existing_score)
                                and float(metrics["sharpness"]) > float(existing_row["quality_metrics"]["sharpness"])
                            )
                        ):
                            selected_rows_by_pose[pose_key] = candidate_row
                    elif not is_duplicate_pose:
                        selected_rows_by_path[str(Path(candidate_row["selected_frame_path"]).resolve())] = candidate_row
                        known_pose_keys.add(pose_key)
                        new_selected_count += 1
                    seen_pose.add(pose_key)
            else:
                row["reason"] = str(feature.get("reason", "no_face_or_pose"))

            all_rows.append(row)
    finally:
        capture.release()
        landmarker.close()

    if args.best_per_rounded_pose:
        selected_rows = sorted(
            selected_rows_by_pose.values(),
            key=lambda item: (int(item.get("frame_index", 0)), str(item.get("selected_frame_path", ""))),
        )
        selected_rows_by_path = {
            str(Path(item["selected_frame_path"]).resolve()): item
            for item in selected_rows
        }
        known_pose_keys.update(selected_rows_by_pose.keys())
        new_selected_count = len(selected_rows)
    else:
        selected_rows = sorted(
            selected_rows_by_path.values(),
            key=lambda item: (int(item.get("frame_index", 0)), str(item.get("selected_frame_path", ""))),
        )

    materialize_selected_frames(selected_rows, selected_dir)
    selected_all_frame_paths = {str(item["all_frame_path"]) for item in selected_rows}
    for row in all_rows:
        row["selected"] = str(row.get("all_frame_path")) in selected_all_frame_paths

    summary = {
        "video": str(video_path.resolve()),
        "model_path": str(model_path.resolve()),
        "delegate": args.delegate,
        "num_faces": args.num_faces,
        "frame_step": args.frame_step,
        "fps": fps,
        "start_sec": args.start_sec,
        "end_sec": args.end_sec,
        "start_frame": start_frame,
        "end_frame": end_frame,
        "processed_frames": processed_count,
        "total_rows": len(all_rows),
        "selected_frames": len(selected_rows),
        "selected_frames_new": new_selected_count,
        "dedupe_rounded_pose": args.dedupe_rounded_pose,
        "best_per_rounded_pose": args.best_per_rounded_pose,
        "skip_existing_rounded_pose": args.skip_existing_rounded_pose,
        "existing_selected_pose_json": seed_info["json_path"],
        "seeded_pose_keys": len(existing_pose_keys),
        "seeded_selected_rows": len(seeded_selected_rows),
        "seeded_rows_from_selected_frames_scan": seed_info["scanned_frame_rows"],
        "crop_center_width": args.crop_center_width,
        "crop_center_height": args.crop_center_height,
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
        "ranges": {
            "yaw": [args.yaw_min, args.yaw_max],
            "pitch": [args.pitch_min, args.pitch_max],
            "roll": [args.roll_min, args.roll_max],
        },
    }

    (output_dir / "all_pose.json").write_text(
        json.dumps({"summary": summary, "items": all_rows}, indent=2),
        encoding="utf-8",
    )
    (output_dir / "selected_pose.json").write_text(
        json.dumps({"summary": summary, "items": selected_rows}, indent=2),
        encoding="utf-8",
    )

    with (output_dir / "selected_pose.csv").open("w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerow(
            [
                "frame_index",
                "file",
                "yaw_1deg",
                "pitch_1deg",
                "roll_1deg",
                "selected_frame_path",
            ]
        )
        for item in selected_rows:
            writer.writerow(
                [
                    item["frame_index"],
                    item["file"],
                    item["angles_1deg"]["yaw"],
                    item["angles_1deg"]["pitch"],
                    item["angles_1deg"]["roll"],
                    item.get("selected_frame_path", ""),
                ]
            )

    print(
        json.dumps(
            {
                "processed_frames": processed_count,
                "selected_frames": len(selected_rows),
                "selected_frames_new": new_selected_count,
                "seeded_pose_keys": len(existing_pose_keys),
                "output_dir": str(output_dir.resolve()),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
