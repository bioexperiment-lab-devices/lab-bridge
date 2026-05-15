# syntax=docker/dockerfile:1.7

# --- Stage 1: build the SPA ---
FROM node:20-alpine AS web-builder

WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund

COPY web/ ./
# Vite's outDir is ../app/static (relative to web/). We redirect the output
# into /web/dist instead so the second stage can copy it into a fresh tree.
RUN npm run build -- --outDir dist --emptyOutDir

# --- Stage 2: Python runtime ---
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY --from=web-builder /web/dist ./app/static

RUN useradd --uid 10001 --create-home flasher && \
    chown -R flasher:flasher /app
USER flasher

ENV PYTHONPATH=/app

ARG LAB_BRIDGE_VERSION=dev
ARG LAB_BRIDGE_GIT_SHA=unknown
ENV LAB_BRIDGE_VERSION=$LAB_BRIDGE_VERSION \
    LAB_BRIDGE_GIT_SHA=$LAB_BRIDGE_GIT_SHA

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
    CMD python -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').status==200 else 1)" || exit 1

CMD ["uv", "run", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
