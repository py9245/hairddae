from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from concurrent.futures import ThreadPoolExecutor
import sys

import cv2
import numpy as np
import torch
from torchvision.models.segmentation import (
    LRASPP_MobileNet_V3_Large_Weights,
    lraspp_mobilenet_v3_large,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.face_tracking import ServerFaceTracker
from app.hair_segmentation import HairSegmenter


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--face-model", type=Path, default=Path("models/face_landmarker.task"))
    parser.add_argument("--hair-model", type=Path, default=Path("models/mediapipe/hair_segmenter.tflite"))
    parser.add_argument(
        "--body-weights",
        type=Path,
        default=Path("models/torchvision/lraspp_mobilenet_v3_large-coco_with_voc_labels_v1.pth"),
    )
    parser.add_argument("--runs", type=int, default=12)
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--threshold", type=float, default=0.35)
    parser.add_argument("--body-precision", choices=("fp32", "fp16"), default="fp32")
    return parser.parse_args()


class _Claims:
    apply_session_id = "parallel-body-seg-poc"


class _Settings:
    feature_schema_version = 2
    transform_version = "affine_v1"


def _build_body_runner(
    *,
    weights_path: Path,
    threshold: float,
    precision: str,
) -> tuple[callable, dict[str, object]]:
    torch.backends.cudnn.enabled = False
    weights = LRASPP_MobileNet_V3_Large_Weights.COCO_WITH_VOC_LABELS_V1
    categories = list(weights.meta.get("categories", []))
    person_index = int(categories.index("person"))

    model = lraspp_mobilenet_v3_large(weights=None, weights_backbone=None)
    state = torch.load(str(weights_path), map_location="cpu")
    model.load_state_dict(state)
    model = model.eval().to("cuda")
    if precision == "fp16":
        model = model.half()

    mean = torch.tensor([0.485, 0.456, 0.406], dtype=torch.float32, device="cuda").view(3, 1, 1)
    std = torch.tensor([0.229, 0.224, 0.225], dtype=torch.float32, device="cuda").view(3, 1, 1)
    if precision == "fp16":
        mean = mean.half()
        std = std.half()

    blank = np.zeros((256, 256, 3), dtype=np.uint8)
    blank_tensor = torch.from_numpy(blank.astype(np.float32) / 255.0).permute(2, 0, 1)
    blank_tensor = blank_tensor.to("cuda", non_blocking=True)
    if precision == "fp16":
        blank_tensor = blank_tensor.half()
    blank_tensor = ((blank_tensor - mean) / std).unsqueeze(0)
    with torch.inference_mode():
        _ = model(blank_tensor)["out"]
        torch.cuda.synchronize()

    def _run(frame_rgb: np.ndarray) -> tuple[float, tuple[int, int]]:
        started_at = time.perf_counter()
        image_np = frame_rgb.astype(np.float32) / 255.0
        tensor = torch.from_numpy(image_np).permute(2, 0, 1).to("cuda", non_blocking=True)
        if precision == "fp16":
            tensor = tensor.half()
        tensor = ((tensor - mean) / std).unsqueeze(0)
        with torch.inference_mode():
            logits = model(tensor)["out"]
            torch.cuda.synchronize()
        probs = torch.softmax(logits.float(), dim=1)[0, person_index]
        mask = (probs >= threshold).to(torch.uint8).mul_(255).cpu().numpy()
        latency_ms = (time.perf_counter() - started_at) * 1000.0
        return latency_ms, (int(mask.shape[0]), int(mask.shape[1]))

    metadata = {
        "body_model": "lraspp_mobilenet_v3_large",
        "body_precision": precision,
        "person_index": person_index,
        "weights_path": str(weights_path),
    }
    return _run, metadata


def _summarize(rows: list[dict[str, float]], key: str) -> dict[str, float]:
    values = sorted(float(row[key]) for row in rows)
    return {
        "avg": round(sum(values) / len(values), 3),
        "p50": round(values[len(values) // 2], 3),
        "min": round(values[0], 3),
        "max": round(values[-1], 3),
    }


def main() -> int:
    args = _parse_args()
    args.output_json.parent.mkdir(parents=True, exist_ok=True)

    frame_bgr = cv2.imread(str(args.image), cv2.IMREAD_COLOR)
    if frame_bgr is None:
        raise FileNotFoundError(f"failed to read image: {args.image}")
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

    face_tracker = ServerFaceTracker(args.face_model.resolve(), num_faces=1, delegate="gpu")
    hair_segmenter = HairSegmenter(args.hair_model.resolve(), delegate="gpu")
    body_run, body_meta = _build_body_runner(
        weights_path=args.body_weights.resolve(),
        threshold=float(args.threshold),
        precision=args.body_precision,
    )

    face_tracker.warm_up()
    hair_segmenter.warm_up()

    def _run_tracking() -> tuple[float, bool]:
        started_at = time.perf_counter()
        result = face_tracker.extract_tracking_result_from_rgb(
            frame_rgb,
            claims=_Claims(),
            settings=_Settings(),
            seq=1,
            ts_ms=int(time.time() * 1000),
            hair_id_override=11,
            reference_face_bbox=None,
        )
        return (time.perf_counter() - started_at) * 1000.0, bool(result is not None)

    def _run_hair_seg() -> tuple[float, tuple[int, int] | None]:
        started_at = time.perf_counter()
        mask = hair_segmenter.segment_hair_confidence_from_rgb(
            frame_rgb,
            timestamp_ms=int(time.time() * 1000),
        )
        latency_ms = (time.perf_counter() - started_at) * 1000.0
        return latency_ms, None if mask is None else (int(mask.shape[0]), int(mask.shape[1]))

    samples: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        for run_index in range(int(args.warmups) + int(args.runs)):
            total_started_at = time.perf_counter()
            tracking_future = executor.submit(_run_tracking)
            hair_future = executor.submit(_run_hair_seg)
            body_future = executor.submit(body_run, frame_rgb)

            tracking_ms, tracking_ok = tracking_future.result()
            hair_ms, hair_shape = hair_future.result()
            body_ms, body_shape = body_future.result()
            prepare_total_ms = (time.perf_counter() - total_started_at) * 1000.0

            if run_index < int(args.warmups):
                continue

            samples.append(
                {
                    "tracking_ms": round(tracking_ms, 3),
                    "hair_segmentation_ms": round(hair_ms, 3),
                    "body_segmentation_ms": round(body_ms, 3),
                    "prepare_total_ms": round(prepare_total_ms, 3),
                    "tracking_ok": tracking_ok,
                    "hair_shape": hair_shape,
                    "body_shape": body_shape,
                }
            )

    payload = {
        "image": str(args.image),
        "input_shape": [int(frame_rgb.shape[0]), int(frame_rgb.shape[1]), int(frame_rgb.shape[2])],
        "runs": int(args.runs),
        "warmups": int(args.warmups),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
        "tracking": _summarize(samples, "tracking_ms"),
        "hair_segmentation": _summarize(samples, "hair_segmentation_ms"),
        "body_segmentation": _summarize(samples, "body_segmentation_ms"),
        "prepare_total": _summarize(samples, "prepare_total_ms"),
        "body_meta": body_meta,
        "samples": samples,
    }
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
