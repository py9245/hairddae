from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import statistics
import sys
import time

import cv2


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.auth import TicketClaims
from app.config import Settings
from app.face_tracking import ServerFaceTracker
from app.frame_prepare_pipeline import TrackingCacheSnapshot, prepare_runtime_frame
from app.hair_attenuation import HairAttenuator
from app.hair_segmentation import HairSegmenter
from app.hairddae_runtime_manager import HairddaeRuntimeManager
from cv2_cuda_utils import opencv_resize


def load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value and len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def parse_stage(value: str) -> tuple[int, int]:
    width_raw, height_raw = value.lower().split("x", 1)
    width = int(width_raw)
    height = int(height_raw)
    if width <= 0 or height <= 0:
        raise ValueError("stage dimensions must be positive")
    return width, height


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    index = (len(ordered) - 1) * ratio
    low = int(index)
    high = min(len(ordered) - 1, low + 1)
    weight = index - low
    return float(ordered[low] + (ordered[high] - ordered[low]) * weight)


def resize_for_processing(frame_bgr, max_dimension: int):
    height, width = frame_bgr.shape[:2]
    if max_dimension <= 0 or max(width, height) <= max_dimension:
        return frame_bgr
    scale = float(max_dimension) / float(max(width, height))
    resized_width = max(1, int(round(width * scale)))
    resized_height = max(1, int(round(height * scale)))
    return opencv_resize(frame_bgr, (resized_width, resized_height), interpolation=cv2.INTER_AREA)


def make_claims(hair_id: int, dataset_code: str) -> TicketClaims:
    return TicketClaims(
        user_id="gputest-user",
        apply_session_id="gputest-session",
        device_id="gputest-device",
        hair_id=hair_id,
        node_id="infer-gpu-01",
        schema_version=2,
        dataset_code=dataset_code,
        representative_asset_id=None,
        token_id="gputest-token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )


def build_hair_attenuator(settings: Settings) -> HairAttenuator:
    return HairAttenuator(
        segmentation_confidence_threshold=settings.rtc_hair_segmentation_confidence_threshold,
        strength=settings.rtc_hair_attenuation_strength,
        desaturation=settings.rtc_hair_attenuation_desaturation,
        brightness_lift=settings.rtc_hair_attenuation_brightness_lift,
        blur_kernel_scale=settings.rtc_hair_attenuation_blur_kernel_scale,
        max_work_dimension=settings.rtc_hair_attenuation_max_work_dimension,
        bald_test_mode=settings.rtc_bald_test_mode,
        preserve_eyes_enabled=settings.rtc_preserve_eyes_enabled,
        disable_fringe_suppression=settings.rtc_disable_fringe_suppression,
        disable_covered_suppression=settings.rtc_disable_covered_suppression,
        disable_outer_bulk_suppression=settings.rtc_disable_outer_bulk_suppression,
    )


def run_profile(
    *,
    profile_name: str,
    base_frame_bgr,
    process_max_dimension: int,
    iterations: int,
    prefer_latency: bool,
    settings: Settings,
    claims: TicketClaims,
    dataset_code: str,
    representative_asset_id: str | None,
):
    frame_bgr = resize_for_processing(base_frame_bgr, process_max_dimension)
    face_tracker = ServerFaceTracker(
        settings.face_landmarker_model_path,
        num_faces=settings.face_tracker_num_faces,
        delegate=settings.face_tracker_delegate,
    )
    hair_segmenter = HairSegmenter(
        settings.hair_segmenter_model_path,
        delegate=settings.hair_segmenter_delegate,
    )
    hair_attenuator = build_hair_attenuator(settings)
    runtime_manager = HairddaeRuntimeManager(settings)
    prepare_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="gputest-prepare")
    snapshot = TrackingCacheSnapshot(user_row=None, landmarks_px=None, feature=None)

    total_samples: list[float] = []
    prepare_samples: list[float] = []
    runtime_samples: list[float] = []
    tracking_samples: list[float] = []
    segmentation_samples: list[float] = []
    attenuation_samples: list[float] = []
    overlay_samples: list[float] = []

    try:
        for seq in range(1, iterations + 1):
            started_at = time.perf_counter()
            prepare_started_at = time.perf_counter()
            prepared = prepare_runtime_frame(
                frame_bgr,
                seq=seq,
                face_tracker=face_tracker,
                hair_segmenter=hair_segmenter,
                hair_attenuator=hair_attenuator,
                hair_runtime_manager=runtime_manager,
                claims=claims,
                settings=settings,
                active_dataset_code=dataset_code,
                active_hair_id=claims.hair_id,
                prepare_executor=prepare_executor,
                previous_tracking_snapshot=snapshot,
            )
            prepare_ms = (time.perf_counter() - prepare_started_at) * 1000.0
            snapshot = prepared.tracking_snapshot

            runtime_started_at = time.perf_counter()
            runtime_result = runtime_manager.process_frame(
                dataset_code=dataset_code,
                frame_bgr=frame_bgr,
                render_frame_bgr=prepared.prepared_frame_bgr,
                source_frame_bgr=prepared.prepared_frame_bgr,
                tracked_user_row=prepared.tracked_user_row,
                prefer_latency=prefer_latency,
                session_id=claims.apply_session_id,
                representative_asset_id=representative_asset_id,
            )
            runtime_ms = (time.perf_counter() - runtime_started_at) * 1000.0
            total_ms = (time.perf_counter() - started_at) * 1000.0

            total_samples.append(total_ms)
            prepare_samples.append(prepare_ms)
            runtime_samples.append(runtime_ms)
            tracking_samples.append(float(prepared.metrics.tracking_latency_ms))
            segmentation_samples.append(float(prepared.metrics.hair_segmentation_latency_ms))
            attenuation_samples.append(float(prepared.metrics.hair_attenuation_latency_ms))
            overlay_samples.append(float(runtime_result.get("overlay_latency_ms", 0.0) or 0.0))
    finally:
        prepare_executor.shutdown(wait=True, cancel_futures=False)
        runtime_manager.close()
        hair_attenuator.close()
        hair_segmenter.close()
        face_tracker.close()

    return {
        "profile": profile_name,
        "input_shape": {
            "width": int(base_frame_bgr.shape[1]),
            "height": int(base_frame_bgr.shape[0]),
        },
        "processing_shape": {
            "width": int(frame_bgr.shape[1]),
            "height": int(frame_bgr.shape[0]),
        },
        "iterations": iterations,
        "prefer_latency": prefer_latency,
        "metrics_ms": {
            "e2e_total": {
                "avg": round(statistics.fmean(total_samples), 3),
                "p50": round(percentile(total_samples, 0.5), 3),
                "p95": round(percentile(total_samples, 0.95), 3),
            },
            "prepare_wall": {
                "avg": round(statistics.fmean(prepare_samples), 3),
                "p50": round(percentile(prepare_samples, 0.5), 3),
                "p95": round(percentile(prepare_samples, 0.95), 3),
            },
            "runtime_wall": {
                "avg": round(statistics.fmean(runtime_samples), 3),
                "p50": round(percentile(runtime_samples, 0.5), 3),
                "p95": round(percentile(runtime_samples, 0.95), 3),
            },
            "tracking": {
                "avg": round(statistics.fmean(tracking_samples), 3),
                "p50": round(percentile(tracking_samples, 0.5), 3),
                "p95": round(percentile(tracking_samples, 0.95), 3),
            },
            "segmentation": {
                "avg": round(statistics.fmean(segmentation_samples), 3),
                "p50": round(percentile(segmentation_samples, 0.5), 3),
                "p95": round(percentile(segmentation_samples, 0.95), 3),
            },
            "attenuation": {
                "avg": round(statistics.fmean(attenuation_samples), 3),
                "p50": round(percentile(attenuation_samples, 0.5), 3),
                "p95": round(percentile(attenuation_samples, 0.95), 3),
            },
            "overlay": {
                "avg": round(statistics.fmean(overlay_samples), 3),
                "p50": round(percentile(overlay_samples, 0.5), 3),
                "p95": round(percentile(overlay_samples, 0.95), 3),
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark current pipeline at reduced vs near-native processing resolution")
    parser.add_argument("--image", default=str(REPO_ROOT / "testimage" / "긴머리_test.png"))
    parser.add_argument("--stage", default="576x1024")
    parser.add_argument("--dataset-code", default="0001")
    parser.add_argument("--hair-id", type=int, default=1)
    parser.add_argument("--iterations", type=int, default=8)
    parser.add_argument("--process-dim", action="append", type=int, help="Process max dimension profile. Repeatable.")
    parser.add_argument("--prefer-latency", action="store_true", default=True)
    parser.add_argument("--output-json", default="")
    args = parser.parse_args()

    load_env_file(REPO_ROOT / ".env.server")
    settings = Settings.from_env()
    claims = make_claims(args.hair_id, args.dataset_code)

    image_path = Path(args.image).expanduser().resolve()
    frame_bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if frame_bgr is None:
        raise FileNotFoundError(f"failed to load image: {image_path}")

    stage_width, stage_height = parse_stage(args.stage)
    base_frame_bgr = cv2.resize(frame_bgr, (stage_width, stage_height), interpolation=cv2.INTER_AREA)

    dims = args.process_dim or [400, 560, max(stage_width, stage_height)]
    results = []
    for process_dim in dims:
        profile_name = f"process_max_dimension_{process_dim}"
        print(f"[gputest] running {profile_name} on stage {stage_width}x{stage_height} iterations={args.iterations}", flush=True)
        results.append(
            run_profile(
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
