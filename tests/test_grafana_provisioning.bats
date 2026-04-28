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
    run yq e '.title' "$ROOT/compose/grafana/provisioning/dashboards/client-logs.json"
    [ "$status" -eq 0 ]
    [[ "$output" == "Lab client logs" ]]
    run yq e '.panels | length' "$ROOT/compose/grafana/provisioning/dashboards/client-logs.json"
    [ "$status" -eq 0 ]
    [[ "$output" == "4" ]]
    run yq e '.panels | map(.title) | join(",")' "$ROOT/compose/grafana/provisioning/dashboards/client-logs.json"
    [ "$status" -eq 0 ]
    [[ "$output" == *"Live tail"* ]]
    [[ "$output" == *"Log volume by client"* ]]
    [[ "$output" == *"Errors"* ]]
    [[ "$output" == *"Current versions"* ]]
    run yq e '.templating.list | map(.name) | join(",")' "$ROOT/compose/grafana/provisioning/dashboards/client-logs.json"
    [ "$status" -eq 0 ]
    [[ "$output" == *"client"* ]]
    [[ "$output" == *"stream"* ]]
    [[ "$output" == *"version"* ]]
}
