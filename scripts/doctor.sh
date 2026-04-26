#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

missing=0
for cmd in task yq htpasswd openssl ssh rsync; do
    if command -v "$cmd" >/dev/null 2>&1; then
        log "$cmd ✓"
    else
        warn "$cmd ✗ (missing)"
        missing=1
    fi
done

# yq must be the mikefarah Go variant (v4+); detect by --version output.
if command -v yq >/dev/null 2>&1; then
    if yq --version 2>&1 | grep -qE 'mikefarah|version v?[4-9]'; then
        log "yq is mikefarah v4+ ✓"
    else
        warn "yq is present but does not look like mikefarah v4+ — install from https://github.com/mikefarah/yq"
        missing=1
    fi
fi

[[ "$missing" -eq 0 ]] || die "missing prerequisites — see README"
log "all prerequisites present"
