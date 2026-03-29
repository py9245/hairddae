from __future__ import annotations


def main() -> int:
    import cv2

    print(f"cv2_version={cv2.__version__}")
    print(f"has_cuda_module={hasattr(cv2, 'cuda')}")
    if hasattr(cv2, "cuda"):
        try:
            print(f"cuda_device_count={cv2.cuda.getCudaEnabledDeviceCount()}")
        except Exception as exc:  # pragma: no cover - runtime dependent
            print(f"cuda_device_count_error={exc}")

    for line in cv2.getBuildInformation().splitlines():
        stripped = line.strip()
        if (
            "NVIDIA CUDA" in line
            or "cuDNN" in line
            or stripped.startswith("To be built:")
            or stripped.startswith("Disabled:")
            or stripped.startswith("Unavailable:")
            or stripped.startswith("OpenCL:")
        ):
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
