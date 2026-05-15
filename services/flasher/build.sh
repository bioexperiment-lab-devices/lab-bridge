#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

VERSION="$(awk 'NF { print $1; exit }' "$SCRIPT_DIR/VERSION")"
GIT_SHA="$(git -C "$REPO_ROOT" rev-parse --short=7 HEAD 2>/dev/null || echo unknown)"

: "${FLASHER_IMAGE_REPO:=$(yq e '.flasher_image_repo' "$REPO_ROOT/compose/pins.yaml")}"
FLASHER_IMAGE="${FLASHER_IMAGE_REPO}:${VERSION}"

cd "$SCRIPT_DIR"
docker buildx build \
    --platform linux/amd64 \
    --build-arg "LAB_BRIDGE_VERSION=${VERSION}" \
    --build-arg "LAB_BRIDGE_GIT_SHA=${GIT_SHA}" \
    --tag "$FLASHER_IMAGE" \
    --push \
    .
echo
echo "Pushed $FLASHER_IMAGE"
echo "Bump services/flasher/VERSION and commit to pin this tag."
