# syntax=docker/dockerfile:1.7
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# aiortc native deps: PyAV needs libav*, aiortc needs libsrtp + libvpx + libopus.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libavdevice59 libavfilter9 libavformat60 libavcodec60 libavutil58 \
    libswscale7 libswresample4 \
    libsrtp2-1 libopus0 libvpx7 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app

RUN useradd --uid 10001 --create-home streamer && \
    mkdir -p /data && \
    chown -R streamer:streamer /app /data
USER streamer

ENV PYTHONPATH=/app

ARG LAB_BRIDGE_VERSION=dev
ARG LAB_BRIDGE_GIT_SHA=unknown
ENV LAB_BRIDGE_VERSION=$LAB_BRIDGE_VERSION \
    LAB_BRIDGE_GIT_SHA=$LAB_BRIDGE_GIT_SHA

EXPOSE 8000
EXPOSE 50000-50100/udp
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
    CMD python -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').status==200 else 1)" || exit 1

CMD ["uv", "run", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
