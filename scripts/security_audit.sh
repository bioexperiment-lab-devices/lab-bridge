#!/usr/bin/env bash
# Run the security audit harness against a target URL.
#
# Usage:
#   LDS_AUDIT_ADMIN_PASS=... LDS_AUDIT_RES_PASS=... \
#     scripts/security_audit.sh [--target-url=https://...] [--slow]
#
# Outputs:
#   docs/security/<date>-audit-report.md
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT/tests/security"

if [[ -z "${LDS_AUDIT_ADMIN_PASS:-}" ]]; then
    echo "error: LDS_AUDIT_ADMIN_PASS not set" >&2
    exit 2
fi
if [[ -z "${LDS_AUDIT_RES_PASS:-}" ]]; then
    echo "error: LDS_AUDIT_RES_PASS not set" >&2
    exit 2
fi

uv sync >&2
exec uv run pytest "$@"
