#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${1:-$REPO_ROOT/.venv/bin/python}"
DOCKER_IMAGE="${MEDIAPIPE_GPU_BUILDER_IMAGE:-nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04}"
WORKSPACE_ROOT="${MEDIAPIPE_BUILD_WORKSPACE:-$REPO_ROOT/.cache/mediapipe-gpu-build}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "python not found: $PYTHON_BIN" >&2
  exit 1
fi

run_direct_build() {
  mkdir -p "$WORKSPACE_ROOT"
  export MEDIAPIPE_BUILD_WORKSPACE="$WORKSPACE_ROOT"
  "$REPO_ROOT/scripts/install_mediapipe_gpu.sh" --python "$PYTHON_BIN"
}

run_docker_build() {
  mkdir -p "$WORKSPACE_ROOT"
  mkdir -p "$WORKSPACE_ROOT/bazel-cache"
  docker run --rm \
    --gpus all \
    -e MEDIAPIPE_BUILD_WORKSPACE="$WORKSPACE_ROOT" \
    -e DEBIAN_FRONTEND=noninteractive \
    -e HOST_UID="$(id -u)" \
    -e HOST_GID="$(id -g)" \
    -v "$REPO_ROOT":"$REPO_ROOT" \
    -v "$WORKSPACE_ROOT/bazel-cache":/root/.cache/bazel \
    -w "$REPO_ROOT" \
    "$DOCKER_IMAGE" \
    bash -lc "
      apt-get update &&
      apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        clang \
        cmake \
        curl \
        git \
        libegl1-mesa-dev \
        libgl1-mesa-dev \
        libgles2-mesa-dev \
        openjdk-17-jdk \
        protobuf-compiler \
        python3 \
        python3-dev \
        python3-venv \
        python-is-python3 \
        unzip \
        zip &&
      if ! command -v bazel >/dev/null 2>&1; then
        curl -L --fail --retry 3 \
          https://github.com/bazelbuild/bazelisk/releases/download/v1.25.0/bazelisk-linux-amd64 \
          -o /usr/local/bin/bazel &&
        chmod +x /usr/local/bin/bazel
      fi &&
      bash scripts/install_mediapipe_gpu.sh --python '$PYTHON_BIN' &&
      chown -R \"\$HOST_UID:\$HOST_GID\" '$REPO_ROOT/.venv'
    "
}

if command -v bazel >/dev/null 2>&1 && command -v clang >/dev/null 2>&1 && command -v clang++ >/dev/null 2>&1 && command -v cmake >/dev/null 2>&1 && command -v protoc >/dev/null 2>&1 && command -v java >/dev/null 2>&1; then
  run_direct_build
else
  run_docker_build
fi

"$PYTHON_BIN" "$REPO_ROOT/scripts/inspect_mediapipe_gpu.py"
