# Chisel Client Log Forwarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add internal Loki + Grafana to the lab-bridge stack so chisel clients can push logs over the existing tunnel and the operator can query them in a browser.

**Architecture:** Two new containers on the existing `labnet` Docker network. Loki has no published port — it is reachable from Grafana over `labnet` and from clients only via a chisel forward tunnel (`127.0.0.1:3100 → loki:3100`). Grafana is exposed via a `/grafana/` subpath on the existing Caddy site (one shared TLS cert, no new public ports). Chisel auth gates network reachability; Loki itself runs in single-tenant mode.

**Tech Stack:** Docker Compose, Caddy v2, jpillora/chisel, Grafana Loki 3.x, Grafana 11.x, bash + yq + sed for templating, bats-core for tests.

---

## File Structure

**New files:**
- `compose/loki/config.yaml.tmpl` — Loki single-binary config; `__LOKI_RETENTION_HOURS__` substituted at deploy time.
- `compose/grafana/provisioning/datasources/loki.yaml` — static; declares the Loki datasource.
- `compose/grafana/provisioning/dashboards/lab-bridge.yaml` — static; dashboard provider config.
- `compose/grafana/provisioning/dashboards/client-logs.json` — static; bundled dashboard.

**Modified files:**
- `compose/docker-compose.yml.tmpl` — add `loki`, `grafana` services and top-level `secrets:`.
- `compose/Caddyfile.tmpl` — add `handle_path /grafana/*` block.
- `compose/chisel-users.json.tmpl` — header comment update only (output schema doc).
- `config.example.yaml`, `config.yaml` — add `loki:`, `grafana:` sections.
- `tests/fixtures/valid_config.yaml` — same additions.
- `scripts/lib/config.sh` — validate new fields; export `LOKI_IMAGE`, `LOKI_RETENTION_DAYS`, `GRAFANA_IMAGE`.
- `scripts/lib/render.sh` — extend `render_compose`, `render_chisel_users`; add `render_loki_config`.
- `scripts/secrets.sh` — add `set-grafana-password` subcommand.
- `scripts/provision.sh` — create `loki_data` (uid 10001) and `grafana_data` (uid 472).
- `scripts/deploy.sh` — stage Loki config + Grafana provisioning + admin password; add rsync excludes.
- `scripts/ops.sh` — add `logs:loki`, `logs:grafana`, `loki-disk` subcommands.
- `Taskfile.yml` — wire new task commands.
- `.gitignore` — add `compose/grafana/admin_password`.
- `README.md` — quick-start additions and Grafana URL pointer.
- `tests/test_render.bats`, `tests/test_config.bats`, `tests/test_secrets.bats`, `tests/test_deploy.bats`, `tests/test_ops.bats` — extended with new cases.

---

## Task 1: Extend config schema and validation

**Files:**
- Modify: `tests/fixtures/valid_config.yaml`
- Modify: `scripts/lib/config.sh`
- Modify: `tests/test_config.bats`
- Modify: `config.example.yaml`
- Modify: `config.yaml`

- [ ] **Step 1: Add new sections to the test fixture**

Append to `tests/fixtures/valid_config.yaml`:

```yaml
loki:
  image: grafana/loki:3.2.1
  retention_days: 30
grafana:
  image: grafana/grafana:11.3.0
```

The full updated file should be:

```yaml
vps:
  host: 192.0.2.10
  ssh_user: khamit
  ssh_port: 22
  remote_root: /srv/lab-bridge
  notebooks_path: /srv/jupyterlab/work
caddy:
  acme_email: ops@example.com
jupyter:
  image: quay.io/jupyter/scipy-notebook:2026-04-20
  password_hash: "sha1:abcdef012345:0123456789abcdef0123456789abcdef01234567"
chisel:
  image: jpillora/chisel:1.10.1
  listen_port: 8080
loki:
  image: grafana/loki:3.2.1
  retention_days: 30
grafana:
  image: grafana/grafana:11.3.0
chisel_clients:
  - name: microscope-1
    reverse_port: 9001
    password: "k7HfLpNqRsT3uVwX1yZ2aB3cD4eF5gH6"
```

- [ ] **Step 2: Write the failing test for new required fields**

Append to `tests/test_config.bats`:

```bash
@test "validate_config: rejects config missing loki/grafana fields" {
    cat > "$TMPDIR/bad.yaml" <<'EOF'
vps: {host: 1.2.3.4, ssh_user: u, ssh_port: 22, remote_root: /srv/x, notebooks_path: /srv/y}
caddy: {acme_email: o@x.io}
jupyter:
  image: quay.io/jupyter/scipy-notebook:2026-04-20
  password_hash: "sha1:abcdef012345:0123456789abcdef0123456789abcdef01234567"
chisel: {image: jpillora/chisel:1.10.1, listen_port: 8080}
chisel_clients: []
EOF
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $TMPDIR/bad.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"loki.image"* ]]
    [[ "$output" == *"loki.retention_days"* ]]
    [[ "$output" == *"grafana.image"* ]]
}

@test "validate_config: rejects non-numeric loki.retention_days" {
    cp "$ROOT/tests/fixtures/valid_config.yaml" "$TMPDIR/cfg.yaml"
    yq -i '.loki.retention_days = "abc"' "$TMPDIR/cfg.yaml"
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $TMPDIR/cfg.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"retention_days"* ]]
}

@test "load_config: exports LOKI_IMAGE, LOKI_RETENTION_DAYS, GRAFANA_IMAGE" {
    run bash -c "source $ROOT/scripts/lib/config.sh; load_config $ROOT/tests/fixtures/valid_config.yaml; echo \$LOKI_IMAGE \$LOKI_RETENTION_DAYS \$GRAFANA_IMAGE"
    [ "$status" -eq 0 ]
    [[ "$output" == *"grafana/loki:3.2.1 30 grafana/grafana:11.3.0"* ]]
}
```

- [ ] **Step 3: Run tests, verify they fail**

Run: `bats tests/test_config.bats`
Expected: the three new tests fail (missing fields not yet validated; LOKI_IMAGE not yet exported).

- [ ] **Step 4: Add validation and exports in config.sh**

In `scripts/lib/config.sh`, extend `_REQUIRED_FIELDS` and `load_config`:

```bash
_REQUIRED_FIELDS=(
    .vps.host
    .vps.ssh_user
    .vps.ssh_port
    .vps.remote_root
    .vps.notebooks_path
    .caddy.acme_email
    .jupyter.image
    .jupyter.password_hash
    .chisel.image
    .chisel.listen_port
    .loki.image
    .loki.retention_days
    .grafana.image
)
```

After the existing `chisel_clients` validation loop (right before the `if (( ${#errors[@]} > 0 ))` block), add:

```bash
    # loki.retention_days must be a positive integer.
    local retention
    retention="$(_yq e '.loki.retention_days // ""' "$path")"
    if [[ -n "$retention" ]] && ! [[ "$retention" =~ ^[0-9]+$ ]]; then
        errors+=("loki.retention_days must be a positive integer, got: $retention")
    fi
```

In `load_config`, add the new exports next to the existing ones:

```bash
    export LOKI_IMAGE          ; LOKI_IMAGE="$(_yq e '.loki.image' "$path")"
    export LOKI_RETENTION_DAYS ; LOKI_RETENTION_DAYS="$(_yq e '.loki.retention_days' "$path")"
    export GRAFANA_IMAGE       ; GRAFANA_IMAGE="$(_yq e '.grafana.image' "$path")"
```

- [ ] **Step 5: Run tests, verify they pass**

Run: `bats tests/test_config.bats`
Expected: all tests pass (existing ones remain green).

- [ ] **Step 6: Update `config.example.yaml`**

Append before `# Lab devices that connect inbound via chisel.`:

```yaml
loki:
  # Single-binary, filesystem-backed log storage. Pinned for reproducibility.
  image: grafana/loki:3.2.1
  retention_days: 30                  # age-based eviction in Loki's compactor

grafana:
  # UI for tailing/searching the chisel-client logs Loki ingests.
  # Behind the existing Caddy site at https://<vps-host>/grafana/.
  image: grafana/grafana:11.3.0
```

- [ ] **Step 7: Update local `config.yaml`**

Same additions as `config.example.yaml`. Use the operator's existing values; `retention_days: 30`, the two pinned images.

- [ ] **Step 8: Commit**

```bash
git add tests/fixtures/valid_config.yaml scripts/lib/config.sh tests/test_config.bats config.example.yaml config.yaml
git commit -m "feat(config): add loki/grafana config sections and validation"
```

---

## Task 2: Render Loki and Grafana services into docker-compose

**Files:**
- Modify: `compose/docker-compose.yml.tmpl`
- Modify: `scripts/lib/render.sh`
- Modify: `tests/test_render.bats`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_render.bats`:

```bash
@test "render_compose: emits loki and grafana services with correct images" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/fixtures/valid_config.yaml
        render_compose $ROOT/compose/docker-compose.yml.tmpl $TMPDIR/docker-compose.yml
        cat $TMPDIR/docker-compose.yml
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"image: grafana/loki:3.2.1"* ]]
    [[ "$output" == *"image: grafana/grafana:11.3.0"* ]]
    [[ "$output" == *"GF_SERVER_ROOT_URL: https://192.0.2.10/grafana/"* ]]
    [[ "$output" == *"./loki/config.yaml:/etc/loki/config.yaml:ro"* ]]
    [[ "$output" == *"./loki_data:/loki"* ]]
    [[ "$output" == *"./grafana_data:/var/lib/grafana"* ]]
    [[ "$output" == *"./grafana/admin_password"* ]]
    [[ "$output" != *"__"*"__"* ]]
}

@test "render_compose: loki has no published ports (only labnet)" {
    bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/fixtures/valid_config.yaml
        render_compose $ROOT/compose/docker-compose.yml.tmpl $TMPDIR/docker-compose.yml
    "
    # Extract the loki service block and assert no `ports:` key in it.
    run yq e '.services.loki | has("ports")' "$TMPDIR/docker-compose.yml"
    [ "$status" -eq 0 ]
    [[ "$output" == "false" ]]
}
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `bats tests/test_render.bats`
Expected: the two new tests fail (template doesn't contain loki/grafana yet).

- [ ] **Step 3: Extend the docker-compose template**

In `compose/docker-compose.yml.tmpl`, append the new services *before* the closing `networks:` section, and add a top-level `secrets:` section:

```yaml
  loki:
    image: __LOKI_IMAGE__
    restart: unless-stopped
    command: ["-config.file=/etc/loki/config.yaml"]
    volumes:
      - ./loki/config.yaml:/etc/loki/config.yaml:ro
      - ./loki_data:/loki
    networks: [labnet]
    # No `ports:` — only Grafana (over labnet) and chisel-tunneled clients reach it.

  grafana:
    image: __GRAFANA_IMAGE__
    restart: unless-stopped
    environment:
      GF_SECURITY_ADMIN_PASSWORD__FILE: /run/secrets/grafana_admin_password
      GF_SERVER_ROOT_URL: https://__VPS_HOST__/grafana/
      GF_SERVER_SERVE_FROM_SUB_PATH: "true"
      GF_USERS_ALLOW_SIGN_UP: "false"
      GF_AUTH_ANONYMOUS_ENABLED: "false"
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
      - ./grafana_data:/var/lib/grafana
    secrets:
      - grafana_admin_password
    networks: [labnet]
    depends_on: [loki]

networks:
  labnet:
    driver: bridge

secrets:
  grafana_admin_password:
    file: ./grafana/admin_password
```

(Replace the original `networks:` block with the new one shown above; the `services:` keys above it stay unchanged.)

- [ ] **Step 4: Extend `render_compose` to substitute the new placeholders**

In `scripts/lib/render.sh`, update `render_compose`:

```bash
render_compose() {
    local tmpl="${1:?}" out="${2:?}"
    [[ -f "$tmpl" ]] || die "template not found: $tmpl"
    sed \
        -e "s|__JUPYTER_IMAGE__|${JUPYTER_IMAGE:?}|g" \
        -e "s|__JUPYTER_PASSWORD_HASH__|${JUPYTER_PASSWORD_HASH:?}|g" \
        -e "s|__CHISEL_IMAGE__|${CHISEL_IMAGE:?}|g" \
        -e "s|__CHISEL_LISTEN_PORT__|${CHISEL_LISTEN_PORT:?}|g" \
        -e "s|__NOTEBOOKS_PATH__|${VPS_NOTEBOOKS_PATH:?}|g" \
        -e "s|__LOKI_IMAGE__|${LOKI_IMAGE:?}|g" \
        -e "s|__GRAFANA_IMAGE__|${GRAFANA_IMAGE:?}|g" \
        -e "s|__VPS_HOST__|${VPS_HOST:?}|g" \
        "$tmpl" > "$out"
}
```

- [ ] **Step 5: Run tests, verify they pass**

Run: `bats tests/test_render.bats`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add compose/docker-compose.yml.tmpl scripts/lib/render.sh tests/test_render.bats
git commit -m "feat(compose): add loki and grafana services to render pipeline"
```

---

## Task 3: Add /grafana/ subpath route to Caddyfile

**Files:**
- Modify: `compose/Caddyfile.tmpl`
- Modify: `tests/test_render.bats`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_render.bats`:

```bash
@test "render_caddyfile: routes /grafana/* to grafana:3000 and falls through to jupyter" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/fixtures/valid_config.yaml
        render_caddyfile $ROOT/compose/Caddyfile.tmpl $TMPDIR/Caddyfile
        cat $TMPDIR/Caddyfile
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"handle_path /grafana/*"* ]]
    [[ "$output" == *"reverse_proxy grafana:3000"* ]]
    [[ "$output" == *"reverse_proxy jupyter:8888"* ]]
}
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `bats tests/test_render.bats`
Expected: new case fails.

- [ ] **Step 3: Update the Caddyfile template**

Replace the inner block in `compose/Caddyfile.tmpl` so it reads:

```caddy
{
    email __ACME_EMAIL__
    # Modern TLS clients (curl, OpenSSL) do not send SNI when the URL is an IP
    # literal (RFC 6066 forbids IP in SNI). Without this, Caddy returns
    # tlsv1 internal_error to clients with no SNI, including our own healthcheck.
    default_sni __VPS_HOST__
}

https://__VPS_HOST__ {
    tls {
        # Email comes from the global `email` directive above.
        issuer acme {
            profile shortlived
        }
    }

    # /grafana/* is handled exclusively (handle_path strips the prefix) so the
    # default reverse_proxy below only sees notebook traffic.
    handle_path /grafana/* {
        reverse_proxy grafana:3000
    }

    # Auth is handled by JupyterLab itself (cookie-based), not at the edge.
    # Reason: HTTP Basic Auth on mobile browsers re-prompts on every WebSocket
    # upgrade, breaking notebook kernels. JupyterLab's password identity
    # provider uses cookies and works reliably on mobile.
    reverse_proxy jupyter:8888
}
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `bats tests/test_render.bats`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add compose/Caddyfile.tmpl tests/test_render.bats
git commit -m "feat(caddy): route /grafana/* to grafana:3000 subpath"
```

---

## Task 4: Append loki:3100 to chisel users allow-list

**Files:**
- Modify: `scripts/lib/render.sh`
- Modify: `compose/chisel-users.json.tmpl`
- Modify: `tests/test_render.bats`

- [ ] **Step 1: Write the failing test**

Update the existing chisel users test in `tests/test_render.bats` and add a new one:

```bash
@test "render_chisel_users: emits one entry per chisel_clients with R: and loki:3100" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/fixtures/valid_config.yaml
        render_chisel_users $TMPDIR/users.json
        cat $TMPDIR/users.json
    "
    [ "$status" -eq 0 ]
    echo "$output" | yq -p json e '.' >/dev/null
    [[ "$output" == *'"microscope-1:k7HfLpNqRsT3uVwX1yZ2aB3cD4eF5gH6"'* ]]
    [[ "$output" == *'R:0.0.0.0:9001'* ]]
    [[ "$output" == *'loki:3100'* ]]
}

@test "render_chisel_users: each user gets exactly two allow-list entries" {
    bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/fixtures/valid_config.yaml
        render_chisel_users $TMPDIR/users.json
    "
    run yq -p json e '."microscope-1:k7HfLpNqRsT3uVwX1yZ2aB3cD4eF5gH6" | length' "$TMPDIR/users.json"
    [ "$status" -eq 0 ]
    [[ "$output" == "2" ]]
}
```

The original "emits one entry per chisel_clients with route restriction" test is replaced; remove it.

- [ ] **Step 2: Run tests, verify they fail**

Run: `bats tests/test_render.bats`
Expected: the two new cases fail (current output only has the `R:` entry).

- [ ] **Step 3: Extend `render_chisel_users`**

In `scripts/lib/render.sh`, replace `render_chisel_users` with:

```bash
# render_chisel_users <output_path>
# Builds the chisel users.json from .chisel_clients in CONFIG_PATH.
# Each user is allow-listed for both their reverse port (R:0.0.0.0:<port>)
# and the in-network Loki push endpoint (loki:3100). The forward path lets
# the client tunnel its log stream to Loki without exposing Loki publicly.
render_chisel_users() {
    local out="${1:?}"
    yq -o=json e '
        .chisel_clients
        | map({(.name + ":" + .password): ["R:0.0.0.0:" + (.reverse_port | tostring), "loki:3100"]})
        | (. // [{}])
        | .[] as $item ireduce ({}; . * $item)
    ' "${CONFIG_PATH:?}" > "$out"
}
```

- [ ] **Step 4: Update the template's documentation comment**

In `compose/chisel-users.json.tmpl`, replace the comment:

```jsonc
// This file is rendered programmatically by render_chisel_users in
// scripts/lib/render.sh — there is no in-place placeholder substitution.
// Output shape:
// {
//   "<name>:<password>": [
//     "R:0.0.0.0:<reverse_port>",   // device's reverse tunnel
//     "loki:3100"                   // forward tunnel to internal Loki
//   ],
//   ...
// }
```

- [ ] **Step 5: Run tests, verify they pass**

Run: `bats tests/test_render.bats`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/lib/render.sh compose/chisel-users.json.tmpl tests/test_render.bats
git commit -m "feat(chisel): authorize loki:3100 forward tunnel for every client"
```

---

## Task 5: Render Loki config from a template

**Files:**
- Create: `compose/loki/config.yaml.tmpl`
- Modify: `scripts/lib/render.sh`
- Modify: `tests/test_render.bats`

- [ ] **Step 1: Write the Loki config template**

Create `compose/loki/config.yaml.tmpl`:

```yaml
auth_enabled: false

server:
  http_listen_port: 3100
  grpc_listen_port: 9095
  log_level: warn

common:
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory

schema_config:
  configs:
    - from: 2026-01-01
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

limits_config:
  retention_period: __LOKI_RETENTION_HOURS__h
  reject_old_samples: true
  reject_old_samples_max_age: 168h
  ingestion_rate_mb: 4
  ingestion_burst_size_mb: 8
  max_label_name_length: 128
  max_label_value_length: 1024
  max_label_names_per_series: 15

compactor:
  working_directory: /loki/compactor
  retention_enabled: true
  retention_delete_delay: 2h
  delete_request_store: filesystem

ruler:
  storage:
    type: local
    local:
      directory: /loki/rules
```

- [ ] **Step 2: Write the failing test**

Append to `tests/test_render.bats`:

```bash
@test "render_loki_config: substitutes retention hours (days * 24)" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/fixtures/valid_config.yaml
        render_loki_config $ROOT/compose/loki/config.yaml.tmpl $TMPDIR/loki.yaml
        cat $TMPDIR/loki.yaml
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"retention_period: 720h"* ]]
    [[ "$output" != *"__"*"__"* ]]
}

@test "render_loki_config: parses as valid YAML with the expected schema" {
    bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/fixtures/valid_config.yaml
        render_loki_config $ROOT/compose/loki/config.yaml.tmpl $TMPDIR/loki.yaml
    "
    run yq e '.compactor.retention_enabled' "$TMPDIR/loki.yaml"
    [ "$status" -eq 0 ]
    [[ "$output" == "true" ]]
    run yq e '.schema_config.configs[0].schema' "$TMPDIR/loki.yaml"
    [[ "$output" == "v13" ]]
}
```

- [ ] **Step 3: Run tests, verify they fail**

Run: `bats tests/test_render.bats`
Expected: the new tests fail (`render_loki_config` not defined).

- [ ] **Step 4: Add `render_loki_config` to `scripts/lib/render.sh`**

Append:

```bash
# render_loki_config <template_path> <output_path>
# Substitutes __LOKI_RETENTION_HOURS__ (computed from LOKI_RETENTION_DAYS).
render_loki_config() {
    local tmpl="${1:?}" out="${2:?}"
    [[ -f "$tmpl" ]] || die "template not found: $tmpl"
    local hours=$(( ${LOKI_RETENTION_DAYS:?} * 24 ))
    sed -e "s|__LOKI_RETENTION_HOURS__|${hours}|g" "$tmpl" > "$out"
}
```

- [ ] **Step 5: Run tests, verify they pass**

Run: `bats tests/test_render.bats`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add compose/loki/config.yaml.tmpl scripts/lib/render.sh tests/test_render.bats
git commit -m "feat(loki): add filesystem-backed config template with retention substitution"
```

---

## Task 6: Add static Grafana provisioning files

**Files:**
- Create: `compose/grafana/provisioning/datasources/loki.yaml`
- Create: `compose/grafana/provisioning/dashboards/lab-bridge.yaml`
- Create: `compose/grafana/provisioning/dashboards/client-logs.json`
- Create: `tests/test_grafana_provisioning.bats`

- [ ] **Step 1: Create the datasource provisioning file**

`compose/grafana/provisioning/datasources/loki.yaml`:

```yaml
apiVersion: 1
datasources:
  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    isDefault: true
    editable: false
```

- [ ] **Step 2: Create the dashboard provider config**

`compose/grafana/provisioning/dashboards/lab-bridge.yaml`:

```yaml
apiVersion: 1
providers:
  - name: lab-bridge
    folder: ''
    type: file
    disableDeletion: true
    editable: false
    updateIntervalSeconds: 30
    options:
      path: /etc/grafana/provisioning/dashboards
```

- [ ] **Step 3: Create the bundled dashboard**

`compose/grafana/provisioning/dashboards/client-logs.json`:

```json
{
  "annotations": {
    "list": []
  },
  "editable": false,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 0,
  "id": null,
  "links": [],
  "liveNow": true,
  "panels": [
    {
      "type": "logs",
      "title": "Live tail",
      "datasource": { "type": "loki", "uid": "loki" },
      "gridPos": { "h": 14, "w": 24, "x": 0, "y": 0 },
      "options": {
        "showTime": true,
        "wrapLogMessage": true,
        "enableLogDetails": true,
        "sortOrder": "Descending",
        "dedupStrategy": "none"
      },
      "targets": [
        {
          "expr": "{client=~\"$client\", stream=~\"$stream\", version=~\"$version\"}",
          "refId": "A",
          "queryType": "range",
          "maxLines": 1000
        }
      ]
    },
    {
      "type": "timeseries",
      "title": "Log volume by client",
      "datasource": { "type": "loki", "uid": "loki" },
      "gridPos": { "h": 8, "w": 12, "x": 0, "y": 14 },
      "targets": [
        {
          "expr": "sum by (client) (rate({client=~\".+\"}[5m]))",
          "refId": "A",
          "legendFormat": "{{client}}"
        }
      ]
    },
    {
      "type": "logs",
      "title": "Errors",
      "datasource": { "type": "loki", "uid": "loki" },
      "gridPos": { "h": 8, "w": 12, "x": 12, "y": 14 },
      "options": {
        "showTime": true,
        "wrapLogMessage": true,
        "sortOrder": "Descending"
      },
      "targets": [
        {
          "expr": "{client=~\"$client\"} |= \"ERROR\"",
          "refId": "A",
          "queryType": "range",
          "maxLines": 500
        }
      ]
    },
    {
      "type": "table",
      "title": "Current versions",
      "datasource": { "type": "loki", "uid": "loki" },
      "gridPos": { "h": 8, "w": 24, "x": 0, "y": 22 },
      "targets": [
        {
          "expr": "topk(1, max by (client, version) (max_over_time({client=~\".+\"}[1h])))",
          "refId": "A",
          "queryType": "instant"
        }
      ]
    }
  ],
  "refresh": "10s",
  "schemaVersion": 39,
  "style": "dark",
  "tags": ["lab-bridge", "logs"],
  "templating": {
    "list": [
      {
        "name": "client",
        "label": "Client",
        "type": "query",
        "datasource": { "type": "loki", "uid": "loki" },
        "definition": "label_values(client)",
        "query": { "type": 1, "label": "client", "stream": "" },
        "includeAll": true,
        "multi": true,
        "current": { "selected": true, "text": "All", "value": "$__all" },
        "refresh": 2
      },
      {
        "name": "stream",
        "label": "Stream",
        "type": "custom",
        "query": "stdout,stderr",
        "includeAll": true,
        "multi": true,
        "current": { "selected": true, "text": "All", "value": "$__all" },
        "options": [
          { "selected": false, "text": "stdout", "value": "stdout" },
          { "selected": false, "text": "stderr", "value": "stderr" }
        ]
      },
      {
        "name": "version",
        "label": "Version",
        "type": "query",
        "datasource": { "type": "loki", "uid": "loki" },
        "definition": "label_values(version)",
        "query": { "type": 1, "label": "version", "stream": "" },
        "includeAll": true,
        "multi": true,
        "current": { "selected": true, "text": "All", "value": "$__all" },
        "refresh": 2
      }
    ]
  },
  "time": { "from": "now-1h", "to": "now" },
  "timepicker": {},
  "timezone": "",
  "title": "Lab client logs",
  "uid": "lab-bridge-client-logs",
  "version": 1,
  "weekStart": ""
}
```

- [ ] **Step 4: Write a sanity test**

Create `tests/test_grafana_provisioning.bats`:

```bash
#!/usr/bin/env bats

load helpers

@test "grafana datasource yaml is valid YAML and points to loki:3100" {
    run yq e '.datasources[0].url' "$ROOT/compose/grafana/provisioning/datasources/loki.yaml"
    [ "$status" -eq 0 ]
    [[ "$output" == "http://loki:3100" ]]
}

@test "grafana dashboard provider yaml is valid and read-only" {
    run yq e '.providers[0].editable' "$ROOT/compose/grafana/provisioning/dashboards/lab-bridge.yaml"
    [ "$status" -eq 0 ]
    [[ "$output" == "false" ]]
}

@test "grafana dashboard json is valid JSON with the four expected panels" {
    run yq -p json e '.title' "$ROOT/compose/grafana/provisioning/dashboards/client-logs.json"
    [ "$status" -eq 0 ]
    [[ "$output" == "Lab client logs" ]]
    run yq -p json e '.panels | length' "$ROOT/compose/grafana/provisioning/dashboards/client-logs.json"
    [[ "$output" == "4" ]]
    run yq -p json e '.panels | map(.title) | join(",")' "$ROOT/compose/grafana/provisioning/dashboards/client-logs.json"
    [[ "$output" == *"Live tail"* ]]
    [[ "$output" == *"Log volume by client"* ]]
    [[ "$output" == *"Errors"* ]]
    [[ "$output" == *"Current versions"* ]]
    run yq -p json e '.templating.list | map(.name) | join(",")' "$ROOT/compose/grafana/provisioning/dashboards/client-logs.json"
    [[ "$output" == *"client"* ]]
    [[ "$output" == *"stream"* ]]
    [[ "$output" == *"version"* ]]
}
```

- [ ] **Step 5: Run tests, verify they pass**

Run: `bats tests/test_grafana_provisioning.bats`
Expected: all three tests pass.

- [ ] **Step 6: Commit**

```bash
git add compose/grafana/provisioning tests/test_grafana_provisioning.bats
git commit -m "feat(grafana): provision Loki datasource and Lab client logs dashboard"
```

---

## Task 7: Add `secrets:set-grafana-password` task

**Files:**
- Modify: `scripts/secrets.sh`
- Modify: `Taskfile.yml`
- Modify: `.gitignore`
- Modify: `tests/test_secrets.bats`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_secrets.bats`:

```bash
@test "secrets set-grafana-password: writes plaintext to compose/grafana/admin_password mode 0600" {
    export LDS_GRAFANA_PASSWORD_FILE="$TMPDIR/admin_password"
    run bash -c "echo -e 'g00d-pw\ng00d-pw' | $ROOT/scripts/secrets.sh set-grafana-password"
    [ "$status" -eq 0 ]
    [[ -f "$LDS_GRAFANA_PASSWORD_FILE" ]]
    [[ "$(cat "$LDS_GRAFANA_PASSWORD_FILE")" == "g00d-pw" ]]
    perms="$(stat -c '%a' "$LDS_GRAFANA_PASSWORD_FILE" 2>/dev/null || stat -f '%Lp' "$LDS_GRAFANA_PASSWORD_FILE")"
    [[ "$perms" == "600" ]]
}

@test "secrets set-grafana-password: refuses mismatched confirmation" {
    export LDS_GRAFANA_PASSWORD_FILE="$TMPDIR/admin_password"
    run bash -c "echo -e 'one\ntwo' | $ROOT/scripts/secrets.sh set-grafana-password"
    [ "$status" -ne 0 ]
    [[ "$output" == *"match"* ]] || [[ "$output" == *"mismatch"* ]]
}

@test "secrets set-grafana-password: refuses empty password" {
    export LDS_GRAFANA_PASSWORD_FILE="$TMPDIR/admin_password"
    run bash -c "echo -e '\n' | $ROOT/scripts/secrets.sh set-grafana-password"
    [ "$status" -ne 0 ]
    [[ "$output" == *"empty"* ]]
}
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `bats tests/test_secrets.bats`
Expected: new cases fail (`unknown subcommand: set-grafana-password`).

- [ ] **Step 3: Implement `cmd_set_grafana_password`**

In `scripts/secrets.sh`, add the function and wire it into `main`:

```bash
cmd_set_grafana_password() {
    # Plaintext on disk; matches the existing trust model on the VPS
    # (caddy_data certs and chisel-users.json are already plaintext under compose/).
    local pwfile="${LDS_GRAFANA_PASSWORD_FILE:-$SCRIPT_DIR/../compose/grafana/admin_password}"
    mkdir -p "$(dirname "$pwfile")"

    local pw
    pw="$(prompt_password "Grafana admin password (used to log in to https://<vps-host>/grafana/)")"

    # Atomic write so a partial file never lingers.
    local tmp
    tmp="$(mktemp "${pwfile}.XXXXXX")"
    printf '%s' "$pw" > "$tmp"
    chmod 600 "$tmp"
    mv "$tmp" "$pwfile"
    log "wrote Grafana admin password to $pwfile (deploy to apply)"
}
```

Update the `main` switch:

```bash
        set-jupyter-password) cmd_set_jupyter_password "$@" ;;
        set-grafana-password) cmd_set_grafana_password "$@" ;;
        add-client)           cmd_add_client "$@" ;;
```

- [ ] **Step 4: Wire the Taskfile command**

In `Taskfile.yml`, add under `# --- Secrets ---`:

```yaml
  "secrets:set-grafana-password":
    desc: Set or rotate the Grafana admin password (prompts; deploy to apply)
    cmd: bash scripts/secrets.sh set-grafana-password
```

- [ ] **Step 5: Add the password file to `.gitignore`**

Append to `.gitignore`:

```
compose/grafana/admin_password
```

- [ ] **Step 6: Run tests, verify they pass**

Run: `bats tests/test_secrets.bats`
Expected: all tests pass (including the existing ones).

- [ ] **Step 7: Commit**

```bash
git add scripts/secrets.sh Taskfile.yml .gitignore tests/test_secrets.bats
git commit -m "feat(secrets): add set-grafana-password task"
```

---

## Task 8: Provision data directories for Loki and Grafana

**Files:**
- Modify: `scripts/provision.sh`
- Modify: `tests/test_provision.bats`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_provision.bats`:

```bash
@test "provision: creates loki_data and grafana_data with correct ownership" {
    run bash "$ROOT/scripts/provision.sh"
    [ "$status" -eq 0 ]
    # Loki container runs as uid 10001
    docker exec lds-fake-vps stat -c '%u' /srv/lab-bridge/loki_data | grep -q '^10001$'
    # Grafana container runs as uid 472
    docker exec lds-fake-vps stat -c '%u' /srv/lab-bridge/grafana_data | grep -q '^472$'
}
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `bats tests/test_provision.bats`
Expected: new test fails (directories not created yet).

- [ ] **Step 3: Update `provision.sh`**

In `scripts/provision.sh`, inside the remote heredoc, replace the existing directory-creation block (the "3. Directories." section) with:

```bash
# 3. Directories. JupyterLab containers run as UID 1000 (jovyan).
# Loki and Grafana run as their own non-root UIDs and need to write
# to the bind-mounted state dirs.
sudo mkdir -p \
    "$REMOTE_ROOT" \
    "$REMOTE_ROOT/chisel" \
    "$REMOTE_ROOT/caddy_data" \
    "$REMOTE_ROOT/loki_data" \
    "$REMOTE_ROOT/grafana_data" \
    "$NOTEBOOKS_PATH"
sudo chown -R "$USER:$USER" "$REMOTE_ROOT"
sudo chown -R 1000:100 "$NOTEBOOKS_PATH"
sudo chmod 775 "$NOTEBOOKS_PATH"
# Loki uses 10001 (grafana/loki image's "loki" user).
sudo chown -R 10001:10001 "$REMOTE_ROOT/loki_data"
# Grafana uses 472 ("grafana" user in grafana/grafana).
sudo chown -R 472:472   "$REMOTE_ROOT/grafana_data"
log "ok"
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `bats tests/test_provision.bats`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/provision.sh tests/test_provision.bats
git commit -m "feat(provision): create loki_data and grafana_data with correct uids"
```

---

## Task 9: Stage Loki + Grafana files in deploy.sh

**Files:**
- Modify: `scripts/deploy.sh`
- Modify: `tests/test_deploy.bats`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_deploy.bats`:

```bash
@test "deploy: stages loki config, grafana provisioning, and admin_password" {
    # Pre-create the grafana admin password file (secrets:set-grafana-password
    # output, simulated to keep the test hermetic).
    export LDS_GRAFANA_PASSWORD_FILE="$TMPDIR/admin_password"
    printf 'testpw' > "$LDS_GRAFANA_PASSWORD_FILE"
    chmod 600 "$LDS_GRAFANA_PASSWORD_FILE"

    run bash "$ROOT/scripts/deploy.sh"
    [ "$status" -eq 0 ]
    docker exec lds-fake-vps test -f /srv/lab-bridge/loki/config.yaml
    docker exec lds-fake-vps test -f /srv/lab-bridge/grafana/admin_password
    docker exec lds-fake-vps test -f /srv/lab-bridge/grafana/provisioning/datasources/loki.yaml
    docker exec lds-fake-vps test -f /srv/lab-bridge/grafana/provisioning/dashboards/lab-bridge.yaml
    docker exec lds-fake-vps test -f /srv/lab-bridge/grafana/provisioning/dashboards/client-logs.json
    # rendered loki config substitutes retention hours
    run docker exec lds-fake-vps grep -F 'retention_period: 720h' /srv/lab-bridge/loki/config.yaml
    [ "$status" -eq 0 ]
}

@test "deploy: rsync --delete preserves loki_data and grafana_data" {
    export LDS_GRAFANA_PASSWORD_FILE="$TMPDIR/admin_password"
    printf 'testpw' > "$LDS_GRAFANA_PASSWORD_FILE"
    chmod 600 "$LDS_GRAFANA_PASSWORD_FILE"

    bash "$ROOT/scripts/deploy.sh"
    docker exec lds-fake-vps bash -c 'sudo mkdir -p /srv/lab-bridge/loki_data /srv/lab-bridge/grafana_data'
    docker exec lds-fake-vps bash -c 'echo loki-marker | sudo tee /srv/lab-bridge/loki_data/marker > /dev/null'
    docker exec lds-fake-vps bash -c 'echo grafana-marker | sudo tee /srv/lab-bridge/grafana_data/marker > /dev/null'
    bash "$ROOT/scripts/deploy.sh"
    docker exec lds-fake-vps test -f /srv/lab-bridge/loki_data/marker
    docker exec lds-fake-vps test -f /srv/lab-bridge/grafana_data/marker
}

@test "deploy: fails fast when grafana admin_password is missing" {
    export LDS_GRAFANA_PASSWORD_FILE="$TMPDIR/does-not-exist"
    run bash "$ROOT/scripts/deploy.sh"
    [ "$status" -ne 0 ]
    [[ "$output" == *"set-grafana-password"* ]] || [[ "$output" == *"admin_password"* ]]
}
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `bats tests/test_deploy.bats`
Expected: new tests fail (deploy.sh does not stage the new files yet).

- [ ] **Step 3: Update `scripts/deploy.sh` to stage the new files**

Replace the body of `main()` after the "render templates" log line and before the "Build SSH/rsync" section with:

```bash
    log "rendering templates..."
    mkdir -p "$stage/chisel" "$stage/loki" "$stage/grafana/provisioning"
    render_compose      "$REPO_ROOT/compose/docker-compose.yml.tmpl" "$stage/docker-compose.yml"
    render_caddyfile    "$REPO_ROOT/compose/Caddyfile.tmpl"          "$stage/Caddyfile"
    render_chisel_users "$stage/chisel/users.json"
    render_loki_config  "$REPO_ROOT/compose/loki/config.yaml.tmpl"   "$stage/loki/config.yaml"

    # Static Grafana provisioning — datasource + dashboard provider + dashboard JSON.
    cp -R "$REPO_ROOT/compose/grafana/provisioning/." "$stage/grafana/provisioning/"

    # Grafana admin password file (created by `task secrets:set-grafana-password`).
    local pwfile="${LDS_GRAFANA_PASSWORD_FILE:-$REPO_ROOT/compose/grafana/admin_password}"
    [[ -f "$pwfile" ]] || die "grafana admin password not found at $pwfile — run: task secrets:set-grafana-password"
    install -m 600 "$pwfile" "$stage/grafana/admin_password"
```

In the rsync command, add the new excludes:

```bash
    rsync -az --delete \
        --exclude='caddy_data/' \
        --exclude='caddy_config/' \
        --exclude='loki_data/' \
        --exclude='grafana_data/' \
        -e "$rsync_e" \
        "$stage/" "$target:$VPS_REMOTE_ROOT/"
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `bats tests/test_deploy.bats`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/deploy.sh tests/test_deploy.bats
git commit -m "feat(deploy): stage loki config, grafana provisioning, admin password"
```

---

## Task 10: Add ops commands for Loki/Grafana logs and disk

**Files:**
- Modify: `scripts/ops.sh`
- Modify: `Taskfile.yml`
- Modify: `tests/test_ops.bats`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ops.bats`:

```bash
@test "ops logs:loki: returns success and shows recent log lines" {
    run bash "$ROOT/scripts/ops.sh" logs:loki
    [ "$status" -eq 0 ]
}

@test "ops logs:grafana: returns success" {
    run bash "$ROOT/scripts/ops.sh" logs:grafana
    [ "$status" -eq 0 ]
}

@test "ops loki-disk: prints loki_data size and configured retention" {
    run bash "$ROOT/scripts/ops.sh" loki-disk
    [ "$status" -eq 0 ]
    [[ "$output" == *"loki_data"* ]]
    [[ "$output" == *"retention"* ]] || [[ "$output" == *"30"* ]]
}
```

The test setup file (existing `setup()`) needs `LDS_GRAFANA_PASSWORD_FILE` set so the deploy step succeeds. Update `setup()` to include:

```bash
    export LDS_GRAFANA_PASSWORD_FILE="$TMPDIR/admin_password"
    printf 'testpw' > "$LDS_GRAFANA_PASSWORD_FILE"
    chmod 600 "$LDS_GRAFANA_PASSWORD_FILE"
```

(insert after the existing `LDS_SKIP_HEALTHCHECK=1` line, before the `bash "$ROOT/scripts/provision.sh"` line.)

- [ ] **Step 2: Run tests, verify they fail**

Run: `bats tests/test_ops.bats`
Expected: the three new tests fail (`unknown subcommand: logs:loki`).

- [ ] **Step 3: Add ops subcommands**

In `scripts/ops.sh`, add the new functions:

```bash
cmd_logs_loki()    { load_config "$CONFIG"; remote_compose "logs --tail=200 loki"; }
cmd_logs_grafana() { load_config "$CONFIG"; remote_compose "logs --tail=200 grafana"; }

cmd_loki_disk() {
    load_config "$CONFIG"
    local ssh_base
    ssh_base="$(build_ssh)"
    # du -sh on the VPS, then echo the configured retention so the operator
    # has both numbers in one place.
    $ssh_base "$VPS_SSH_USER@$VPS_HOST" \
        "du -sh $VPS_REMOTE_ROOT/loki_data 2>/dev/null || echo '0  $VPS_REMOTE_ROOT/loki_data (missing)'"
    log "configured retention: ${LOKI_RETENTION_DAYS} days"
}
```

Update the `main` switch:

```bash
    case "$sub" in
        ps)            cmd_ps ;;
        logs)          cmd_logs "$@" ;;
        logs:loki)     cmd_logs_loki ;;
        logs:grafana)  cmd_logs_grafana ;;
        loki-disk)     cmd_loki_disk ;;
        ssh)           cmd_ssh ;;
        restart)       cmd_restart ;;
        down)          cmd_down ;;
        destroy)       cmd_destroy ;;
        backup)        cmd_backup ;;
        *) die "unknown subcommand: $sub" ;;
    esac
```

- [ ] **Step 4: Wire Taskfile entries**

In `Taskfile.yml`, under `# --- Operations ---`, add:

```yaml
  "ops:logs:loki":
    desc: Tail recent loki container logs
    cmd: bash scripts/ops.sh logs:loki
  "ops:logs:grafana":
    desc: Tail recent grafana container logs
    cmd: bash scripts/ops.sh logs:grafana
  "ops:loki-disk":
    desc: Show loki_data disk usage and configured retention
    cmd: bash scripts/ops.sh loki-disk
```

- [ ] **Step 5: Run tests, verify they pass**

Run: `bats tests/test_ops.bats`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/ops.sh Taskfile.yml tests/test_ops.bats
git commit -m "feat(ops): add logs:loki, logs:grafana, loki-disk commands"
```

---

## Task 11: Integration check — Loki + Grafana come up on the fake VPS

**Files:**
- Modify: `tests/test_deploy.bats`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_deploy.bats`:

```bash
@test "deploy: loki and grafana come up healthy on the fake VPS" {
    export LDS_GRAFANA_PASSWORD_FILE="$TMPDIR/admin_password"
    printf 'testpw' > "$LDS_GRAFANA_PASSWORD_FILE"
    chmod 600 "$LDS_GRAFANA_PASSWORD_FILE"

    run bash "$ROOT/scripts/deploy.sh"
    [ "$status" -eq 0 ]
    # All five compose services should be in `running` state.
    docker exec lds-fake-vps bash -c '
        cd /srv/lab-bridge && docker compose ps --status running --format "{{.Service}}"
    ' | sort | tr -d "\r" | grep -E "^(caddy|jupyter|chisel|loki|grafana)$" | wc -l | tr -d "[:space:]" | grep -q "^5$"

    # Loki readiness: poll for up to 60 s. wget exits 0 when /ready returns 200.
    local i
    for i in $(seq 1 60); do
        if docker exec lds-fake-vps bash -c '
            cd /srv/lab-bridge && docker compose exec -T loki wget -q -O - http://localhost:3100/ready
        ' >/dev/null 2>&1; then
            break
        fi
        sleep 1
    done
    docker exec lds-fake-vps bash -c '
        cd /srv/lab-bridge && docker compose exec -T loki wget -q -O - http://localhost:3100/ready
    ' >/dev/null
}
```

- [ ] **Step 2: Run the test, verify it fails on a clean tree before wiring**

(If running this task in isolation; if Tasks 2/5/6/9 are already in, the test should pass immediately.)

Run: `bats tests/test_deploy.bats -f "loki and grafana come up healthy"`
Expected: PASS once Tasks 2, 5, 6, and 9 are wired together.

- [ ] **Step 3: Commit**

```bash
git add tests/test_deploy.bats
git commit -m "test(deploy): assert loki and grafana come up healthy"
```

---

## Task 12: Documentation — README updates

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the Quick start section**

In `README.md`, update the Quick start code block to include the Grafana password step:

```bash
task doctor                                   # check local prerequisites
cp config.example.yaml config.yaml            # then edit with your VPS details
task secrets:set-jupyter-password             # set the shared JupyterLab password
task secrets:set-grafana-password             # set the Grafana admin password
task secrets:add-client -- microscope-1 9001  # add a lab device
task provision                                # first-time VPS setup
task deploy                                   # render configs + bring up stack
```

- [ ] **Step 2: Add a "Lab client logs" section**

After the existing JupyterLab paragraph, append:

```markdown
## Lab client logs

Chisel clients push their stdout/stderr through the existing tunnel into an
internal Loki, queryable in Grafana at `https://<vps-ip>/grafana/`. Log in
with `admin` / the password set via `task secrets:set-grafana-password`. The
"Lab client logs" dashboard is provisioned automatically: live tail, log
volume by client, errors, and current versions per client.

Operations:

- `task ops:logs:loki` / `task ops:logs:grafana` — tail container stderr
- `task ops:loki-disk` — show `loki_data/` size and the configured retention
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document grafana password setup and Lab client logs dashboard"
```

---

## Self-review notes

- **Spec coverage**: every section in `docs/superpowers/specs/2026-04-28-chisel-client-logs-design.md` is implemented:
  - "Server-side changes" → Tasks 2, 3, 4, 8.
  - "Loki configuration" → Task 5.
  - "Grafana provisioning" → Task 6.
  - "Operator interface" → Tasks 1, 7, 10, 12.
  - "Push protocol / Identity" → contract is described in the spec (client-side) and enforced server-side by chisel auth (Task 4) and Loki ingestion limits (Task 5).
  - "Failure modes" → covered indirectly by validation (Task 1), age-based retention (Task 5), `restart: unless-stopped` (Task 2), and `ops:loki-disk` (Task 10).
  - "Testing strategy" → unit tests in Tasks 1, 2, 3, 4, 5, 6, 7; integration tests in Tasks 8, 9, 10, 11.
- **Out-of-scope items** (per spec) are not included: cron disk-check, per-client auth proxy, alerting, multi-user Grafana, client-side implementation.
- **Compose project name**: rsync target is `$VPS_REMOTE_ROOT` (`/srv/lab-bridge` per fixture and `config.yaml`); pre-existing tests that hardcode `/srv/lab_devices_server` are out of scope for this plan.
