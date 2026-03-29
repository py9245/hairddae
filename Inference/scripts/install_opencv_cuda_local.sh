#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${1:-$REPO_ROOT/.venv/bin/python}"
CUDA_ARCH_BIN="${OPENCV_CUDA_ARCH_BIN:-}"
DOCKER_IMAGE="${OPENCV_CUDA_BUILDER_IMAGE:-nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04}"
WORKSPACE_ROOT="${OPENCV_BUILD_WORKSPACE:-$REPO_ROOT/.cache/opencv-cuda-build}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "python not found: $PYTHON_BIN" >&2
  exit 1
fi

if [[ -z "$CUDA_ARCH_BIN" ]]; then
  if command -v nvidia-smi >/dev/null 2>&1; then
    CUDA_ARCH_BIN="$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader 2>/dev/null | head -n 1 || true)"
  fi
  CUDA_ARCH_BIN="${CUDA_ARCH_BIN:-7.5}"
fi

run_direct_build() {
  mkdir -p "$WORKSPACE_ROOT"
  export OPENCV_BUILD_WORKSPACE="$WORKSPACE_ROOT"
  "$REPO_ROOT/scripts/install_opencv_cuda.sh" \
    --python "$PYTHON_BIN" \
    --cuda-arch-bin "$CUDA_ARCH_BIN"
}

run_docker_build() {
  mkdir -p "$WORKSPACE_ROOT"
  docker run --rm \
    --gpus all \
    -e OPENCV_CUDA_ARCH_BIN="$CUDA_ARCH_BIN" \
    -e OPENCV_BUILD_WORKSPACE="$WORKSPACE_ROOT" \
    -e DEBIAN_FRONTEND=noninteractive \
    -e HOST_UID="$(id -u)" \
    -e HOST_GID="$(id -g)" \
    -v "$REPO_ROOT":"$REPO_ROOT" \
    -w "$REPO_ROOT" \
    "$DOCKER_IMAGE" \
    bash -lc "
      apt-get update &&
      apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        cmake \
        curl \
        git \
        ninja-build \
        patchelf \
        pkg-config \
        python3 \
        python3-dev \
        python3-venv \
        python-is-python3 \
        libavcodec-dev \
        libavformat-dev \
        libavutil-dev \
        libeigen3-dev \
        libglib2.0-0 \
        libgl1 \
        libgomp1 \
        libjpeg-dev \
        liblapack-dev \
        libopenblas-dev \
        libpng-dev \
        libswscale-dev \
        libtbb-dev \
        libtiff-dev \
        libwebp-dev \
        zlib1g-dev &&
      bash scripts/install_opencv_cuda.sh --python '$PYTHON_BIN' --cuda-arch-bin '$CUDA_ARCH_BIN' &&
      chown -R \"\$HOST_UID:\$HOST_GID\" '$REPO_ROOT/.venv'
    "
}

if command -v nvcc >/dev/null 2>&1 && command -v cmake >/dev/null 2>&1 && command -v ninja >/dev/null 2>&1 && command -v patchelf >/dev/null 2>&1; then
  run_direct_build
else
  run_docker_build
fi

"$PYTHON_BIN" "$REPO_ROOT/scripts/inspect_opencv_cuda.py"
