#!/usr/bin/env bats

load helpers

setup() { setup_tmpdir; }
teardown() { teardown_tmpdir; }

@test "log prints a green tagged line to stderr" {
    run bash -c "source $ROOT/scripts/lib/common.sh; log hello 2>&1 1>/dev/null"
    [ "$status" -eq 0 ]
    [[ "$output" == *"hello"* ]]
    [[ "$output" == *"[lab]"* ]]
}

@test "warn prints a yellow tagged line to stderr" {
    run bash -c "source $ROOT/scripts/lib/common.sh; warn careful 2>&1 1>/dev/null"
    [ "$status" -eq 0 ]
    [[ "$output" == *"careful"* ]]
    [[ "$output" == *"[warn]"* ]]
}

@test "die prints to stderr and exits non-zero" {
    run bash -c "source $ROOT/scripts/lib/common.sh; die nope"
    [ "$status" -ne 0 ]
    [[ "$output" == *"nope"* ]]
}

@test "require_cmd succeeds when command exists" {
    run bash -c "source $ROOT/scripts/lib/common.sh; require_cmd ls"
    [ "$status" -eq 0 ]
}

@test "require_cmd fails when command missing" {
    run bash -c "source $ROOT/scripts/lib/common.sh; require_cmd definitely_not_a_command_xyz"
    [ "$status" -ne 0 ]
    [[ "$output" == *"definitely_not_a_command_xyz"* ]]
}

@test "_profile_images: core profile omits the heavy optional images" {
    local fixture_chisel fixture_authelia
    fixture_chisel="$(yq e '.chisel_image' "$ROOT/tests/integration/fixtures/valid_images.yaml")"
    fixture_authelia="$(yq e '.authelia_image' "$ROOT/compose/images.yaml")"
    run bash -c "source $ROOT/tests/integration/helpers.bash; LDS_SUITE_PROFILE=core _profile_images"
    [ "$status" -eq 0 ] || false
    [[ "$output" != *"scipy-notebook"* ]] || false
    [[ "$output" != *"experiment-studio"* ]] || false
    [[ "$output" == *"caddy"* ]] || false
    [[ "$output" == *"$fixture_chisel"* ]] || false
    [[ "$output" == *"$fixture_authelia"* ]]
}

@test "_profile_images: full profile includes every fixture image" {
    local fixture_loki fixture_grafana
    fixture_loki="$(yq e '.loki_image' "$ROOT/tests/integration/fixtures/valid_images.yaml")"
    fixture_grafana="$(yq e '.grafana_image' "$ROOT/tests/integration/fixtures/valid_images.yaml")"
    run bash -c "source $ROOT/tests/integration/helpers.bash; LDS_SUITE_PROFILE=full _profile_images"
    [ "$status" -eq 0 ] || false
    [[ "$output" == *"scipy-notebook"* ]] || false
    [[ "$output" == *"experiment-studio"* ]] || false
    [[ "$output" == *"$fixture_loki"* ]] || false
    [[ "$output" == *"$fixture_grafana"* ]]
}

@test "_profile_images: reads tags from the fixture, not hardcoded values" {
    local fixture_studio
    fixture_studio="$(yq e '.studio_image' "$ROOT/tests/integration/fixtures/valid_images.yaml")"
    run bash -c "source $ROOT/tests/integration/helpers.bash; LDS_SUITE_PROFILE=full _profile_images"
    [[ "$output" == *"$fixture_studio"* ]]
}

@test "_profile_images: fails loudly instead of emitting 'null' when a fixture key is renamed" {
    local broken="$BATS_TEST_TMPDIR/broken_images.yaml"
    cp "$ROOT/tests/integration/fixtures/valid_images.yaml" "$broken"
    # Mirror the reviewer's exact repro: rename a required key so yq's plain
    # `.loki_image` lookup would print the literal string "null" and exit 0.
    yq -i 'del(.loki_image)' "$broken"
    run bash -c "source $ROOT/tests/integration/helpers.bash; _profile_images '$broken'"
    [ "$status" -ne 0 ] || false
    [[ "$output" != *"null"* ]]
}

@test "compose_images_available: aborts hard (not a graceful skip) when _profile_images fails" {
    # Stub out _profile_images after sourcing helpers.bash so this exercises
    # compose_images_available's own propagation logic without needing
    # docker or a broken fixture on disk. A `return 1` here would be
    # indistinguishable to callers from "Docker Hub rate-limited, skip
    # gracefully" — the exact false-green class this fix closes — so the
    # real function must exit the process instead.
    run bash -c "
        source $ROOT/tests/integration/helpers.bash
        _profile_images() { echo 'yq error: key not found' >&2; return 1; }
        compose_images_available
    "
    [ "$status" -ne 0 ] || false
    [[ "$output" == *"test-infra bug"* ]]
}
