#!/usr/bin/env bats

load helpers

@test "grafana datasource yaml is valid YAML and points to loki:3100" {
    run yq e '.datasources[0].url' "$ROOT/compose/grafana/provisioning/datasources/loki.yaml"
    [ "$status" -eq 0 ]
    [[ "$output" == "http://loki:3100" ]]
}

@test "grafana datasource has stable uid 'loki' (matches dashboard refs)" {
    run yq e '.datasources[0].uid' "$ROOT/compose/grafana/provisioning/datasources/loki.yaml"
    [ "$status" -eq 0 ]
    [[ "$output" == "loki" ]]
}

@test "grafana dashboard provider yaml is valid and read-only" {
    run yq e '.providers[0].editable' "$ROOT/compose/grafana/provisioning/dashboards/lab-bridge.yaml"
    [ "$status" -eq 0 ]
    [[ "$output" == "false" ]]
}

@test "grafana dashboard json is valid JSON with the four expected panels" {
    # Use -p json -oy so yq treats the file as JSON input and emits YAML output
    # (bare strings without quotes). Without -p json the output format is
    # auto-detected by extension, but auto-mode emits quoted JSON strings in
    # yq v4.45+ which breaks the equality assertions below.
    run bash -c "yq -p json -oy e '.title' '$ROOT/compose/grafana/provisioning/dashboards/client-logs.json' 2>/dev/null"
    [ "$status" -eq 0 ]
    [[ "$output" == "Lab client logs" ]]
    run bash -c "yq -p json -oy e '.panels | length' '$ROOT/compose/grafana/provisioning/dashboards/client-logs.json' 2>/dev/null"
    [ "$status" -eq 0 ]
    [[ "$output" == "4" ]]
    run bash -c "yq -p json -oy e '.panels | map(.title) | join(\",\")' '$ROOT/compose/grafana/provisioning/dashboards/client-logs.json' 2>/dev/null"
    [ "$status" -eq 0 ]
    [[ "$output" == *"Live tail"* ]]
    [[ "$output" == *"Log volume by client"* ]]
    [[ "$output" == *"Errors"* ]]
    [[ "$output" == *"Current versions"* ]]
    run bash -c "yq -p json -oy e '.templating.list | map(.name) | join(\",\")' '$ROOT/compose/grafana/provisioning/dashboards/client-logs.json' 2>/dev/null"
    [ "$status" -eq 0 ]
    [[ "$output" == *"client"* ]]
    [[ "$output" == *"stream"* ]]
    [[ "$output" == *"version"* ]]
}
