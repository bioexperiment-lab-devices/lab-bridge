# VPS metrics: Prometheus + Grafana dashboard stack

**Status:** draft (brainstorming complete; pending implementation plan).

**Supersedes:** [2026-05-18-unified-agent-monitoring-design.md](2026-05-18-unified-agent-monitoring-design.md) — the Yandex Unified Agent path. UA was implemented and merged but never wired to any consumer before this swap. This spec records the rationale.

## Problem

The platform currently has no host-level observability:

- Grafana + Loki cover application logs (chisel client logs, agent fleet logs), but nothing watches the VPS itself.
- We do not know RAM pressure, disk fill, disk I/O saturation, or network bandwidth on the prod VPS until something falls over.
- The chisel server multiplexes long-lived TCP tunnels — TCP connection counts and network bandwidth matter, and we have no view of either.
- Per-container resource use (CPU, RAM, restart counts) is invisible — useful when a single container misbehaves.

The just-merged Yandex Unified Agent approach (PRs #58, #60) satisfied the metrics-collection goal but introduced cloud lock-in: a Yandex-specific config schema, a `cloud_meta` IAM dependency, a `yc.folder_id` plumbing path through `pins.yaml`/`config.yaml`/`render.sh`/`deploy.sh`, conditional-strip rendering for CI, and operator setup steps (SA creation, SA attachment, folder-id wiring). Migrating off Yandex would touch all of those.

A pure-Prometheus stack — node-exporter for host metrics, cAdvisor for per-container metrics, Caddy's built-in `/metrics` endpoint for proxy metrics, JupyterLab's built-in `/metrics` endpoint (best-effort) — collected by a local Prometheus and displayed in the existing Grafana, achieves the same outcome with zero cloud-specific code paths and standard, well-understood components.

## Goals

1. **Surface host + container + proxy health for the prod VPS in Grafana**, covering: CPU, RAM, disk space, disk I/O, network bytes/packets, TCP connection states, kernel counters (host); per-container CPU/RAM/network/restart counts (containers); request rates, 5xx rates, TLS handshake stats (Caddy).
2. **Zero cloud lock-in.** No cloud-specific config schemas, no metadata-service dependencies, no vendor-tied IAM. The stack works identically on AWS / GCP / bare-metal.
3. **Symmetry with the existing Loki path.** Prometheus is a Grafana datasource just like Loki. Dashboards are committed JSON under `compose/grafana/provisioning/dashboards/` just like `client-logs.json`. Operators have one UI (Grafana) for both logs and metrics.
4. **No new secrets.** No new `task secrets:set-*` flow, no new GH secret to dual-manage, no new entry in the laptop/CI sync ledger.
5. **CI deploys exercise the same stack as prod.** The Prometheus stack participates in CI's fake-VPS bring-up without conditional gating. Adds a `metrics-smoke` matrix cell to the platform integration tier so cross-service wiring is asserted on every PR.
6. **Atomic swap.** A single PR removes the Yandex Unified Agent code surface and adds the Prometheus stack, so the platform never sits in an intermediate "two monitoring stacks" or "no monitoring stack" state.

## Non-goals

- **Alerting rules and notification channels.** No alertmanager, no SMTP/Telegram/webhook wiring, no alert rules. The spec stops at "metrics arrive in Prometheus, dashboards render in Grafana." Operator notices problems by looking at dashboards. Alerting is a separate brainstorm with its own design questions (which channel, which secret management story, which rules) and will land in its own spec.
- **Application-level metrics from siteapp and flasher.** Neither exposes a Prometheus endpoint today, and adding one requires service-level code changes. Out of scope. Caddy/cAdvisor coverage already gives proxy-side per-route signals and container-side resource signals for siteapp and flasher's containers.
- **A chisel-aware metrics exporter.** No native `/metrics` endpoint exists on `jpillora/chisel` and no official exporter exists. The chisel-relevant signals — active tunnels, bandwidth, container health — are derivable from node-exporter (TCP connection states on the chisel listen port, network counters) and cAdvisor (chisel container CPU/RAM/network), which v1 already scrapes. A custom chisel sidecar exporter is rejected as overkill for a one-VPS lab.
- **Exposing the Prometheus or cAdvisor UI on the internet.** Both are accessed only via Grafana's datasource path on `labnet`. Ad-hoc PromQL queries go through `docker compose exec` or an SSH tunnel. Same exposure model as Loki today. No Caddy route, no basicauth.
- **Off-VPS metric history.** Prometheus TSDB is local; if the VPS dies, recent history is gone. Same property as Loki today; not a regression from the UA design, which also kept metrics in a remote system not under our control.
- **Multi-VPS.** Single-VPS today. The `external_labels: { host, env }` block in `prometheus.yml` is forward-compat for adding a second instance, but no federation/remote-write is built now.
- **Container-renamed-or-rescheduled stability.** The deploy model is "single VPS, services live for the lifetime of the deploy." Prometheus discovers targets via static DNS names on `labnet`. No service discovery, no relabeling.

## Design

### Component shape

Three new compose services, all on the existing `labnet` bridge, none published to host ports.

```yaml
prometheus:
  image: __PROMETHEUS_IMAGE__
  restart: unless-stopped
  command:
    - --config.file=/etc/prometheus/prometheus.yml
    - --storage.tsdb.path=/prometheus
    - --storage.tsdb.retention.time=__PROMETHEUS_RETENTION_DAYS__d
    - --web.listen-address=:9090
  volumes:
    - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    - ./prometheus_data:/prometheus
  networks: [labnet]

node-exporter:
  image: __NODE_EXPORTER_IMAGE__
  restart: unless-stopped
  command:
    - --path.procfs=/host/proc
    - --path.sysfs=/host/sys
    - --path.rootfs=/host/root
    - --collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($|/)
  volumes:
    - /proc:/host/proc:ro
    - /sys:/host/sys:ro
    - /:/host/root:ro,rslave
  networks: [labnet]

cadvisor:
  image: __CADVISOR_IMAGE__
  restart: unless-stopped
  volumes:
    - /:/rootfs:ro
    - /var/run:/var/run:ro
    - /sys:/sys:ro
    - /var/lib/docker:/var/lib/docker:ro
    - /var/run/docker.sock:/var/run/docker.sock:ro
  networks: [labnet]
```

Notes on placement:

- **`prometheus` is `labnet`-only.** Grafana scrapes it at `http://prometheus:9090` over docker DNS. No published port. No Caddy route.
- **`node-exporter` uses bridge networking (NOT `network_mode: host`).** With `/proc` and `/sys` bind-mounted into `/host/proc` and `/host/sys` and `--path.procfs`/`--path.sysfs` overrides, network counters are read from the host's actual `/proc/net/*`. This keeps node-exporter off the host network namespace and avoids exposing port 9100 directly on the host.
- **`cadvisor` runs unprivileged.** Modern Docker permits cAdvisor to read its required interfaces without `privileged: true`.

One existing-service change:

- **`caddy`**: the Caddyfile gains a single directive `admin :2019` so the admin endpoint (which already serves `/metrics`) binds inside the container on `labnet` rather than the default `localhost:2019` (unreachable). Port stays unpublished; only `prometheus` scrapes it. The custom `lab-bridge-caddy` image is unchanged.

### Scrape configuration

`compose/prometheus/prometheus.yml.tmpl` (rendered by `render.sh::render_prometheus_config`, only `__VPS_HOST__` is a placeholder):

```yaml
global:
  scrape_interval: 15s
  scrape_timeout: 10s
  external_labels:
    host: __VPS_HOST__
    env: prod

scrape_configs:
  - job_name: prometheus
    static_configs: [{ targets: ['prometheus:9090'] }]
  - job_name: node-exporter
    static_configs: [{ targets: ['node-exporter:9100'] }]
  - job_name: cadvisor
    static_configs: [{ targets: ['cadvisor:8080'] }]
  - job_name: caddy
    static_configs: [{ targets: ['caddy:2019'] }]
  - job_name: jupyter
    metrics_path: /jupyter/metrics
    static_configs: [{ targets: ['jupyter:8888'] }]
```

Scrape interval is 15s — granular enough to catch incidents, infrequent enough to keep series counts low. `external_labels: { host, env }` apply to series after they leave Prometheus (remote-write / alerting / federation). For one-VPS local Grafana queries they are decorative; kept for forward-compat with a future second VPS.

**JupyterLab fallback.** `jupyter_server` exposes `/metrics` natively, but the `quay.io/jupyter/scipy-notebook` image may require an additional config flag or auth on that endpoint. The planning step verifies behavior on the pinned tag (`2026-04-20`). If `/jupyter/metrics` is not reachable unauth'd over `labnet`, the jupyter job is **omitted from v1's `prometheus.yml.tmpl`** and the `metrics-smoke` test does not assert it. JupyterLab metrics become a follow-up. This fallback is documented in the PR body so the omission is intentional and traceable.

### Grafana wiring

`compose/grafana/provisioning/datasources/prometheus.yaml` — new file, sibling of `loki.yaml`, no placeholders:

```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    uid: prometheus       # stable uid so dashboard JSON references resolve
                          # to this datasource across re-imports (same reason
                          # as loki.yaml's uid: loki — see its comment).
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
```

Prometheus becomes the default Grafana datasource. Two coupled edits make this deterministic:

- The new `prometheus.yaml` declares `isDefault: true`.
- The existing `compose/grafana/provisioning/datasources/loki.yaml` is edited to flip `isDefault: true → false`. Grafana only accepts one default datasource; without this flip both files would set `true` and Grafana would pick arbitrarily.

The existing `client-logs.json` dashboard references Loki via its stable `uid: loki` (the comment in `loki.yaml` calls out this exact reason). It keeps working unchanged after the default flip — `isDefault` only governs which datasource appears in Grafana's UI dropdowns by default, not which one resolves a `uid`-named panel query.

Dashboards (committed JSON under `compose/grafana/provisioning/dashboards/`, picked up automatically by the existing `lab-bridge.yaml` provider config):

- `node-exporter-full.json` — derived from Grafana marketplace ID 1860; covers CPU/RAM/disk/network/IO/load.
- `cadvisor.json` — derived from marketplace ID 19908; per-container resource use.
- `caddy.json` — derived from marketplace ID 20802; request rates, status codes, TLS stats.
- `platform.json` — hand-rolled overview with ~6 panels (CPU%, RAM%, disk%, network bytes/s, top container by CPU, Caddy request rate). The "first look" dashboard.

All four are datasource-templated to `Prometheus`. UIDs are pinned in the JSON so dashboard links don't break across re-imports. Marketplace exports are used as starting points but committed verbatim — any future drift is intentional, lives in git, and is reviewable. Renovate does not manage dashboard JSON; upstream-marketplace drift is a manual refresh, not an automatic one.

### Render-layer changes

`scripts/lib/render.sh`:

- **Add** `render_prometheus_config <template> <output>` — substitutes `__VPS_HOST__` into `compose/prometheus/prometheus.yml.tmpl` → `<remote_root>/prometheus/prometheus.yml`. Mirrors `render_loki_config`.
- **Add** three new placeholders to `render_compose`: `__PROMETHEUS_IMAGE__`, `__NODE_EXPORTER_IMAGE__`, `__CADVISOR_IMAGE__`, plus `__PROMETHEUS_RETENTION_DAYS__` (used in the `prometheus` service's command args). All render unconditionally — no marker-block strip, no `LDS_*` toggle.
- **Remove** the entire `render_unified_agent_config` function (current lines around 164–169+).
- **Remove** the `strip_unified_agent` shell-eval branch in `render_compose` (lines 52–60) and the `eval "$strip_unified_agent"` invocation in the pipe (line 77).

`scripts/lib/config.sh`:

- **Add** reads from `pins.yaml`: `export PROMETHEUS_IMAGE`, `export NODE_EXPORTER_IMAGE`, `export CADVISOR_IMAGE`, `export PROMETHEUS_RETENTION_DAYS`.
- **Remove** `export YC_FOLDER_ID` (line 147) and its comment block at lines 144–146.
- **Remove** `export UNIFIED_AGENT_IMAGE` (line 160).
- **Remove** the `.unified_agent_image` validator entry (line 41).

`scripts/deploy.sh`:

- **Add** one call to `render_prometheus_config` in the staging step, sibling of `render_loki_config`.
- **Remove** the `render_unified_agent_config` call.

### Compose template changes

`compose/docker-compose.yml.tmpl`:

- **Add** the three new service blocks (`prometheus`, `node-exporter`, `cadvisor`) per the "Component shape" section above. Unconditional — no marker-block wrapping.
- **Add** `prometheus` to `grafana.depends_on` (Grafana already depends on Loki at line 68; Prometheus gets the same ordering hint so Grafana finds the datasource on first start). `caddy.depends_on` is unchanged.
- **Remove** the `# >>>unified-agent` / `# <<<unified-agent` marker block (current lines 101–129) in its entirety.

`compose/Caddyfile.tmpl`:

- **Add** the line `admin :2019` at the top of the global options block.

`compose/pins.yaml`:

- **Add**:
  - `prometheus_image: prom/prometheus:<vX.Y.Z>` (exact tag pinned during planning).
  - `node_exporter_image: quay.io/prometheus/node-exporter:<vX.Y.Z>`.
  - `cadvisor_image: gcr.io/cadvisor/cadvisor:<vX.Y.Z>`.
  - `prometheus_retention_days: 30` (mirrors `loki_retention_days`).
- **Remove**:
  - `unified_agent_image: cr.yandex/yc/unified-agent:25.03.80` (lines 12–16, plus the comment block).

`config.example.yaml`:

- **Remove** the `yc.folder_id` example field. No new fields added.

`config.yaml` (laptop, gitignored) and `compose/config.ci.yaml.tmpl`: **no changes.** The Prometheus stack has no instance-specific values or secrets. The vault guard (`LDS_REQUIRE_VAULT=1`) and the `chisel_clients: []` CI assertion are unaffected.

### Compose directory layout

`compose/`:

- **Remove**: `compose/unified-agent/` directory entirely.
- **Add**: `compose/prometheus/prometheus.yml.tmpl`.

`compose/grafana/provisioning/`:

- **Add**: `datasources/prometheus.yaml`, `dashboards/node-exporter-full.json`, `dashboards/cadvisor.json`, `dashboards/caddy.json`, `dashboards/platform.json`.
- **Edit**: `datasources/loki.yaml` — flip `isDefault: true → false`. Required so Grafana resolves `prometheus.yaml`'s `isDefault: true` deterministically.
- No change to `dashboards/lab-bridge.yaml` provider config or `dashboards/client-logs.json`.

### Spec/plan supersession

The Yandex Unified Agent design and plan documents stay in the repo as historical record but are marked superseded:

- `docs/superpowers/specs/2026-05-18-unified-agent-monitoring-design.md` gets a top banner:
  > **Status:** Superseded by [2026-05-18-vps-metrics-design.md](2026-05-18-vps-metrics-design.md). Yandex Unified Agent was implemented but never deployed before being swapped for a pure Prometheus + node-exporter stack to remove cloud lock-in. See the successor spec for rationale.

  The frontmatter `Status:` line at the top of the doc is set to `superseded`.

- `docs/superpowers/plans/2026-05-18-unified-agent-monitoring.md` gets the same banner format.

### Testing

**Render-layer (`cheap` matrix cell in `pr-platform.yml`).** Edits to `tests/integration/test_render.bats`, `tests/integration/test_config.bats`, and `tests/integration/fixtures/valid_pins.yaml`:

- **Drop** the UA-specific assertion branches (the `yc.folder_id set → unified-agent block present` and `yc.folder_id empty → block stripped` branches in `test_render.bats`; the `unified_agent_image` line in `fixtures/valid_pins.yaml`; the matching `test_config.bats` assertions for the `UNIFIED_AGENT_IMAGE` and `YC_FOLDER_ID` env vars).
- **Add** assertions for the new placeholders: `__PROMETHEUS_IMAGE__`, `__NODE_EXPORTER_IMAGE__`, `__CADVISOR_IMAGE__`, `__PROMETHEUS_RETENTION_DAYS__` substituted into rendered compose; `compose/prometheus/prometheus.yml.tmpl` renders to a file with `__VPS_HOST__` populated and `scrape_configs:` containing the four (or five, if jupyter is in) job entries.
- **Add** schema assertions for `pins.yaml`: new pins parse and surface as expected env vars; `unified_agent_image` is no longer expected.

**Platform integration (the bats matrix in `pr-platform.yml`).** Cells `cheap`, `deploy`, `ops`, `provision`, `routes-smoke` exist today; the Prometheus stack participates in `deploy`'s fake-VPS bring-up automatically (three more containers, expected stack-up time delta well under the 25-minute matrix timeout).

**New matrix cell: `metrics-smoke`.** A new bats file `tests/integration/test_metrics_smoke.bats` that:

1. Brings up the full fake-VPS stack. Uses the `compose_images_available` skip pattern (mirror `test_routes_smoke.bats:11-14`) so flaky anonymous Quay.io/Docker Hub pulls don't hard-fail.
2. Polls `prometheus:9090/-/ready` until 200 (bounded retry, ~60s max).
3. Queries `http://localhost:<mapped-prom-port>/api/v1/targets?state=active` and asserts the JSON response contains entries for `node-exporter`, `cadvisor`, `caddy`, `prometheus` jobs.
4. Asserts each of those targets reports `health == "up"`.
5. If the planning step confirms `/jupyter/metrics` works unauth'd on the pinned image, the jupyter job is also asserted in the test. Otherwise the jupyter job is absent from `prometheus.yml.tmpl` and not asserted.

Added as a new cell to the `.github/workflows/pr-platform.yml` bats matrix. Branch protection's required check stays the `platform` aggregator job; individual matrix cells are not individually required (same pattern as the existing five cells).

**No per-service workflow.** The Prometheus stack is platform infrastructure under `compose/`, not a service under `services/<name>/`. No `pr-prometheus.yml` is created. The `pr-platform.yml` matrix is the appropriate test surface.

**Out-of-scope for tests:**

- Specific metric values (`up == 1` is enough; the contents of each scraper's series are that scraper's job).
- Dashboard rendering (Grafana renders at runtime; invalid JSON logs an error but doesn't crash, and rendering is a UI concern, not a wiring concern).
- Retention behavior (30d in 25min is not testable).

### Rollout

1. Spec lands at `docs/superpowers/specs/2026-05-18-vps-metrics-design.md` (this document) and is committed.
2. Implementation plan lands at `docs/superpowers/plans/2026-05-18-vps-metrics.md` via the `writing-plans` skill (next step after spec approval).
3. Single implementation PR (Approach 1 — atomic swap). Conventional Commits title: `feat(platform): swap host monitoring from Yandex Unified Agent to Prometheus + Grafana stack`. Approximate diff: +500 / −280.
4. PR runs full `pr-platform.yml` matrix including the new `metrics-smoke` cell. `pr-siteapp` and `pr-flasher` fast-skip via paths-filter (no `services/` touch). Required check `pr-platform / platform` must pass.
5. Squash-merge → release-please proposes the next minor (`0.10.0` from current `0.9.0`, since the PR is `feat:`).
6. Release PR runs full CI again — the integration test gate before production deploy.
7. Release PR merge → CI deploys to fake-VPS via `release-build.yml`'s stack-only flow (`LDS_STACK_ONLY=1`), unchanged.
8. Operator runs `task deploy` from the laptop to push to prod VPS.

### Post-deploy verification

Manual, documented in the PR body so the reviewer and the deploying operator have a shared checklist:

- `task remote:status` (or current ops equivalent) — all containers report `Up`.
- Browse `https://<vps>/grafana/` → confirm the Prometheus datasource appears under Connections → Data sources → "Test" returns success → open the `platform.json` dashboard → confirm panels render with non-empty data.
- SSH to VPS: `docker compose exec prometheus wget -qO- localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job, health}'` — every target reports `health: "up"` (subject to the jupyter fallback).

### Backout

Revert the squash commit. release-please cuts a revert release; CI deploys roll back the stack-only changes. No data migration concerns:

- Prometheus TSDB lives in a docker volume created by the deploy; reverting removes the service and the volume goes away.
- UA had no consumer wired (Yandex Monitoring dashboards were never set up by an operator), so nothing depends on UA's continued operation.

### Cloud portability

The lock-in introduced by this stack is zero. Every component (Prometheus, node-exporter, cAdvisor) is vendor-neutral and runs identically on AWS, GCP, or bare-metal. Moving the platform off Yandex Cloud touches no part of the metrics stack.

The Yandex Cloud service account stays attached to the prod VM (intentionally out of scope for this PR — it's a Yandex-side click, not a repo change). It's now unused by this stack but useful for future things (object storage, Cloud Logging). Removal is an operational follow-up.

### Known caveats

Called out explicitly in the implementation PR body so reviewers and future-readers can see what was knowingly accepted:

1. **JupyterLab `/metrics` fallback.** Described above. If `/jupyter/metrics` requires auth on the pinned image, jupyter is silently absent from v1 scrape config. Tracked as a follow-up.
2. **Caddy admin API exposure on `labnet`.** With `admin :2019`, Caddy's admin API becomes reachable from any container on `labnet`. The admin API can reload Caddy's running config; any compromised container on `labnet` could in principle push a new Caddyfile. Mitigation for a one-VPS lab: `labnet` contains only stack services we control; no untrusted code runs there. Same trust model already accepted for Loki and Grafana inter-service traffic. If `labnet` ever hosts untrusted workloads, revisit by either placing the admin endpoint on a separate internal network or using Caddy's `admin.origins` restriction.
3. **No off-VPS metric history.** Prometheus TSDB is local; if the VPS dies, recent history is gone. Same property as Loki today. Not a regression from the UA design (which also stored history in a system not under our backup control).

## Resolved decisions

- **Alerting is a non-goal for this spec.** No alertmanager, no notification channels, no alert rules. Operators look at Grafana dashboards. Alerting design is deferred to a separate brainstorm.
- **Scrape target list for v1**: `node-exporter`, `cadvisor`, `caddy`, `jupyter` (best-effort), `prometheus` self. `siteapp` and `flasher` are excluded — they don't expose `/metrics` today and adding it requires service-level changes.
- **Chisel coverage**: derived from `node-exporter` (TCP connection states, network counters on the chisel listen port) + `cadvisor` (chisel container resource use). No chisel-specific exporter.
- **Prometheus and cAdvisor UIs are `labnet`-only.** No Caddy route, no basicauth. Ad-hoc access via `docker compose exec` or SSH tunnel.
- **Retention = 30d**, mirroring `loki_retention_days`. New pin `prometheus_retention_days: 30`.
- **Yandex Unified Agent spec + plan are kept and marked superseded** with a banner linking to this spec. Code surface is hard-deleted.
- **Approach 1 (single atomic PR)**: one squash-merge contains the adds and the deletes. No intermediate state where two stacks coexist or where the platform has no monitoring at all.
- **Unconditional rendering of the Prometheus stack.** No marker-block strip, no `LDS_*` toggle. CI fake-VPS brings up the same stack as prod.
- **Approach 1 implies a Conventional Commits `feat:` PR**, which release-please will translate into the next minor bump.
