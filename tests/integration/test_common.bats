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
    run bash -c "source $ROOT/tests/integration/helpers.bash; LDS_SUITE_PROFILE=core _profile_images"
    [ "$status" -eq 0 ] || false
    [[ "$output" != *"scipy-notebook"* ]] || false
    [[ "$output" != *"experiment-studio"* ]] || false
    [[ "$output" == *"caddy"* ]] || false
    [[ "$output" == *"authelia"* ]]
}

@test "_profile_images: full profile includes every fixture image" {
    run bash -c "source $ROOT/tests/integration/helpers.bash; LDS_SUITE_PROFILE=full _profile_images"
    [ "$status" -eq 0 ] || false
    [[ "$output" == *"scipy-notebook"* ]] || false
    [[ "$output" == *"experiment-studio"* ]] || false
    [[ "$output" == *"grafana"* ]]
}

@test "_profile_images: reads tags from the fixture, not hardcoded values" {
    local fixture_studio
    fixture_studio="$(yq e '.studio_image' "$ROOT/tests/integration/fixtures/valid_images.yaml")"
    run bash -c "source $ROOT/tests/integration/helpers.bash; LDS_SUITE_PROFILE=full _profile_images"
    [[ "$output" == *"$fixture_studio"* ]]
}
