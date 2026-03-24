FROM nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_CACHE_DIR=/tmp/uv-cache \
    UV_LINK_MODE=copy \
    MPLCONFIGDIR=/tmp/matplotlib \
    PATH="/root/.local/bin:${PATH}"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        clang \
        cmake \
        curl \
        git \
        libavcodec-dev \
        libavformat-dev \
        libavutil-dev \
        libegl1-mesa-dev \
        libeigen3-dev \
        libgl1-mesa-dev \
        libgles2-mesa-dev \
        libegl1 \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        libjpeg-dev \
        liblapack-dev \
        libopenblas-dev \
        libpng-dev \
        openjdk-17-jdk \
        libswscale-dev \
        libtbb-dev \
        libtiff-dev \
        libwebp-dev \
        ninja-build \
        patchelf \
        pkg-config \
        protobuf-compiler \
        python3 \
        python3-dev \
        python3-pip \
        python3-venv \
        python-is-python3 \
        unzip \
        zip \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv
RUN curl -L --fail --retry 3 \
      https://github.com/bazelbuild/bazelisk/releases/download/v1.25.0/bazelisk-linux-amd64 \
      -o /usr/local/bin/bazel \
    && chmod +x /usr/local/bin/bazel

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev \
    && rm -rf /tmp/uv-cache /root/.cache

COPY scripts ./scripts
ARG OPENCV_CUDA_ARCH_BIN=7.5
RUN bash ./scripts/install_opencv_cuda.sh \
      --python /app/.venv/bin/python \
      --cuda-arch-bin "${OPENCV_CUDA_ARCH_BIN}"
RUN bash ./scripts/install_mediapipe_gpu.sh \
      --python /app/.venv/bin/python

COPY app ./app
COPY hairddae_tools ./hairddae_tools
COPY models ./models

FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_CACHE_DIR=/tmp/uv-cache \
    UV_LINK_MODE=copy \
    MPLCONFIGDIR=/tmp/matplotlib \
    PATH="/root/.local/bin:${PATH}"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        libavcodec58 \
        libavformat58 \
        libavutil56 \
        libegl1 \
        libgl1 \
        libgles2 \
        libglib2.0-0 \
        libgomp1 \
        libjpeg8 \
        libpng16-16 \
        libswscale5 \
        libtiff5 \
        libwebp7 \
        libwebpdemux2 \
        libwebpmux3 \
        python3 \
        python3-pip \
        python3-venv \
        python-is-python3 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/.venv /app/.venv
COPY app ./app
COPY hairddae_tools ./hairddae_tools
COPY models ./models
COPY scripts ./scripts

EXPOSE 8090

CMD ["/app/.venv/bin/python", "-m", "uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8090"]
