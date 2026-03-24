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

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev \
    && rm -rf /tmp/uv-cache /root/.cache

COPY app ./app
COPY hairddae_tools ./hairddae_tools
COPY models ./models

EXPOSE 8090

CMD ["/app/.venv/bin/python", "-m", "uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8090"]
