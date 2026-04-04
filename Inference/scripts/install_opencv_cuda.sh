#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN=""
OPENCV_VERSION="${OPENCV_VERSION:-4.13.0}"
CUDA_ARCH_BIN="${OPENCV_CUDA_ARCH_BIN:-}"
WORKSPACE_ROOT="${OPENCV_BUILD_WORKSPACE:-/tmp/opencv-cuda-build}"
BUILD_JOBS="${OPENCV_BUILD_JOBS:-}"
PRESERVE_BUILD="${OPENCV_BUILD_PRESERVE:-1}"

detect_cuda_arch_bin() {
  local detected=""
  local gpu_name=""

  if command -v nvidia-smi >/dev/null 2>&1; then
    detected="$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader 2>/dev/null | head -n 1 || true)"
    if [[ -n "$detected" ]]; then
      echo "$detected"
      return 0
    fi

    gpu_name="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -n 1 || true)"
    case "$gpu_name" in
      *A10G*|*A10*)
        echo "8.6"
        return 0
        ;;
      *L4*)
        echo "8.9"
        return 0
        ;;
      *A100*)
        echo "8.0"
        return 0
        ;;
      *T4*)
        echo "7.5"
        return 0
        ;;
      *V100*)
        echo "7.0"
        return 0
        ;;
    esac
  fi

  echo ""
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --python)
      PYTHON_BIN="$2"
      shift 2
      ;;
    --opencv-version)
      OPENCV_VERSION="$2"
      shift 2
      ;;
    --cuda-arch-bin)
      CUDA_ARCH_BIN="$2"
      shift 2
      ;;
    --workspace)
      WORKSPACE_ROOT="$2"
      shift 2
      ;;
    --jobs)
      BUILD_JOBS="$2"
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$PYTHON_BIN" ]]; then
  echo "--python is required" >&2
  exit 2
fi

for required in "$PYTHON_BIN" curl tar cmake ninja patchelf; do
  if ! command -v "$required" >/dev/null 2>&1; then
    echo "missing required command: $required" >&2
    exit 1
  fi
done

if ! command -v nvcc >/dev/null 2>&1; then
  echo "nvcc is required inside the build environment" >&2
  exit 1
fi

if [[ -z "$CUDA_ARCH_BIN" ]]; then
  CUDA_ARCH_BIN="$(detect_cuda_arch_bin)"
  CUDA_ARCH_BIN="${CUDA_ARCH_BIN:-7.5}"
fi

if [[ -z "$BUILD_JOBS" ]]; then
  BUILD_JOBS="$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)"
fi

readarray -t PY_META < <("$PYTHON_BIN" - <<'PY'
import glob
import os
import sys
import sysconfig

import numpy

site_packages = sysconfig.get_path("platlib")
cv2_dir = os.path.join(site_packages, "cv2")
if not os.path.isdir(cv2_dir):
    matches = sorted(glob.glob(os.path.join(site_packages, "cv2*")))
    cv2_dir = matches[0] if matches else cv2_dir

libs_candidates = [
    os.path.join(site_packages, "opencv_python_headless.libs"),
    os.path.join(site_packages, "opencv_python.libs"),
    os.path.join(site_packages, "opencv_contrib_python.libs"),
]
libs_dir = next((path for path in libs_candidates if os.path.isdir(path)), libs_candidates[0])
py_include = sysconfig.get_path("include")
py_libdir = sysconfig.get_config_var("LIBDIR") or ""
py_ldlibrary = sysconfig.get_config_var("LDLIBRARY") or ""
py_library = os.path.join(py_libdir, py_ldlibrary) if py_libdir and py_ldlibrary else ""
print(cv2_dir)
print(libs_dir)
print(site_packages)
print(py_include)
print(py_library)
print(numpy.get_include())
print(sys.version_info.major)
print(sys.version_info.minor)
PY
)

CV2_DIR="${PY_META[0]}"
LIBS_DIR="${PY_META[1]}"
SITE_PACKAGES="${PY_META[2]}"
PYTHON_INCLUDE_DIR="${PY_META[3]}"
PYTHON_LIBRARY="${PY_META[4]}"
NUMPY_INCLUDE_DIR="${PY_META[5]}"
PYTHON_MAJOR="${PY_META[6]}"
PYTHON_MINOR="${PY_META[7]}"

WORKSPACE_ROOT="$(realpath "$WORKSPACE_ROOT")"
DOWNLOAD_ROOT="$WORKSPACE_ROOT/downloads"
SRC_ROOT="$WORKSPACE_ROOT/src"
BUILD_ROOT="$WORKSPACE_ROOT/build"
STAGE_ROOT="$WORKSPACE_ROOT/stage"
STAGE_PYTHON_ROOT="$STAGE_ROOT/python"

mkdir -p "$DOWNLOAD_ROOT" "$SRC_ROOT" "$BUILD_ROOT" "$STAGE_PYTHON_ROOT" "$LIBS_DIR"

OPENCV_TARBALL="$DOWNLOAD_ROOT/opencv-${OPENCV_VERSION}.tar.gz"
OPENCV_SRC_DIR="$SRC_ROOT/opencv-${OPENCV_VERSION}"
OPENCV_CONTRIB_TARBALL="$DOWNLOAD_ROOT/opencv_contrib-${OPENCV_VERSION}.tar.gz"
OPENCV_CONTRIB_SRC_DIR="$SRC_ROOT/opencv_contrib-${OPENCV_VERSION}"

if [[ ! -f "$OPENCV_TARBALL" ]]; then
  curl -L --fail --retry 3 \
    "https://github.com/opencv/opencv/archive/refs/tags/${OPENCV_VERSION}.tar.gz" \
    -o "$OPENCV_TARBALL"
fi

if [[ ! -f "$OPENCV_CONTRIB_TARBALL" ]]; then
  curl -L --fail --retry 3 \
    "https://github.com/opencv/opencv_contrib/archive/refs/tags/${OPENCV_VERSION}.tar.gz" \
    -o "$OPENCV_CONTRIB_TARBALL"
fi

if [[ ! -d "$OPENCV_SRC_DIR" ]]; then
  tar -xzf "$OPENCV_TARBALL" -C "$SRC_ROOT"
fi
if [[ ! -d "$OPENCV_CONTRIB_SRC_DIR" ]]; then
  tar -xzf "$OPENCV_CONTRIB_TARBALL" -C "$SRC_ROOT"
fi

if [[ "$PRESERVE_BUILD" != "1" ]]; then
  rm -rf "$BUILD_ROOT" "$STAGE_ROOT"
fi

mkdir -p "$BUILD_ROOT" "$STAGE_PYTHON_ROOT"

CMAKE_ARGS=(
  -S "$OPENCV_SRC_DIR"
  -B "$BUILD_ROOT"
  -G Ninja
  -D CMAKE_BUILD_TYPE=Release
  -D CMAKE_INSTALL_PREFIX="$STAGE_ROOT"
  -D CMAKE_INSTALL_RPATH="\$ORIGIN;\$ORIGIN/../opencv_python_headless.libs"
  -D BUILD_SHARED_LIBS=ON
  -D BUILD_TESTS=OFF
  -D BUILD_PERF_TESTS=OFF
  -D BUILD_EXAMPLES=OFF
  -D BUILD_DOCS=OFF
  -D BUILD_opencv_apps=OFF
  -D BUILD_JAVA=OFF
  -D BUILD_opencv_python2=OFF
  -D BUILD_opencv_python3=ON
  -D INSTALL_PYTHON_EXAMPLES=OFF
  -D OPENCV_GENERATE_PKGCONFIG=ON
  -D ENABLE_FAST_MATH=ON
  -D CUDA_FAST_MATH=ON
  -D WITH_CUDA=ON
  -D WITH_CUBLAS=ON
  -D WITH_CUDNN=ON
  -D OPENCV_DNN_CUDA=ON
  -D WITH_FFMPEG=ON
  -D WITH_GSTREAMER=OFF
  -D WITH_QT=OFF
  -D WITH_OPENGL=OFF
  -D OPENCV_EXTRA_MODULES_PATH="$OPENCV_CONTRIB_SRC_DIR/modules"
  -D PYTHON3_EXECUTABLE="$PYTHON_BIN"
  -D PYTHON3_INCLUDE_DIR="$PYTHON_INCLUDE_DIR"
  -D PYTHON3_NUMPY_INCLUDE_DIRS="$NUMPY_INCLUDE_DIR"
  -D PYTHON3_PACKAGES_PATH="$STAGE_PYTHON_ROOT"
  -D OPENCV_PYTHON3_INSTALL_PATH="$STAGE_PYTHON_ROOT"
  -D CUDA_ARCH_BIN="$CUDA_ARCH_BIN"
  -D BUILD_LIST=core,imgproc,imgcodecs,videoio,photo,calib3d,features2d,flann,ml,objdetect,video,dnn,gapi,highgui,cudaarithm,cudaimgproc,cudawarping,cudev,python3
)

if [[ -n "$PYTHON_LIBRARY" && -f "$PYTHON_LIBRARY" ]]; then
  CMAKE_ARGS+=(-D "PYTHON3_LIBRARY=$PYTHON_LIBRARY")
fi

echo "building CUDA OpenCV ${OPENCV_VERSION} for ${PYTHON_BIN}"
echo "site-packages=${SITE_PACKAGES}"
echo "CUDA_ARCH_BIN=${CUDA_ARCH_BIN}"
cmake "${CMAKE_ARGS[@]}"
cmake --build "$BUILD_ROOT" --parallel "$BUILD_JOBS"
cmake --install "$BUILD_ROOT"

BUILT_SO="$(find "$STAGE_ROOT" -type f -name 'cv2*.so' | head -n 1 || true)"
if [[ -z "$BUILT_SO" ]]; then
  echo "failed to locate built cv2 shared object" >&2
  exit 1
fi

TARGET_SO="$CV2_DIR/cv2.abi3.so"
cp -f "$BUILT_SO" "$TARGET_SO"
patchelf --set-rpath '$ORIGIN/../opencv_python_headless.libs' "$TARGET_SO"

find "$LIBS_DIR" -maxdepth 1 -type f \( -name 'libopencv*.so*' -o -name 'libade*.so*' -o -name 'libcudart*.so*' -o -name 'libcublas*.so*' -o -name 'libcublasLt*.so*' -o -name 'libcudnn*.so*' -o -name 'libcusolver*.so*' -o -name 'libcusparse*.so*' -o -name 'libnpp*.so*' \) -delete

copy_dep() {
  local dep_path="$1"
  local dep_name
  local dep_real
  dep_name="$(basename "$dep_path")"
  dep_real="$(readlink -f "$dep_path")"

  case "$dep_name" in
    linux-vdso.so.*|ld-linux*.so*|libcuda.so*|libnvidia-*.so*|libc.so*|libm.so*|libdl.so*|libpthread.so*|librt.so*)
      return 0
      ;;
  esac

  if [[ ! -f "$LIBS_DIR/$dep_name" ]]; then
    cp -f "$dep_real" "$LIBS_DIR/$dep_name"
    chmod 755 "$LIBS_DIR/$dep_name"
  fi
}

while IFS= read -r lib_path; do
  [[ -n "$lib_path" ]] || continue
  lib_name="$(basename "$lib_path")"
  cp -f "$lib_path" "$LIBS_DIR/$lib_name"
  chmod 755 "$LIBS_DIR/$lib_name"
done < <(find "$STAGE_ROOT" -type f \( -name 'libopencv*.so*' -o -name 'libade*.so*' \) | sort)

while IFS= read -r link_path; do
  [[ -n "$link_path" ]] || continue
  link_name="$(basename "$link_path")"
  link_target="$(readlink "$link_path")"
  [[ -n "$link_target" ]] || continue
  ln -sfn "$link_target" "$LIBS_DIR/$link_name"
done < <(find "$STAGE_ROOT" -type l \( -name 'libopencv*.so*' -o -name 'libade*.so*' \) | sort)

resolved_new=1
while [[ "$resolved_new" -eq 1 ]]; do
  resolved_new=0
  while IFS= read -r scan_target; do
    [[ -n "$scan_target" ]] || continue
    while IFS= read -r dep_path; do
      [[ -n "$dep_path" ]] || continue
      dep_name="$(basename "$dep_path")"
      case "$dep_name" in
        linux-vdso.so.*|ld-linux*.so*|libcuda.so*|libnvidia-*.so*|libc.so*|libm.so*|libdl.so*|libpthread.so*|librt.so*)
          continue
          ;;
      esac
      if [[ ! -f "$LIBS_DIR/$dep_name" ]]; then
        copy_dep "$dep_path"
        resolved_new=1
      fi
    done < <(ldd "$scan_target" 2>/dev/null | awk '/=> \// {print $3}')
  done < <(printf '%s\n' "$TARGET_SO"; find "$LIBS_DIR" -maxdepth 1 -type f -name '*.so*' | sort)
done

while IFS= read -r lib_path; do
  [[ -n "$lib_path" ]] || continue
  patchelf --set-rpath '$ORIGIN' "$lib_path" || true
done < <(find "$LIBS_DIR" -maxdepth 1 -type f -name '*.so*' | sort)

echo "CUDA OpenCV installed into:"
echo "  binary: $TARGET_SO"
echo "  libs:   $LIBS_DIR"

"$PYTHON_BIN" - <<'PY'
import cv2

print("cv2_version", cv2.__version__)
print("has_cuda_module", hasattr(cv2, "cuda"))
if hasattr(cv2, "cuda"):
    try:
        print("cuda_device_count", cv2.cuda.getCudaEnabledDeviceCount())
    except Exception as exc:  # pragma: no cover - runtime dependent
        print("cuda_device_count_error", exc)
PY
