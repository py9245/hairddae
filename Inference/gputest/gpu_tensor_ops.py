from __future__ import annotations

from functools import lru_cache
from typing import Literal

import numpy as np

try:
    import torch
    import torch.nn.functional as F
except Exception:  # pragma: no cover
    torch = None
    F = None


def gpu_ready() -> bool:
    return bool(torch is not None and F is not None and torch.cuda.is_available())


if gpu_ready():
    torch.backends.cudnn.enabled = False


def require_gpu() -> None:
    if not gpu_ready():
        raise RuntimeError("torch cuda runtime is unavailable")


def device() -> "torch.device":
    require_gpu()
    return torch.device("cuda")


def _as_float_tensor(image: np.ndarray) -> "torch.Tensor":
    require_gpu()
    array = np.ascontiguousarray(image)
    tensor = torch.from_numpy(array).to(device=device(), dtype=torch.float32)
    if tensor.ndim == 2:
        return tensor.unsqueeze(0).unsqueeze(0)
    if tensor.ndim == 3:
        return tensor.permute(2, 0, 1).unsqueeze(0)
    raise ValueError("unsupported image rank")


def image_to_tensor(image: np.ndarray) -> "torch.Tensor":
    tensor = _as_float_tensor(image)
    if image.dtype == np.uint8:
        return tensor / 255.0
    return tensor


def mask_to_tensor(mask: np.ndarray) -> "torch.Tensor":
    tensor = _as_float_tensor(mask)
    if mask.dtype == np.uint8:
        tensor = tensor / 255.0
    return torch.clamp(tensor, 0.0, 1.0)


def tensor_to_image(tensor: "torch.Tensor", *, dtype: np.dtype = np.uint8) -> np.ndarray:
    require_gpu()
    resolved = tensor.detach()
    if resolved.ndim == 4:
        resolved = resolved.squeeze(0)
    if resolved.ndim == 3:
        resolved = resolved.permute(1, 2, 0)
    array = resolved.clamp(0.0, 1.0).cpu().numpy()
    if np.issubdtype(dtype, np.integer):
        return np.clip(np.rint(array * 255.0), 0, 255).astype(dtype)
    return array.astype(dtype, copy=False)


def tensor_to_mask(tensor: "torch.Tensor", *, dtype: np.dtype = np.uint8) -> np.ndarray:
    require_gpu()
    resolved = tensor.detach()
    if resolved.ndim == 4:
        resolved = resolved.squeeze(0)
    if resolved.ndim == 3:
        resolved = resolved.squeeze(0)
    array = resolved.clamp(0.0, 1.0).cpu().numpy()
    if np.issubdtype(dtype, np.integer):
        return np.clip(np.rint(array * 255.0), 0, 255).astype(dtype)
    return array.astype(dtype, copy=False)


def resize_tensor(
    tensor: "torch.Tensor",
    size: tuple[int, int],
    *,
    mode: Literal["bilinear", "nearest"] = "bilinear",
) -> "torch.Tensor":
    kwargs = {"mode": mode}
    if mode != "nearest":
        kwargs["align_corners"] = True
    return F.interpolate(tensor, size=size, **kwargs)


@lru_cache(maxsize=128)
def _gaussian_kernel_1d(size: int, sigma: float) -> "torch.Tensor":
    require_gpu()
    center = (size - 1) * 0.5
    coords = torch.arange(size, dtype=torch.float32, device=device()) - center
    resolved_sigma = max(1e-6, float(sigma))
    kernel = torch.exp(-(coords * coords) / (2.0 * resolved_sigma * resolved_sigma))
    return kernel / torch.clamp(kernel.sum(), min=1e-6)


def _resolve_kernel_size(sigma: float) -> int:
    resolved = int(round(float(sigma) * 6.0 + 1.0))
    resolved = max(3, resolved)
    return resolved if resolved % 2 == 1 else resolved + 1


def gaussian_blur_tensor(
    tensor: "torch.Tensor",
    *,
    sigma_x: float,
    sigma_y: float | None = None,
) -> "torch.Tensor":
    require_gpu()
    resolved_sigma_y = float(sigma_y if sigma_y is not None else sigma_x)
    resolved_sigma_x = float(sigma_x)
    kernel_w = _resolve_kernel_size(resolved_sigma_x)
    kernel_h = _resolve_kernel_size(resolved_sigma_y)
    channels = int(tensor.shape[1])
    kernel_x = _gaussian_kernel_1d(kernel_w, resolved_sigma_x)
    kernel_y = _gaussian_kernel_1d(kernel_h, resolved_sigma_y)
    weights_x = kernel_x.view(1, 1, 1, kernel_w).repeat(channels, 1, 1, 1)
    weights_y = kernel_y.view(1, 1, kernel_h, 1).repeat(channels, 1, 1, 1)
    pad_x = kernel_w // 2
    pad_y = kernel_h // 2
    padded_x = F.pad(tensor, (pad_x, pad_x, 0, 0), mode="reflect")
    blurred_x = F.conv2d(padded_x, weights_x, groups=channels)
    padded_y = F.pad(blurred_x, (0, 0, pad_y, pad_y), mode="reflect")
    return F.conv2d(padded_y, weights_y, groups=channels)


def dilate_mask(mask_tensor: "torch.Tensor", *, kernel_size: int, iterations: int = 1) -> "torch.Tensor":
    require_gpu()
    tensor = mask_tensor
    pad = kernel_size // 2
    for _ in range(max(1, int(iterations))):
        tensor = F.max_pool2d(tensor, kernel_size=kernel_size, stride=1, padding=pad)
    return tensor


def erode_mask(mask_tensor: "torch.Tensor", *, kernel_size: int, iterations: int = 1) -> "torch.Tensor":
    require_gpu()
    tensor = mask_tensor
    pad = kernel_size // 2
    for _ in range(max(1, int(iterations))):
        tensor = -F.max_pool2d(-tensor, kernel_size=kernel_size, stride=1, padding=pad)
    return tensor


def alpha_blend(base_tensor: "torch.Tensor", overlay_tensor: "torch.Tensor", alpha_tensor: "torch.Tensor") -> "torch.Tensor":
    return base_tensor * (1.0 - alpha_tensor) + overlay_tensor * alpha_tensor


def apply_masked_gain(rgb_tensor: "torch.Tensor", mask_tensor: "torch.Tensor", gain: float | None) -> "torch.Tensor":
    if gain is None:
        return rgb_tensor
    resolved_gain = float(gain)
    if abs(resolved_gain - 1.0) <= 1e-4:
        return rgb_tensor
    gain_tensor = torch.clamp(mask_tensor, 0.0, 1.0)
    return torch.clamp(rgb_tensor * (1.0 + gain_tensor * max(0.0, resolved_gain - 1.0)), 0.0, 1.0)


def _normalization_matrix(width: int, height: int) -> "torch.Tensor":
    require_gpu()
    return torch.tensor(
        [
            [(width - 1) * 0.5, 0.0, (width - 1) * 0.5],
            [0.0, (height - 1) * 0.5, (height - 1) * 0.5],
            [0.0, 0.0, 1.0],
        ],
        dtype=torch.float32,
        device=device(),
    )


def cv_affine_to_theta(
    matrix: np.ndarray,
    *,
    src_width: int,
    src_height: int,
    dst_width: int,
    dst_height: int,
) -> "torch.Tensor":
    require_gpu()
    affine = np.asarray(matrix, dtype=np.float32)
    if affine.shape != (2, 3):
        raise ValueError("expected 2x3 affine matrix")
    affine_3x3 = np.vstack([affine, np.array([0.0, 0.0, 1.0], dtype=np.float32)])
    dst_from_src = torch.from_numpy(affine_3x3).to(device=device(), dtype=torch.float32)
    src_from_dst = torch.linalg.inv(dst_from_src)
    src_norm_from_pix = torch.linalg.inv(_normalization_matrix(src_width, src_height))
    dst_pix_from_norm = _normalization_matrix(dst_width, dst_height)
    theta = src_norm_from_pix @ src_from_dst @ dst_pix_from_norm
    return theta[:2, :]


def warp_affine_tensor(
    tensor: "torch.Tensor",
    matrix: np.ndarray,
    *,
    dst_width: int,
    dst_height: int,
    mode: Literal["bilinear", "nearest"] = "bilinear",
) -> "torch.Tensor":
    require_gpu()
    src_height = int(tensor.shape[-2])
    src_width = int(tensor.shape[-1])
    theta = cv_affine_to_theta(
        matrix,
        src_width=src_width,
        src_height=src_height,
        dst_width=dst_width,
        dst_height=dst_height,
    ).unsqueeze(0)
    grid = F.affine_grid(
        theta,
        size=(int(tensor.shape[0]), int(tensor.shape[1]), dst_height, dst_width),
        align_corners=True,
    )
    return F.grid_sample(
        tensor,
        grid,
        mode=mode,
        padding_mode="zeros",
        align_corners=True,
    )
