from __future__ import annotations

from functools import lru_cache

import cv2
import numpy as np
from PIL import Image

from app.acceleration import detect_runtime_acceleration
from app.catalog import AssetBundle


@lru_cache(maxsize=64)
def _load_rgba_image(path: str) -> np.ndarray:
    image = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise FileNotFoundError(path)

    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGBA)
    elif image.shape[2] == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGBA)
    elif image.shape[2] == 4:
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA)
    else:
        raise ValueError(f"unsupported image shape for {path}: {image.shape}")

    return np.ascontiguousarray(image)


def _invert_affine(a: float, b: float, c: float, d: float, e: float, f: float) -> tuple[float, ...] | None:
    determinant = a * d - b * c
    if abs(determinant) < 1e-8:
        return None

    inv_a = d / determinant
    inv_b = -b / determinant
    inv_c = -c / determinant
    inv_d = a / determinant
    inv_e = (c * f - d * e) / determinant
    inv_f = (b * e - a * f) / determinant
    return (inv_a, inv_c, inv_e, inv_b, inv_d, inv_f)


def _scale_render_task(
    render_task: dict[str, object],
    reference_width: int,
    reference_height: int,
    frame_width: int,
    frame_height: int,
) -> dict[str, object]:
    if (
        reference_width <= 0
        or reference_height <= 0
        or frame_width <= 0
        or frame_height <= 0
        or (reference_width == frame_width and reference_height == frame_height)
    ):
        return render_task

    matrix = render_task.get("matrix")
    destination_roi = render_task.get("destination_roi")
    destination_quad = render_task.get("destination_quad")
    if not isinstance(matrix, dict) or not isinstance(destination_roi, dict):
        return render_task

    scale_x = frame_width / reference_width
    scale_y = frame_height / reference_height

    scaled_task = dict(render_task)
    scaled_task["matrix"] = {
        "a": float(matrix["a"]) * scale_x,
        "b": float(matrix["b"]) * scale_y,
        "c": float(matrix["c"]) * scale_x,
        "d": float(matrix["d"]) * scale_y,
        "e": float(matrix["e"]) * scale_x,
        "f": float(matrix["f"]) * scale_y,
    }
    scaled_task["destination_roi"] = {
        "x": int(round(float(destination_roi["x"]) * scale_x)),
        "y": int(round(float(destination_roi["y"]) * scale_y)),
        "w": int(round(float(destination_roi["w"]) * scale_x)),
        "h": int(round(float(destination_roi["h"]) * scale_y)),
    }
    if isinstance(destination_quad, list):
        scaled_task["destination_quad"] = [
            {
                "x": round(float(point["x"]) * scale_x, 3),
                "y": round(float(point["y"]) * scale_y, 3),
            }
            for point in destination_quad
            if isinstance(point, dict)
        ]
    return scaled_task


def _blend_rgba_over_rgb(base_roi: np.ndarray, overlay_rgba: np.ndarray) -> None:
    alpha = overlay_rgba[:, :, 3].astype(np.uint16)
    if not np.any(alpha):
        return

    inverse_alpha = 255 - alpha
    blended = (
        (
            overlay_rgba[:, :, :3].astype(np.uint16) * alpha[:, :, None]
            + base_roi.astype(np.uint16) * inverse_alpha[:, :, None]
            + 127
        )
        // 255
    ).astype(np.uint8)
    mask = alpha > 0
    base_roi[mask] = blended[mask]


def _normalized_acceleration_preference(preference: str) -> str:
    resolved = preference.strip().lower()
    if resolved in {"auto", "cpu", "opencv_cuda"}:
        return resolved
    return "auto"


def _cuda_gpu_mat_ctor():
    if hasattr(cv2, "cuda_GpuMat"):
        return cv2.cuda_GpuMat
    cuda_module = getattr(cv2, "cuda", None)
    if cuda_module is not None and hasattr(cuda_module, "GpuMat"):
        return cuda_module.GpuMat
    return None


def _opencv_cuda_warp_enabled(preference: str) -> bool:
    if _normalized_acceleration_preference(preference) == "cpu":
        return False
    return detect_runtime_acceleration().opencv_cuda_warp_affine_available


def _opencv_cuda_alpha_enabled(preference: str) -> bool:
    if _normalized_acceleration_preference(preference) == "cpu":
        return False
    return detect_runtime_acceleration().opencv_cuda_alpha_comp_available


@lru_cache(maxsize=64)
def _load_rgba_image_gpu(path: str):
    gpu_mat_ctor = _cuda_gpu_mat_ctor()
    if gpu_mat_ctor is None:
        raise RuntimeError("OpenCV CUDA GpuMat is unavailable")

    gpu_mat = gpu_mat_ctor()
    gpu_mat.upload(_load_rgba_image(path))
    return gpu_mat


def _warp_rgba_patch_cuda(
    path: str,
    inverse_matrix: np.ndarray,
    roi_width: int,
    roi_height: int,
    *,
    acceleration_preference: str,
):
    if not _opencv_cuda_warp_enabled(acceleration_preference):
        return None

    cuda_module = getattr(cv2, "cuda", None)
    if cuda_module is None or not hasattr(cuda_module, "warpAffine"):
        return None

    try:
        return cuda_module.warpAffine(
            _load_rgba_image_gpu(path),
            inverse_matrix,
            (roi_width, roi_height),
            flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0, 0),
        )
    except Exception:
        return None


def _download_cuda_mat(gpu_mat) -> np.ndarray | None:
    try:
        return gpu_mat.download()
    except Exception:
        return None


def _blend_rgba_over_rgb_cuda(
    base_roi: np.ndarray,
    overlay_rgba_gpu,
    *,
    acceleration_preference: str,
) -> np.ndarray | None:
    if not _opencv_cuda_alpha_enabled(acceleration_preference):
        return None

    cuda_module = getattr(cv2, "cuda", None)
    gpu_mat_ctor = _cuda_gpu_mat_ctor()
    if cuda_module is None or gpu_mat_ctor is None:
        return None

    try:
        base_gpu = gpu_mat_ctor()
        base_gpu.upload(base_roi)
        base_rgba_gpu = cuda_module.cvtColor(base_gpu, cv2.COLOR_RGB2RGBA)
        blended_rgba_gpu = cuda_module.alphaComp(
            overlay_rgba_gpu,
            base_rgba_gpu,
            cuda_module.ALPHA_OVER,
        )
        blended_rgb_gpu = cuda_module.cvtColor(blended_rgba_gpu, cv2.COLOR_RGBA2RGB)
        return blended_rgb_gpu.download()
    except Exception:
        return None


def compose_bundle_frame_rgb(
    frame_rgb: np.ndarray,
    bundle: AssetBundle | None,
    *,
    reference_width: int | None = None,
    reference_height: int | None = None,
    acceleration_preference: str = "auto",
) -> np.ndarray:
    if (
        bundle is None
        or bundle.hair_rgba_path is None
        or bundle.render_task is None
        or bundle.hair_bbox is None
    ):
        return frame_rgb

    if frame_rgb.ndim != 3 or frame_rgb.shape[2] != 3:
        return frame_rgb

    render_task = bundle.render_task
    if reference_width is not None and reference_height is not None:
        render_task = _scale_render_task(
            render_task,
            reference_width=reference_width,
            reference_height=reference_height,
            frame_width=int(frame_rgb.shape[1]),
            frame_height=int(frame_rgb.shape[0]),
        )
    destination_roi = render_task.get("destination_roi")
    matrix = render_task.get("matrix")
    if not destination_roi or not matrix:
        return frame_rgb

    roi_width = int(destination_roi["w"])
    roi_height = int(destination_roi["h"])
    if roi_width <= 0 or roi_height <= 0:
        return frame_rgb

    hair_rgba_path = str(bundle.hair_rgba_path)
    source_patch = _load_rgba_image(hair_rgba_path)
    source_origin_x = int(bundle.hair_bbox["x"])
    source_origin_y = int(bundle.hair_bbox["y"])

    local_e = (
        float(matrix["a"]) * float(source_origin_x)
        + float(matrix["c"]) * float(source_origin_y)
        + float(matrix["e"])
        - float(destination_roi["x"])
    )
    local_f = (
        float(matrix["b"]) * float(source_origin_x)
        + float(matrix["d"]) * float(source_origin_y)
        + float(matrix["f"])
        - float(destination_roi["y"])
    )

    inverse = _invert_affine(
        float(matrix["a"]),
        float(matrix["b"]),
        float(matrix["c"]),
        float(matrix["d"]),
        local_e,
        local_f,
    )
    if inverse is None:
        return frame_rgb

    inverse_matrix = np.asarray(inverse, dtype=np.float32).reshape(2, 3)
    warped_patch_gpu = None
    if _opencv_cuda_warp_enabled(acceleration_preference):
        warped_patch_gpu = _warp_rgba_patch_cuda(
            hair_rgba_path,
            inverse_matrix,
            roi_width,
            roi_height,
            acceleration_preference=acceleration_preference,
        )

    warped_patch = None
    if warped_patch_gpu is None:
        warped_patch = cv2.warpAffine(
            source_patch,
            inverse_matrix,
            (roi_width, roi_height),
            flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0, 0),
        )

    output = np.ascontiguousarray(frame_rgb).copy()
    frame_height, frame_width = output.shape[:2]
    x0 = max(0, int(destination_roi["x"]))
    y0 = max(0, int(destination_roi["y"]))
    x1 = min(frame_width, x0 + roi_width)
    y1 = min(frame_height, y0 + roi_height)
    if x1 <= x0 or y1 <= y0:
        return output

    base_roi = output[y0:y1, x0:x1]
    if (
        warped_patch_gpu is not None
        and (x1 - x0) == roi_width
        and (y1 - y0) == roi_height
    ):
        full_gpu_roi = _blend_rgba_over_rgb_cuda(
            base_roi,
            warped_patch_gpu,
            acceleration_preference=acceleration_preference,
        )
        if full_gpu_roi is not None:
            base_roi[:, :] = full_gpu_roi
            return output

    if warped_patch_gpu is not None:
        warped_patch = _download_cuda_mat(warped_patch_gpu)

    if warped_patch is None:
        return output

    warped_patch = warped_patch[: y1 - y0, : x1 - x0]
    _blend_rgba_over_rgb(base_roi, warped_patch)
    return output


def compose_bundle_frame(
    frame_image: Image.Image,
    bundle: AssetBundle | None,
    *,
    reference_width: int | None = None,
    reference_height: int | None = None,
    acceleration_preference: str = "auto",
) -> Image.Image:
    frame_rgb = np.asarray(frame_image.convert("RGB"))
    rendered_rgb = compose_bundle_frame_rgb(
        frame_rgb,
        bundle,
        reference_width=reference_width,
        reference_height=reference_height,
        acceleration_preference=acceleration_preference,
    )
    return Image.fromarray(rendered_rgb)
