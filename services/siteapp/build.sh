#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

VERSION="$(awk 'NF { print $1; exit }' "$REPO_ROOT/VERSION")"
GIT_SHA="$(git -C "$REPO_ROOT" rev-parse --short=7 HEAD 2>/dev/null || echo unknown)"

: "${SITEAPP_IMAGE_REPO:=$(yq e '.siteapp_image_repo' "$REPO_ROOT/compose/pins.yaml")}"
SITEAPP_IMAGE="${SITEAPP_IMAGE_REPO}:${VERSION}"

cd "$SCRIPT_DIR"
docker buildx build \
    --platform linux/amd64 \
    --build-arg "LAB_BRIDGE_VERSION=${VERSION}" \
    --build-arg "LAB_BRIDGE_GIT_SHA=${GIT_SHA}" \
    --tag "$SITEAPP_IMAGE" \
    --push \
    .
echo
echo "Pushed $SITEAPP_IMAGE"
echo "Version is managed by release-please — do not bump VERSION manually."
