from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
import os

import cv2
from mediapipe.tasks.python import BaseOptions


def _normalized_preference(preference: str) -> str:
    resolved = preference.strip().lower()
    if resolved in {"cpu", "gpu", "auto"}:
        return resolved
    return "auto"


def _nvidia_device_files_present() -> bool:
    return any(Path(candidate).exists() for candidate in ("/dev/nvidia0", "/dev/nvidiactl", "/dev/nvidia-uvm"))


def _nvidia_runtime_visible() -> bool:
    visible_devices = os.getenv("NVIDIA_VISIBLE_DEVICES", "").strip().lower()
    return _nvidia_device_files_present() or (visible_devices not in {"", "void", "none"})


def _opencv_cuda_device_count() -> int:
    if not hasattr(cv2, "cuda"):
        return 0
    try:
        return int(cv2.cuda.getCudaEnabledDeviceCount())
    except Exception:
        return 0


def _opencv_build_has_cuda() -> bool:
    try:
        build_info = cv2.getBuildInformation()
    except Exception:
        return False
    return any("CUDA" in line and "YES" in line for line in build_info.splitlines())


def _opencv_cuda_has_attr(name: str) -> bool:
    cuda_module = getattr(cv2, "cuda", None)
    return bool(cuda_module is not None and hasattr(cuda_module, name))


def supports_opencv_cuda_warp_affine() -> bool:
    return _opencv_cuda_has_attr("warpAffine")


def supports_opencv_cuda_alpha_comp() -> bool:
    return (
        _opencv_cuda_has_attr("alphaComp")
        and _opencv_cuda_has_attr("ALPHA_OVER")
        and _opencv_cuda_has_attr("cvtColor")
    )


def supports_mediapipe_gpu_delegate() -> bool:
    return bool(hasattr(BaseOptions, "Delegate") and hasattr(BaseOptions.Delegate, "GPU"))


def select_mediapipe_delegate(preference: str) -> tuple[BaseOptions.Delegate, str]:
    resolved_preference = _normalized_preference(preference)
    if resolved_preference == "cpu":
        return BaseOptions.Delegate.CPU, "cpu"

    if supports_mediapipe_gpu_delegate() and _nvidia_runtime_visible():
        return BaseOptions.Delegate.GPU, "gpu"

    return BaseOptions.Delegate.CPU, "cpu"


@dataclass(frozen=True)
class RuntimeAccelerationInfo:
    nvidia_runtime_visible: bool
    mediapipe_gpu_delegate_supported: bool
    opencv_cuda_build_available: bool
    opencv_cuda_device_count: int
    opencv_cuda_warp_affine_supported: bool
    opencv_cuda_alpha_comp_supported: bool

    @property
    def opencv_cuda_runtime_available(self) -> bool:
        return self.opencv_cuda_build_available and self.opencv_cuda_device_count > 0

    @property
    def opencv_cuda_warp_affine_available(self) -> bool:
        return self.opencv_cuda_runtime_available and self.opencv_cuda_warp_affine_supported

    @property
    def opencv_cuda_alpha_comp_available(self) -> bool:
        return self.opencv_cuda_runtime_available and self.opencv_cuda_alpha_comp_supported

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["opencv_cuda_runtime_available"] = self.opencv_cuda_runtime_available
        payload["opencv_cuda_warp_affine_available"] = self.opencv_cuda_warp_affine_available
        payload["opencv_cuda_alpha_comp_available"] = self.opencv_cuda_alpha_comp_available
        return payload


@lru_cache(maxsize=1)
def detect_runtime_acceleration() -> RuntimeAccelerationInfo:
    return RuntimeAccelerationInfo(
        nvidia_runtime_visible=_nvidia_runtime_visible(),
        mediapipe_gpu_delegate_supported=supports_mediapipe_gpu_delegate(),
        opencv_cuda_build_available=_opencv_build_has_cuda(),
        opencv_cuda_device_count=_opencv_cuda_device_count(),
        opencv_cuda_warp_affine_supported=supports_opencv_cuda_warp_affine(),
        opencv_cuda_alpha_comp_supported=supports_opencv_cuda_alpha_comp(),
    )
