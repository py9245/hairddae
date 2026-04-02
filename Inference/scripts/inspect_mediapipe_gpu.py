from __future__ import annotations

from pathlib import Path
import traceback

import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


REPO_ROOT = Path(__file__).resolve().parent.parent
FACE_MODEL_PATH = REPO_ROOT / "models" / "face_landmarker.task"
HAIR_MODEL_PATH = REPO_ROOT / "models" / "mediapipe" / "hair_segmenter.tflite"


def _try_face_landmarker() -> str:
    options = vision.FaceLandmarkerOptions(
        base_options=python.BaseOptions(
            model_asset_path=str(FACE_MODEL_PATH),
            delegate=python.BaseOptions.Delegate.GPU,
        ),
        running_mode=vision.RunningMode.IMAGE,
        num_faces=1,
    )
    detector = vision.FaceLandmarker.create_from_options(options)
    try:
        image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=np.zeros((32, 32, 3), dtype=np.uint8),
        )
        detector.detect(image)
    finally:
        detector.close()
    return "ok"


def _try_hair_segmenter() -> str:
    options = vision.ImageSegmenterOptions(
        base_options=python.BaseOptions(
            model_asset_path=str(HAIR_MODEL_PATH),
            delegate=python.BaseOptions.Delegate.GPU,
        ),
        running_mode=vision.RunningMode.VIDEO,
        output_confidence_masks=True,
        output_category_mask=False,
    )
    segmenter = vision.ImageSegmenter.create_from_options(options)
    try:
        image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=np.zeros((32, 32, 3), dtype=np.uint8),
        )
        segmenter.segment_for_video(image, 1)
    finally:
        segmenter.close()
    return "ok"


def _run(label: str, fn) -> None:
    try:
        result = fn()
        print(f"{label}=ok")
        print(f"{label}_result={result}")
    except Exception as exc:
        print(f"{label}=error")
        print(f"{label}_error={exc}")
        print(traceback.format_exc().strip())


def main() -> int:
    print(f"mediapipe_version={mp.__version__}")
    print(f"face_model_exists={FACE_MODEL_PATH.is_file()}")
    print(f"hair_model_exists={HAIR_MODEL_PATH.is_file()}")
    _run("face_landmarker_gpu", _try_face_landmarker)
    _run("hair_segmenter_gpu", _try_hair_segmenter)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
