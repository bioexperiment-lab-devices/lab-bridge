#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

: "${SITEAPP_IMAGE:?set SITEAPP_IMAGE=ghcr.io/<owner>/lab-bridge-siteapp:<tag>}"

cd "$SCRIPT_DIR"
docker buildx build \
    --platform linux/amd64 \
    --tag "$SITEAPP_IMAGE" \
    --push \
    .
echo
echo "Pushed $SITEAPP_IMAGE"
echo "Now pin in config.yaml: siteapp.image: $SITEAPP_IMAGE"
