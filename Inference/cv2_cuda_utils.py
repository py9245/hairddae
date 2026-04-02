from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import cv2
import numpy as np


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def opencv_cuda_enabled() -> bool:
    if not _env_bool("INFERENCE_OPENCV_CUDA_ENABLED", True):
        return False
    try:
        return bool(hasattr(cv2, "cuda") and cv2.cuda.getCudaEnabledDeviceCount() > 0)
    except Exception:
        return False


def _pixel_count(image: np.ndarray) -> int:
    if image.ndim < 2:
        return 0
    return int(image.shape[0]) * int(image.shape[1])


def _should_use_cuda(image: np.ndarray, min_pixels: int) -> bool:
    return opencv_cuda_enabled() and _pixel_count(image) >= max(0, int(min_pixels))


@lru_cache(maxsize=1)
def _torch_cuda_runtime() -> tuple[bool, Any | None, Any | None]:
    try:
        import torch
        import torch.nn.functional as F
    except Exception:
        return False, None, None
    if not opencv_cuda_enabled() or not torch.cuda.is_available():
        return False, None, None
    return True, torch, F


def _should_use_torch_cuda(image: np.ndarray, min_pixels: int) -> bool:
    if not _env_bool("INFERENCE_OPENCV_TORCH_FILTERS_ENABLED", False):
        return False
    enabled, _, _ = _torch_cuda_runtime()
    if not enabled:
        return False
    return _pixel_count(image) >= max(0, int(min_pixels))


def _upload(image: np.ndarray) -> Any:
    gpu_mat = cv2.cuda_GpuMat()
    gpu_mat.upload(image)
    return gpu_mat


def opencv_cuda_upload(
    image: np.ndarray,
    *,
    min_pixels: int = 65_536,
) -> Any | None:
    if not _should_use_cuda(image, min_pixels):
        return None
    try:
        return _upload(image)
    except Exception:
        return None


def opencv_cuda_download(image_or_gpu: Any) -> np.ndarray:
    if hasattr(image_or_gpu, "download"):
        return image_or_gpu.download()
    return image_or_gpu


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
    enabled, torch, _ = _torch_cuda_runtime()
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
    kernel_2d = kernel_2d / torch.clamp(kernel_2d.sum(), min=1e-6)
    return kernel_2d


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


def opencv_gaussian_blur(
    image: np.ndarray,
    ksize: tuple[int, int],
    sigma_x: float,
    sigma_y: float = 0.0,
    *,
    min_pixels: int = 24_000,
) -> np.ndarray:
    if _should_use_torch_cuda(image, min_pixels) and image.ndim in (2, 3) and image.dtype in (np.uint8, np.float32):
        enabled, torch, F = _torch_cuda_runtime()
        if enabled and torch is not None and F is not None:
            try:
                resolved_sigma_y = float(sigma_y if sigma_y > 0.0 else sigma_x)
                resolved_sigma_x = float(sigma_x if sigma_x > 0.0 else resolved_sigma_y)
                kernel_w = _resolve_gaussian_kernel_size(int(ksize[0]), resolved_sigma_x)
                kernel_h = _resolve_gaussian_kernel_size(int(ksize[1]), resolved_sigma_y)
                kernel_2d = _gaussian_kernel_2d(kernel_w, kernel_h, resolved_sigma_x, resolved_sigma_y)
                if kernel_2d is not None:
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
                pass
    return cv2.GaussianBlur(image, ksize, sigmaX=sigma_x, sigmaY=sigma_y)


def _morphology_with_torch(
    image: np.ndarray,
    kernel: np.ndarray,
    *,
    iterations: int,
    op: str,
    min_pixels: int,
) -> np.ndarray:
    if image.ndim != 2 or kernel.ndim != 2:
        return image
    if image.dtype not in (np.uint8, np.float32):
        return image
    if not _should_use_torch_cuda(image, min_pixels):
        return image

    enabled, torch, F = _torch_cuda_runtime()
    if not enabled or torch is None or F is None:
        return image

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
        return image


def opencv_dilate(
    image: np.ndarray,
    kernel: np.ndarray,
    *,
    iterations: int = 1,
    min_pixels: int = 24_000,
) -> np.ndarray:
    candidate = _morphology_with_torch(
        image,
        kernel,
        iterations=iterations,
        op="dilate",
        min_pixels=min_pixels,
    )
    if candidate is not image:
        return candidate
    return cv2.dilate(image, kernel, iterations=iterations)


def opencv_erode(
    image: np.ndarray,
    kernel: np.ndarray,
    *,
    iterations: int = 1,
    min_pixels: int = 24_000,
) -> np.ndarray:
    candidate = _morphology_with_torch(
        image,
        kernel,
        iterations=iterations,
        op="erode",
        min_pixels=min_pixels,
    )
    if candidate is not image:
        return candidate
    return cv2.erode(image, kernel, iterations=iterations)


def opencv_resize(
    image: np.ndarray,
    dsize: tuple[int, int],
    *,
    interpolation: int = cv2.INTER_LINEAR,
    min_pixels: int = 200_000,
) -> np.ndarray:
    if _should_use_cuda(image, min_pixels):
        try:
            return cv2.cuda.resize(_upload(image), dsize, interpolation=interpolation).download()
        except Exception:
            pass
    return cv2.resize(image, dsize, interpolation=interpolation)


def opencv_flip(
    image: np.ndarray,
    flip_code: int,
    *,
    min_pixels: int = 200_000,
) -> np.ndarray:
    if _should_use_cuda(image, min_pixels) and hasattr(cv2.cuda, "flip"):
        try:
            return cv2.cuda.flip(_upload(image), flip_code).download()
        except Exception:
            pass
    return cv2.flip(image, flip_code)


def opencv_cvt_color(
    image: np.ndarray,
    code: int,
    *,
    dst_cn: int = 0,
    min_pixels: int = 200_000,
) -> np.ndarray:
    if _should_use_cuda(image, min_pixels):
        try:
            if dst_cn > 0:
                return cv2.cuda.cvtColor(_upload(image), code, dst_cn).download()
            return cv2.cuda.cvtColor(_upload(image), code).download()
        except Exception:
            pass
    return cv2.cvtColor(image, code, dst_cn)


def opencv_warp_affine(
    image: np.ndarray,
    matrix: np.ndarray,
    dsize: tuple[int, int],
    *,
    flags: int = cv2.INTER_LINEAR,
    border_mode: int = cv2.BORDER_CONSTANT,
    border_value: int | float | tuple[int, int, int] = 0,
    borderMode: int | None = None,
    borderValue: int | float | tuple[int, int, int] | None = None,
    min_pixels: int = 65_536,
) -> np.ndarray:
    resolved_border_mode = border_mode if borderMode is None else borderMode
    resolved_border_value = border_value if borderValue is None else borderValue
    if _should_use_cuda(image, min_pixels):
        try:
            return cv2.cuda.warpAffine(
                _upload(image),
                matrix,
                dsize,
                flags=flags,
                borderMode=resolved_border_mode,
                borderValue=resolved_border_value,
            ).download()
        except Exception:
            pass
    return cv2.warpAffine(
        image,
        matrix,
        dsize,
        flags=flags,
        borderMode=resolved_border_mode,
        borderValue=resolved_border_value,
    )


def opencv_warp_affine_uploaded(
    gpu_image: Any,
    matrix: np.ndarray,
    dsize: tuple[int, int],
    *,
    flags: int = cv2.INTER_LINEAR,
    border_mode: int = cv2.BORDER_CONSTANT,
    border_value: int | float | tuple[int, int, int] = 0,
    borderMode: int | None = None,
    borderValue: int | float | tuple[int, int, int] | None = None,
) -> Any | None:
    resolved_border_mode = border_mode if borderMode is None else borderMode
    resolved_border_value = border_value if borderValue is None else borderValue
    if gpu_image is None or not opencv_cuda_enabled():
        return None
    try:
        return cv2.cuda.warpAffine(
            gpu_image,
            matrix,
            dsize,
            flags=flags,
            borderMode=resolved_border_mode,
            borderValue=resolved_border_value,
        )
    except Exception:
        return None


def opencv_add_weighted(
    src1: np.ndarray,
    alpha: float,
    src2: np.ndarray,
    beta: float,
    gamma: float = 0.0,
    *,
    min_pixels: int = 200_000,
) -> np.ndarray:
    if src1.shape == src2.shape and _should_use_cuda(src1, min_pixels):
        try:
            return cv2.cuda.addWeighted(_upload(src1), alpha, _upload(src2), beta, gamma).download()
        except Exception:
            pass
    return cv2.addWeighted(src1, alpha, src2, beta, gamma)


def opencv_absdiff(
    left: np.ndarray,
    right: np.ndarray,
    *,
    min_pixels: int = 200_000,
) -> np.ndarray:
    if left.shape == right.shape and _should_use_cuda(left, min_pixels):
        try:
            return cv2.cuda.absdiff(_upload(left), _upload(right)).download()
        except Exception:
            pass
    return cv2.absdiff(left, right)


def opencv_bitwise_and(
    left: np.ndarray,
    right: np.ndarray,
    *,
    mask: np.ndarray | None = None,
    min_pixels: int = 200_000,
) -> np.ndarray:
    if left.shape == right.shape and mask is None and _should_use_cuda(left, min_pixels):
        try:
            return cv2.cuda.bitwise_and(_upload(left), _upload(right)).download()
        except Exception:
            pass
    return cv2.bitwise_and(left, right, mask=mask)


def opencv_bitwise_or(
    left: np.ndarray,
    right: np.ndarray,
    *,
    mask: np.ndarray | None = None,
    min_pixels: int = 200_000,
) -> np.ndarray:
    if left.shape == right.shape and mask is None and _should_use_cuda(left, min_pixels):
        try:
            return cv2.cuda.bitwise_or(_upload(left), _upload(right)).download()
        except Exception:
            pass
    return cv2.bitwise_or(left, right, mask=mask)


def opencv_bitwise_not(
    image: np.ndarray,
    *,
    mask: np.ndarray | None = None,
    min_pixels: int = 200_000,
) -> np.ndarray:
    if mask is None and _should_use_cuda(image, min_pixels):
        try:
            return cv2.cuda.bitwise_not(_upload(image)).download()
        except Exception:
            pass
    return cv2.bitwise_not(image, mask=mask)


def opencv_min(
    left: np.ndarray,
    right: np.ndarray,
    *,
    min_pixels: int = 200_000,
) -> np.ndarray:
    if left.shape == right.shape and _should_use_cuda(left, min_pixels):
        try:
            return cv2.cuda.min(_upload(left), _upload(right)).download()
        except Exception:
            pass
    return cv2.min(left, right)
