#!/usr/bin/env bats

load helpers

setup() {
    setup_tmpdir
    cp "$ROOT/tests/integration/fixtures/valid_images.yaml" "$TMPDIR/images.yaml"
    export LDS_IMAGES_FILE="$TMPDIR/images.yaml"
    export LDS_SKIP_REGISTRY_CHECK=1
    export LDS_NO_GIT=1
}
teardown() { teardown_tmpdir; }

# Build a throwaway git repo so the git-touching paths never act on the real
# checkout. LDS_REPO_DIR is what points images.sh at it.
_scratch_repo() {
    git -C "$TMPDIR" init -q .
    git -C "$TMPDIR" -c user.email=t@t -c user.name=t commit -q --allow-empty -m init
}

@test "images bump: rewrites the tag for a known service" {
    run bash "$ROOT/scripts/images.sh" bump studio 9.9.9
    [ "$status" -eq 0 ]
    run yq e '.studio_image' "$LDS_IMAGES_FILE"
    [[ "$output" == *"experiment-studio:9.9.9"* ]]
}

@test "images bump: preserves the repository, changing only the tag" {
    bash "$ROOT/scripts/images.sh" bump grafana 12.0.0
    run yq e '.grafana_image' "$LDS_IMAGES_FILE"
    [ "$output" = "grafana/grafana:12.0.0" ]
}

@test "images bump: rejects an unknown service with the allowed list" {
    run bash "$ROOT/scripts/images.sh" bump nosuchsvc 1.0.0
    [ "$status" -ne 0 ]
    [[ "$output" == *"unknown service"* ]] || false
    [[ "$output" == *"studio"* ]]
}

@test "images bump: rejects a core repo-built service name" {
    run bash "$ROOT/scripts/images.sh" bump siteapp 1.0.0
    [ "$status" -ne 0 ]
    [[ "$output" == *"unknown service"* ]]
}

@test "images bump: requires both service and version" {
    run bash "$ROOT/scripts/images.sh" bump studio
    [ "$status" -ne 0 ]
    [[ "$output" == *"usage"* ]]
}

@test "images bump: leaves other image keys untouched" {
    bash "$ROOT/scripts/images.sh" bump studio 9.9.9
    run yq e '.grafana_image' "$LDS_IMAGES_FILE"
    [ "$output" = "grafana/grafana:11.3.0" ]
}

@test "images ship: refuses when git working tree is dirty" {
    _scratch_repo
    touch "$TMPDIR/dirty"
    git -C "$TMPDIR" add dirty
    run env LDS_REPO_DIR="$TMPDIR" LDS_IMAGES_FILE="$TMPDIR/images.yaml" \
        bash "$ROOT/scripts/images.sh" ship --dry-run
    [ "$status" -ne 0 ]
    [[ "$output" == *"working tree"* ]]
}

@test "images ship: dry-run prints the releasable commit subject" {
    _scratch_repo
    run env LDS_REPO_DIR="$TMPDIR" LDS_IMAGES_FILE="$TMPDIR/images.yaml" \
        bash "$ROOT/scripts/images.sh" ship --dry-run
    [ "$status" -eq 0 ]
    [[ "$output" == *"feat:"* ]]
}

@test "images bump: dry-run prints the subject and does NOT modify the file" {
    local before
    before="$(yq e '.studio_image' "$LDS_IMAGES_FILE")"
    run bash "$ROOT/scripts/images.sh" bump studio 9.9.9 --dry-run
    [ "$status" -eq 0 ]
    [[ "$output" == *"feat:"* ]] || false
    [[ "$output" == *"studio"* ]] || false
    run yq e '.studio_image' "$LDS_IMAGES_FILE"
    [ "$output" = "$before" ]
}
