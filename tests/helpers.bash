# Source from the repo root regardless of where bats was invoked.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

setup_tmpdir() {
    TMPDIR="$(mktemp -d)"
    export TMPDIR
}

teardown_tmpdir() {
    [[ -n "${TMPDIR:-}" && -d "$TMPDIR" ]] && rm -rf "$TMPDIR"
}

fixture() {
    cat "$ROOT/tests/fixtures/$1"
}
