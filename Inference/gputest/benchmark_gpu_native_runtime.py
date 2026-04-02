from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import time

import cv2


CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parents[0]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

import benchmark_native_e2e as native
from app.face_tracking import ServerFaceTracker
from app.frame_prepare_pipeline import TrackingCacheSnapshot, prepare_runtime_frame
from app.hair_segmentation import HairSegmenter
from gpu_attenuation import GpuNativeHairAttenuator
from gpu_native_runtime import GpuNativeRuntimeManager


def build_gpu_attenuator(settings: native.Settings) -> GpuNativeHairAttenuator:
    return GpuNativeHairAttenuator(
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark gputest rebuilt GPU-native runtime")
    parser.add_argument("--image", default=str(REPO_ROOT / "testimage" / "긴머리_test.png"))
    parser.add_argument("--stage", default="576x1024")
    parser.add_argument("--dataset-code", default="0009")
    parser.add_argument("--hair-id", type=int, default=3)
    parser.add_argument("--iterations", type=int, default=4)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--process-dim", type=int, default=1024)
    parser.add_argument("--output-json", default="")
    args = parser.parse_args()

    native.load_env_file(REPO_ROOT / ".env.server")
    os.environ["INFERENCE_RTC_BUNDLE_RENDER_ENABLED"] = "0"
    os.environ["INFERENCE_RTC_RENDERER_NAME"] = "legacy"
    os.environ["INFERENCE_RTC_LATENCY_RENDERER_NAME"] = "legacy"
    os.environ["INFERENCE_RTC_LIGHTWEIGHT_RENDERER_NAME"] = "legacy"
    settings = native.Settings.from_env()
    claims = native.make_claims(args.hair_id, args.dataset_code)

    image_path = Path(args.image).expanduser().resolve()
    frame_bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if frame_bgr is None:
        raise FileNotFoundError(f"failed to load image: {image_path}")
    stage_width, stage_height = native.parse_stage(args.stage)
    base_frame_bgr = cv2.resize(frame_bgr, (stage_width, stage_height), interpolation=cv2.INTER_AREA)
    frame_bgr = native.resize_for_processing(base_frame_bgr, args.process_dim)

    face_tracker = ServerFaceTracker(
        settings.face_landmarker_model_path,
        num_faces=settings.face_tracker_num_faces,
        delegate=settings.face_tracker_delegate,
    )
    hair_segmenter = HairSegmenter(
        settings.hair_segmenter_model_path,
        delegate=settings.hair_segmenter_delegate,
    )
    hair_attenuator = build_gpu_attenuator(settings)
    runtime_manager = GpuNativeRuntimeManager(settings)
    prepare_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="gputest-gpu-prepare")
    snapshot = TrackingCacheSnapshot(user_row=None, landmarks_px=None, feature=None)

    samples: dict[str, list[float]] = {
        "e2e_total": [],
        "prepare_wall": [],
        "runtime_wall": [],
        "tracking": [],
        "segmentation": [],
        "attenuation": [],
        "overlay": [],
    }
    total_loops = max(1, int(args.iterations)) + max(0, int(args.warmup))
    try:
        for seq in range(1, total_loops + 1):
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
                active_dataset_code=args.dataset_code,
                active_hair_id=claims.hair_id,
                prepare_executor=prepare_executor,
                previous_tracking_snapshot=snapshot,
            )
            prepare_ms = (time.perf_counter() - prepare_started_at) * 1000.0
            snapshot = prepared.tracking_snapshot
            runtime_started_at = time.perf_counter()
            result = runtime_manager.process_frame(
                dataset_code=args.dataset_code,
                frame_bgr=frame_bgr,
                render_frame_bgr=prepared.prepared_frame_bgr,
                source_frame_bgr=prepared.prepared_frame_bgr,
                tracked_user_row=prepared.tracked_user_row,
                prefer_latency=True,
                session_id=claims.apply_session_id,
                representative_asset_id=None,
            )
            runtime_ms = (time.perf_counter() - runtime_started_at) * 1000.0
            total_ms = (time.perf_counter() - started_at) * 1000.0

            if seq > int(args.warmup):
                samples["e2e_total"].append(total_ms)
                samples["prepare_wall"].append(prepare_ms)
                samples["runtime_wall"].append(runtime_ms)
                samples["tracking"].append(float(prepared.metrics.tracking_latency_ms))
                samples["segmentation"].append(float(prepared.metrics.hair_segmentation_latency_ms))
                samples["attenuation"].append(float(prepared.metrics.hair_attenuation_latency_ms))
                samples["overlay"].append(float(result.get("overlay_latency_ms", 0.0) or 0.0))
    finally:
        prepare_executor.shutdown(wait=True, cancel_futures=False)
        runtime_manager.close()
        hair_attenuator.close()
        hair_segmenter.close()
        face_tracker.close()

    payload = {
        "mode": "gpu_native_runtime_rebuild",
        "image": str(image_path),
        "stage": {"width": stage_width, "height": stage_height},
        "processing_shape": {"width": int(frame_bgr.shape[1]), "height": int(frame_bgr.shape[0])},
        "dataset_code": args.dataset_code,
        "hair_id": args.hair_id,
        "iterations": args.iterations,
        "warmup": args.warmup,
        "metrics_ms": {
            key: {
                "avg": round(sum(values) / max(1, len(values)), 3),
                "p50": round(native.percentile(values, 0.5), 3),
                "p95": round(native.percentile(values, 0.95), 3),
            }
            for key, values in samples.items()
        },
    }
    if args.output_json:
        output_path = Path(args.output_json).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
