from __future__ import annotations

import importlib
import os
from functools import lru_cache
from types import ModuleType
from typing import Any

import numpy as np

import cv2_cuda_utils as base


def enable_forced_gpu_env() -> None:
    os.environ["INFERENCE_OPENCV_CUDA_ENABLED"] = "true"
    os.environ["INFERENCE_OPENCV_TORCH_FILTERS_ENABLED"] = "false"
    os.environ["TORCH_CUDNN_V8_API_DISABLED"] = "1"


def _with_min_pixels(kwargs: dict[str, Any], value: int = 0) -> dict[str, Any]:
    resolved = dict(kwargs)
    resolved["min_pixels"] = value
    return resolved


@lru_cache(maxsize=1)
def _torch_runtime() -> tuple[bool, Any | None, Any | None]:
    try:
        import torch
        import torch.nn.functional as F
    except Exception:
        return False, None, None
    if not torch.cuda.is_available():
        return False, None, None
    torch.backends.cudnn.enabled = False
    return True, torch, F


def _resolve_gaussian_kernel_size(size: int, sigma: float) -> int:
    if size and size > 0:
        return size if size % 2 == 1 else size + 1
    if sigma <= 0.0:
        return 3
    resolved = int(round(float(sigma) * 6.0 + 1.0))
    resolved = max(3, resolved)
    return resolved if resolved % 2 == 1 else resolved + 1


@lru_cache(maxsize=64)
def _gaussian_kernel_2d(
    kx: int,
    ky: int,
    sigma_x: float,
    sigma_y: float,
) -> Any:
    enabled, torch, _ = _torch_runtime()
    if not enabled:
        return None

    def _kernel_1d(size: int, sigma: float) -> Any:
        center = (size - 1) * 0.5
        coords = torch.arange(size, dtype=torch.float32, device="cuda") - center
        safe_sigma = max(1e-6, float(sigma))
        weights = torch.exp(-(coords * coords) / (2.0 * safe_sigma * safe_sigma))
        return weights / torch.clamp(weights.sum(), min=1e-6)

    kernel_x = _kernel_1d(kx, sigma_x)
    kernel_y = _kernel_1d(ky, sigma_y)
    kernel_2d = torch.outer(kernel_y, kernel_x)
    return kernel_2d / torch.clamp(kernel_2d.sum(), min=1e-6)


def _to_torch_nchw(image: np.ndarray, *, torch: Any) -> tuple[Any, bool]:
    if image.ndim == 2:
        tensor = torch.from_numpy(np.ascontiguousarray(image)).to(device="cuda", dtype=torch.float32)
        return tensor.unsqueeze(0).unsqueeze(0), True
    if image.ndim == 3:
        tensor = torch.from_numpy(np.ascontiguousarray(image)).to(device="cuda", dtype=torch.float32)
        return tensor.permute(2, 0, 1).unsqueeze(0), False
    raise ValueError("unsupported image rank")


def _from_torch_nchw(tensor: Any, *, single_channel: bool, dtype: np.dtype) -> np.ndarray:
    array = tensor.squeeze(0)
    if single_channel:
        result = array.squeeze(0).detach().cpu().numpy()
    else:
        result = array.permute(1, 2, 0).detach().cpu().numpy()
    if np.issubdtype(dtype, np.integer):
        return np.clip(np.rint(result), 0, 255).astype(dtype)
    return result.astype(dtype, copy=False)


def _torch_gaussian_blur(
    image: np.ndarray,
    ksize: tuple[int, int],
    sigma_x: float,
    sigma_y: float = 0.0,
) -> np.ndarray | None:
    if image.ndim not in (2, 3) or image.dtype not in (np.uint8, np.float32):
        return None
    enabled, torch, F = _torch_runtime()
    if not enabled or torch is None or F is None:
        return None
    try:
        resolved_sigma_y = float(sigma_y if sigma_y > 0.0 else sigma_x)
        resolved_sigma_x = float(sigma_x if sigma_x > 0.0 else resolved_sigma_y)
        kernel_w = _resolve_gaussian_kernel_size(int(ksize[0]), resolved_sigma_x)
        kernel_h = _resolve_gaussian_kernel_size(int(ksize[1]), resolved_sigma_y)
        kernel_2d = _gaussian_kernel_2d(kernel_w, kernel_h, resolved_sigma_x, resolved_sigma_y)
        if kernel_2d is None:
            return None
        tensor, single_channel = _to_torch_nchw(image, torch=torch)
        channels = int(tensor.shape[1])
        pad_x = kernel_w // 2
        pad_y = kernel_h // 2
        padded = F.pad(tensor, (pad_x, pad_x, pad_y, pad_y), mode="reflect")
        kernel = kernel_2d.view(1, 1, kernel_h, kernel_w).repeat(channels, 1, 1, 1)
        with torch.no_grad():
            blurred = F.conv2d(padded, kernel, groups=channels)
        return _from_torch_nchw(blurred, single_channel=single_channel, dtype=image.dtype)
    except Exception:
        return None


def _torch_morphology(
    image: np.ndarray,
    kernel: np.ndarray,
    *,
    iterations: int,
    op: str,
) -> np.ndarray | None:
    if image.ndim != 2 or kernel.ndim != 2 or image.dtype not in (np.uint8, np.float32):
        return None
    enabled, torch, F = _torch_runtime()
    if not enabled or torch is None or F is None:
        return None
    try:
        kernel_mask = torch.from_numpy((kernel > 0).astype(np.bool_)).to(device="cuda")
        if int(kernel_mask.sum().item()) == 0:
            return image
        tensor, _ = _to_torch_nchw(image, torch=torch)
        kh, kw = int(kernel.shape[0]), int(kernel.shape[1])
        pad_x = kw // 2
        pad_y = kh // 2
        for _ in range(max(1, int(iterations))):
            fill_value = 0.0 if op == "dilate" else 255.0
            padded = F.pad(tensor, (pad_x, pad_x, pad_y, pad_y), mode="constant", value=fill_value)
            patches = F.unfold(padded, kernel_size=(kh, kw))
            mask = kernel_mask.flatten().view(1, -1, 1)
            if op == "dilate":
                masked = torch.where(mask, patches, torch.full_like(patches, -1e9))
                tensor = masked.max(dim=1).values.view_as(tensor)
            else:
                masked = torch.where(mask, patches, torch.full_like(patches, 1e9))
                tensor = masked.min(dim=1).values.view_as(tensor)
        return _from_torch_nchw(tensor, single_channel=True, dtype=image.dtype)
    except Exception:
        return None


def opencv_resize(image: np.ndarray, dsize: tuple[int, int], **kwargs: Any) -> np.ndarray:
    return base.opencv_resize(image, dsize, **_with_min_pixels(kwargs))


def opencv_flip(image: np.ndarray, flip_code: int, **kwargs: Any) -> np.ndarray:
    return base.opencv_flip(image, flip_code, **_with_min_pixels(kwargs))


def opencv_cvt_color(image: np.ndarray, code: int, **kwargs: Any) -> np.ndarray:
    return base.opencv_cvt_color(image, code, **_with_min_pixels(kwargs))


def opencv_gaussian_blur(
    image: np.ndarray,
    ksize: tuple[int, int],
    sigma_x: float,
    sigma_y: float = 0.0,
    **kwargs: Any,
) -> np.ndarray:
    candidate = _torch_gaussian_blur(image, ksize, sigma_x, sigma_y)
    if candidate is not None:
        return candidate
    return base.opencv_gaussian_blur(image, ksize, sigma_x, sigma_y, **_with_min_pixels(kwargs))


def opencv_dilate(image: np.ndarray, kernel: np.ndarray, **kwargs: Any) -> np.ndarray:
    candidate = _torch_morphology(image, kernel, iterations=int(kwargs.get("iterations", 1)), op="dilate")
    if candidate is not None:
        return candidate
    return base.opencv_dilate(image, kernel, **_with_min_pixels(kwargs))


def opencv_erode(image: np.ndarray, kernel: np.ndarray, **kwargs: Any) -> np.ndarray:
    candidate = _torch_morphology(image, kernel, iterations=int(kwargs.get("iterations", 1)), op="erode")
    if candidate is not None:
        return candidate
    return base.opencv_erode(image, kernel, **_with_min_pixels(kwargs))


def opencv_warp_affine(
    image: np.ndarray,
    matrix: np.ndarray,
    dsize: tuple[int, int],
    **kwargs: Any,
) -> np.ndarray:
    return base.opencv_warp_affine(image, matrix, dsize, **_with_min_pixels(kwargs))


def opencv_warp_affine_uploaded(gpu_image: Any, matrix: np.ndarray, dsize: tuple[int, int], **kwargs: Any) -> Any:
    return base.opencv_warp_affine_uploaded(gpu_image, matrix, dsize, **kwargs)


def opencv_add_weighted(src1: np.ndarray, alpha: float, src2: np.ndarray, beta: float, gamma: float = 0.0, **kwargs: Any) -> np.ndarray:
    return base.opencv_add_weighted(src1, alpha, src2, beta, gamma, **_with_min_pixels(kwargs))


def opencv_absdiff(left: np.ndarray, right: np.ndarray, **kwargs: Any) -> np.ndarray:
    return base.opencv_absdiff(left, right, **_with_min_pixels(kwargs))


def opencv_bitwise_and(left: np.ndarray, right: np.ndarray, **kwargs: Any) -> np.ndarray:
    return base.opencv_bitwise_and(left, right, **_with_min_pixels(kwargs))


def opencv_bitwise_or(left: np.ndarray, right: np.ndarray, **kwargs: Any) -> np.ndarray:
    return base.opencv_bitwise_or(left, right, **_with_min_pixels(kwargs))


def opencv_bitwise_not(image: np.ndarray, **kwargs: Any) -> np.ndarray:
    return base.opencv_bitwise_not(image, **_with_min_pixels(kwargs))


def opencv_min(left: np.ndarray, right: np.ndarray, **kwargs: Any) -> np.ndarray:
    return base.opencv_min(left, right, **_with_min_pixels(kwargs))


def opencv_cuda_upload(image: np.ndarray, **kwargs: Any) -> Any | None:
    return base.opencv_cuda_upload(image, **_with_min_pixels(kwargs))


def opencv_cuda_download(image_or_gpu: Any) -> np.ndarray:
    return base.opencv_cuda_download(image_or_gpu)


_PATCH_TARGETS = (
    ("app.frame_prepare_pipeline", ("opencv_cvt_color",)),
    (
        "app.hair_attenuation",
        (
            "opencv_add_weighted",
            "opencv_bitwise_and",
            "opencv_bitwise_not",
            "opencv_bitwise_or",
            "opencv_cvt_color",
            "opencv_dilate",
            "opencv_erode",
            "opencv_gaussian_blur",
            "opencv_resize",
        ),
    ),
    (
        "app.overlay_postprocess_pipeline",
        (
            "opencv_absdiff",
            "opencv_bitwise_and",
            "opencv_bitwise_not",
            "opencv_bitwise_or",
            "opencv_dilate",
            "opencv_gaussian_blur",
        ),
    ),
    (
        "hairddae_tools.run_hair_overlay_poc",
        (
            "opencv_cuda_download",
            "opencv_cuda_upload",
            "opencv_cvt_color",
            "opencv_dilate",
            "opencv_gaussian_blur",
            "opencv_resize",
            "opencv_warp_affine",
            "opencv_warp_affine_uploaded",
        ),
    ),
    ("app.hairddae_runtime", ("opencv_add_weighted", "opencv_cvt_color")),
    ("app.server_render", ("opencv_cvt_color", "opencv_dilate", "opencv_gaussian_blur")),
    ("app.rtc", ("opencv_flip", "opencv_resize")),
)


def patch_all() -> list[str]:
    return patch_modules(tuple(module_name for module_name, _ in _PATCH_TARGETS))


def patch_modules(module_names: tuple[str, ...] | list[str]) -> list[str]:
    enable_forced_gpu_env()
    patched: list[str] = []
    requested = set(module_names)
    for module_name, symbols in _PATCH_TARGETS:
        if module_name not in requested:
            continue
        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue
        _patch_module(module, symbols)
        patched.append(module_name)
    return patched


def _patch_module(module: ModuleType, symbols: tuple[str, ...]) -> None:
    for symbol in symbols:
        replacement = globals().get(symbol)
        if replacement is not None and hasattr(module, symbol):
            setattr(module, symbol, replacement)
