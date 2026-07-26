#!/usr/bin/env bats

load helpers

setup() { setup_tmpdir; }
teardown() { teardown_tmpdir; }

@test "log prints a green tagged line to stderr" {
    run bash -c "source $ROOT/scripts/lib/common.sh; log hello 2>&1 1>/dev/null"
    [ "$status" -eq 0 ]
    [[ "$output" == *"hello"* ]] || false
    [[ "$output" == *"[lab]"* ]]
}

@test "warn prints a yellow tagged line to stderr" {
    run bash -c "source $ROOT/scripts/lib/common.sh; warn careful 2>&1 1>/dev/null"
    [ "$status" -eq 0 ]
    [[ "$output" == *"careful"* ]] || false
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

@test "compose_images_available: aborts hard so the caller's skip-guard idiom can't swallow it as a graceful skip" {
    # Every heavy bats suite calls this as
    # `if ! compose_images_available; then <write skip marker>; fi`. Stub out
    # _profile_images after sourcing helpers.bash (no docker or broken
    # fixture needed) and put the guard call itself inside that same `if`
    # idiom, so this test proves the real regression class: a `return 1`
    # here is indistinguishable to that `if` from "Docker Hub rate-limited,
    # skip gracefully" and gets swallowed silently, while the required
    # `exit 1` blows past the `if` entirely and is never reached.
    run bash -c "
        source $ROOT/tests/integration/helpers.bash
        _profile_images() { echo 'yq error: key not found' >&2; return 1; }
        if ! compose_images_available; then echo SWALLOWED_AS_SKIP; fi
        echo REACHED_AFTER_GUARD
    "
    [ "$status" -ne 0 ] || false
    [[ "$output" == *"test-infra bug"* ]] || false
    [[ "$output" != *"SWALLOWED_AS_SKIP"* ]] || false
    [[ "$output" != *"REACHED_AFTER_GUARD"* ]]
}

@test "preload_fake_vps_images: aborts hard so the caller's skip-guard idiom can't swallow it as a graceful skip" {
    # Mirror of the compose_images_available test above: preload_fake_vps_images
    # is the guard's sibling consumer of _profile_images and must exit the
    # process on the same failure, for the same reason — a `return 1` here
    # would be indistinguishable to an `if ! preload_fake_vps_images; then
    # skip; fi` caller from a benign miss, silently turning a broken fixture
    # into a permanent, undetected skip.
    run bash -c "
        source $ROOT/tests/integration/helpers.bash
        _profile_images() { echo 'yq error: key not found' >&2; return 1; }
        if ! preload_fake_vps_images; then echo SWALLOWED_AS_SKIP; fi
        echo REACHED_AFTER_GUARD
    "
    [ "$status" -ne 0 ] || false
    [[ "$output" == *"aborting rather than silently preloading"* ]] || false
    [[ "$output" != *"SWALLOWED_AS_SKIP"* ]] || false
    [[ "$output" != *"REACHED_AFTER_GUARD"* ]]
}

@test "compose_images_available: LDS_REQUIRE_IMAGES=1 turns an unpullable image into a hard failure" {
    # On a release-please PR the heavy suite is the integration gate in front
    # of the production deploy, so "couldn't pull, tested nothing" must be red.
    # Same swallow-proof shape as the fixture-desync tests above: the guard
    # call sits inside the very `if ! …; then skip; fi` idiom the suites use,
    # so a mere `return 1` would be silently absorbed.
    run bash -c "
        source $ROOT/tests/integration/helpers.bash
        _profile_images() { echo 'ghcr.io/example/never-resolves:0.0.0'; }
        docker() { return 1; }   # both inspect and pull fail
        export LDS_PULL_RETRY_DELAYS='0'
        export LDS_REQUIRE_IMAGES=1
        if ! compose_images_available; then echo SWALLOWED_AS_SKIP; fi
        echo REACHED_AFTER_GUARD
    "
    [ "$status" -ne 0 ] || false
    [[ "$output" == *"LDS_REQUIRE_IMAGES=1"* ]] || false
    [[ "$output" != *"SWALLOWED_AS_SKIP"* ]] || false
    [[ "$output" != *"REACHED_AFTER_GUARD"* ]]
}

@test "compose_images_available: without LDS_REQUIRE_IMAGES an unpullable image still skips gracefully" {
    # The default has to stay a graceful skip: an ordinary PR that trips a
    # Docker Hub anonymous-pull rate limit should not go red.
    run bash -c "
        source $ROOT/tests/integration/helpers.bash
        _profile_images() { echo 'ghcr.io/example/never-resolves:0.0.0'; }
        docker() { return 1; }
        export LDS_PULL_RETRY_DELAYS='0'
        if ! compose_images_available; then echo SWALLOWED_AS_SKIP; fi
        echo REACHED_AFTER_GUARD
    "
    [ "$status" -eq 0 ] || false
    [[ "$output" == *"SWALLOWED_AS_SKIP"* ]] || false
    [[ "$output" == *"REACHED_AFTER_GUARD"* ]]
}

@test "_docker_pull_retry: retries a failing pull before giving up, and stops on success" {
    # A single transient 429 must not cost the suite its whole run.
    run bash -c "
        source $ROOT/tests/integration/helpers.bash
        attempts=0
        docker() { attempts=\$((attempts+1)); [ \"\$attempts\" -ge 3 ] && return 0; return 1; }
        export LDS_PULL_RETRY_DELAYS='0 0 0'
        _docker_pull_retry img:1 && echo \"PULLED after \$attempts\"
    "
    [ "$status" -eq 0 ] || false
    [[ "$output" == *"PULLED after 3"* ]]
}
