#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PYTHON_BIN=""
MEDIAPIPE_VERSION="${MEDIAPIPE_VERSION:-}"
WORKSPACE_ROOT="${MEDIAPIPE_BUILD_WORKSPACE:-/tmp/mediapipe-gpu-build}"
BUILD_JOBS="${MEDIAPIPE_BUILD_JOBS:-}"
PRESERVE_BUILD="${MEDIAPIPE_BUILD_PRESERVE:-1}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --python)
      PYTHON_BIN="$2"
      shift 2
      ;;
    --version)
      MEDIAPIPE_VERSION="$2"
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

for required in "$PYTHON_BIN" bazel clang clang++ cmake curl tar unzip zip; do
  if ! command -v "$required" >/dev/null 2>&1; then
    echo "missing required command: $required" >&2
    exit 1
  fi
done

readarray -t PY_META < <("$PYTHON_BIN" - <<'PY'
import importlib.metadata
import os
import sysconfig

site_packages = sysconfig.get_path("platlib")
mediapipe_root = os.path.join(site_packages, "mediapipe")
tasks_c_dir = os.path.join(mediapipe_root, "tasks", "c")
print(importlib.metadata.version("mediapipe"))
print(site_packages)
print(mediapipe_root)
print(tasks_c_dir)
PY
)

INSTALLED_MEDIAPIPE_VERSION="${PY_META[0]}"
SITE_PACKAGES="${PY_META[1]}"
MEDIAPIPE_ROOT="${PY_META[2]}"
TASKS_C_DIR="${PY_META[3]}"

if [[ -z "$MEDIAPIPE_VERSION" ]]; then
  MEDIAPIPE_VERSION="$INSTALLED_MEDIAPIPE_VERSION"
fi

if [[ ! -d "$MEDIAPIPE_ROOT" ]]; then
  echo "mediapipe package not found under $SITE_PACKAGES" >&2
  exit 1
fi

if [[ -z "$BUILD_JOBS" ]]; then
  BUILD_JOBS="$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)"
fi

WORKSPACE_ROOT="$(realpath "$WORKSPACE_ROOT")"
DOWNLOAD_ROOT="$WORKSPACE_ROOT/downloads"
SRC_ROOT="$WORKSPACE_ROOT/src"
SRC_DIR="$SRC_ROOT/mediapipe-${MEDIAPIPE_VERSION}"

mkdir -p "$DOWNLOAD_ROOT" "$SRC_ROOT" "$TASKS_C_DIR"

ARCHIVE_PATH="$DOWNLOAD_ROOT/mediapipe-v${MEDIAPIPE_VERSION}.tar.gz"
if [[ ! -f "$ARCHIVE_PATH" ]]; then
  curl -L --fail --retry 3 \
    "https://github.com/google-ai-edge/mediapipe/archive/refs/tags/v${MEDIAPIPE_VERSION}.tar.gz" \
    -o "$ARCHIVE_PATH"
fi

if [[ "$PRESERVE_BUILD" != "1" ]]; then
  rm -rf "$SRC_DIR"
fi

if [[ ! -d "$SRC_DIR" ]]; then
  tar -xzf "$ARCHIVE_PATH" -C "$SRC_ROOT"
fi

pushd "$SRC_DIR" >/dev/null

export MEDIAPIPE_DISABLE_GPU=0
export PYTHON_BIN_PATH="$PYTHON_BIN"
export CC="${CC:-$(command -v clang || command -v gcc)}"
export CXX="${CXX:-$(command -v g++ || command -v clang++)}"
export CLANG_CUDA_COMPILER_PATH="${CLANG_CUDA_COMPILER_PATH:-$(command -v clang || command -v clang++)}"
if [[ -z "${CPLUS_INCLUDE_PATH:-}" ]] && command -v g++ >/dev/null 2>&1; then
  GCC_MAJOR_VERSION="$(g++ -dumpversion | cut -d. -f1)"
  export CPLUS_INCLUDE_PATH="/usr/include/c++/${GCC_MAJOR_VERSION}:/usr/include/x86_64-linux-gnu/c++/${GCC_MAJOR_VERSION}:/usr/include/c++/${GCC_MAJOR_VERSION}/backward"
fi
if [[ -n "${GCC_MAJOR_VERSION:-}" ]]; then
  GCC_CXX_INCLUDE_1="/usr/include/c++/${GCC_MAJOR_VERSION}"
  GCC_CXX_INCLUDE_2="/usr/include/x86_64-linux-gnu/c++/${GCC_MAJOR_VERSION}"
  GCC_CXX_INCLUDE_3="/usr/include/c++/${GCC_MAJOR_VERSION}/backward"
  GCC_LIB_DIR_1="/usr/lib/gcc/x86_64-linux-gnu/${GCC_MAJOR_VERSION}"
  GCC_LIB_DIR_2="/usr/lib/x86_64-linux-gnu"
  GCC_LIB_DIR_3="/lib/x86_64-linux-gnu"
fi
if [[ -z "${LIBRARY_PATH:-}" ]] && [[ -n "${GCC_LIB_DIR_1:-}" ]]; then
  export LIBRARY_PATH="${GCC_LIB_DIR_1}:${GCC_LIB_DIR_2}:${GCC_LIB_DIR_3}"
fi
if [[ -z "${LDFLAGS:-}" ]] && [[ -n "${GCC_LIB_DIR_1:-}" ]]; then
  export LDFLAGS="-L${GCC_LIB_DIR_1} -L${GCC_LIB_DIR_2} -L${GCC_LIB_DIR_3}"
fi

"$PYTHON_BIN" - <<'PY'
from pathlib import Path

build_file = Path("mediapipe/tasks/c/BUILD")
content = build_file.read_text()
for needle in [
    '        "//mediapipe/tasks/c/audio/audio_classifier:audio_classifier_c_lib",\n',
    '        "//mediapipe/tasks/c/genai/bundler:llm_bundler_utils_c_lib",\n',
    '        "//mediapipe/tasks/c/genai/converter:llm_converter_c_lib",\n',
    '        "//mediapipe/tasks/c/text/language_detector:language_detector_c_lib",\n',
    '        "//mediapipe/tasks/c/text/text_classifier:text_classifier_c_lib",\n',
    '        "//mediapipe/tasks/c/text/text_embedder:text_embedder_c_lib",\n',
]:
    content = content.replace(needle, "")
build_file.write_text(content)
PY

bazel build \
  --jobs="$BUILD_JOBS" \
  --compilation_mode=opt \
  --copt=-DNDEBUG \
  --keep_going \
  --verbose_failures \
  --define=ENABLE_ODML_CONVERTER=1 \
  --define=MEDIAPIPE_DISABLE_GPU=0 \
  --define=xnn_enable_avxvnniint8=false \
  --define=OPENCV=source \
  --action_env=PYTHON_BIN_PATH="$PYTHON_BIN" \
  --action_env=CC="$CC" \
  --action_env=CXX="$CXX" \
  --action_env=CPLUS_INCLUDE_PATH="${CPLUS_INCLUDE_PATH:-}" \
  --action_env=LIBRARY_PATH="${LIBRARY_PATH:-}" \
  --action_env=LDFLAGS="${LDFLAGS:-}" \
  --repo_env=CC="$CC" \
  --repo_env=CXX="$CXX" \
  --repo_env=CPLUS_INCLUDE_PATH="${CPLUS_INCLUDE_PATH:-}" \
  --repo_env=LIBRARY_PATH="${LIBRARY_PATH:-}" \
  --repo_env=LDFLAGS="${LDFLAGS:-}" \
  --repo_env=CLANG_CUDA_COMPILER_PATH="$CLANG_CUDA_COMPILER_PATH" \
  --copt=-DTFLITE_GPU_EXTRA_GLES_DEPS \
  --copt=-DMEDIAPIPE_OMIT_EGL_WINDOW_BIT \
  --copt=-DMESA_EGL_NO_X11_HEADERS \
  --copt=-DEGL_NO_X11 \
  ${GCC_CXX_INCLUDE_1:+--cxxopt=-isystem${GCC_CXX_INCLUDE_1}} \
  ${GCC_CXX_INCLUDE_2:+--cxxopt=-isystem${GCC_CXX_INCLUDE_2}} \
  ${GCC_CXX_INCLUDE_3:+--cxxopt=-isystem${GCC_CXX_INCLUDE_3}} \
  ${GCC_CXX_INCLUDE_1:+--host_cxxopt=-isystem${GCC_CXX_INCLUDE_1}} \
  ${GCC_CXX_INCLUDE_2:+--host_cxxopt=-isystem${GCC_CXX_INCLUDE_2}} \
  ${GCC_CXX_INCLUDE_3:+--host_cxxopt=-isystem${GCC_CXX_INCLUDE_3}} \
  ${GCC_LIB_DIR_1:+--linkopt=-L${GCC_LIB_DIR_1}} \
  ${GCC_LIB_DIR_2:+--linkopt=-L${GCC_LIB_DIR_2}} \
  ${GCC_LIB_DIR_3:+--linkopt=-L${GCC_LIB_DIR_3}} \
  ${GCC_LIB_DIR_1:+--host_linkopt=-L${GCC_LIB_DIR_1}} \
  ${GCC_LIB_DIR_2:+--host_linkopt=-L${GCC_LIB_DIR_2}} \
  ${GCC_LIB_DIR_3:+--host_linkopt=-L${GCC_LIB_DIR_3}} \
  //mediapipe/tasks/c:libmediapipe.so

BUILT_LIB="bazel-bin/mediapipe/tasks/c/libmediapipe.so"
if [[ ! -f "$BUILT_LIB" ]]; then
  echo "failed to locate built libmediapipe.so" >&2
  exit 1
fi

BUILT_OPENCV_DIR="bazel-bin/third_party/copy_opencv_cmake/opencv_cmake/lib"
MEDIAPIPE_OPENCV_SOLIB_DIR="$SITE_PACKAGES/_solib_k8/_U_S_Sthird_Uparty_Copencv_Ucmake___Uthird_Uparty_Sopencv_Ucmake_Slib"

install -m 755 "$BUILT_LIB" "$TASKS_C_DIR/libmediapipe.so"
if [[ -d "$BUILT_OPENCV_DIR" ]]; then
  mkdir -p "$MEDIAPIPE_OPENCV_SOLIB_DIR"
  cp -af "$BUILT_OPENCV_DIR"/libopencv*.so* "$MEDIAPIPE_OPENCV_SOLIB_DIR"/
  if command -v patchelf >/dev/null 2>&1; then
    while IFS= read -r -d '' lib_path; do
      patchelf --set-rpath '$ORIGIN' "$lib_path"
    done < <(find "$MEDIAPIPE_OPENCV_SOLIB_DIR" -maxdepth 1 -type f -name 'libopencv*.so*' -print0)
  fi
fi
popd >/dev/null

echo "MediaPipe GPU library installed into:"
echo "  python: $PYTHON_BIN"
echo "  lib:    $TASKS_C_DIR/libmediapipe.so"

"$PYTHON_BIN" "$REPO_ROOT/scripts/inspect_mediapipe_gpu.py"
