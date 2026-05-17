#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

VERSION="$(awk 'NF { print $1; exit }' "$REPO_ROOT/VERSION")"
GIT_SHA="$(git -C "$REPO_ROOT" rev-parse --short=7 HEAD 2>/dev/null || echo unknown)"

: "${CADDY_IMAGE_REPO:=$(yq e '.caddy_image_repo' "$REPO_ROOT/compose/pins.yaml")}"
if [[ -z "$CADDY_IMAGE_REPO" || "$CADDY_IMAGE_REPO" == "null" ]]; then
    echo "Error: caddy_image_repo not found in compose/pins.yaml." >&2
    echo "This entry is added in Task 10 of the shared-navbar plan;" >&2
    echo "build.sh is not runnable until that task lands." >&2
    exit 1
fi
CADDY_IMAGE="${CADDY_IMAGE_REPO}:${VERSION}"

cd "$SCRIPT_DIR"
docker buildx build \
    --platform linux/amd64 \
    --build-arg "LAB_BRIDGE_VERSION=${VERSION}" \
    --build-arg "LAB_BRIDGE_GIT_SHA=${GIT_SHA}" \
    --tag "$CADDY_IMAGE" \
    --push \
    .
echo
echo "Pushed $CADDY_IMAGE"
echo "Version is managed by release-please — do not bump VERSION manually."
