# Host monitoring via Yandex Unified Agent

**Status:** draft (brainstorming complete; pending user review before implementation plan).

## Problem

The platform currently has no host-level observability:

- Grafana + Loki cover application logs (chisel client logs, Loki ingest from the agent fleet), but nothing watches the VPS itself.
- We do not know RAM pressure, disk fill, disk I/O saturation, or network bandwidth on the prod VPS until something falls over.
- Loki's retention is 30 days of compressed logs; a slowly filling disk is invisible until ingest starts failing.
- The chisel server multiplexes long-lived TCP tunnels — TCP connection counts and network saturation matter, and we have no view of either.

The prod VPS runs on Yandex Cloud. Yandex Monitoring is a fully managed metrics + alerting backend that we already have access to. The intended ingest path is **Yandex Unified Agent** ([docs](https://yandex.cloud/en/docs/monitoring/concepts/data-collection/unified-agent/)) — a small daemon that collects metrics from configured inputs and pushes them out, with `linux_metrics` (CPU/RAM/disk/network/I/O/kernel) as a first-class input and `yc_metrics` as the Yandex Monitoring output.

## Goals

1. **Surface host health for the prod VPS** in Yandex Monitoring, covering at minimum RAM utilization and disk space utilization (the user-explicit asks), plus a small set of cheaply-included additional signals that pay off operationally (disk I/O, CPU + load, network bandwidth, TCP connections, agent self-metrics).
2. **Keep the Yandex Cloud surface narrow and replaceable.** Only the `unified-agent` service block and its config file know about Yandex. The rest of the stack — Caddy, Loki, Grafana provisioning, siteapp, flasher — stays vendor-neutral. Migrating to AWS / GCP / self-hosted means swapping those two artifacts and nothing else.
3. **Don't break CI.** The CI deploy targets a fake-VPS that isn't a Yandex Cloud VM and cannot auth to `monitoring.api.cloud.yandex.net` via the metadata service. The unified-agent service must be cleanly omitted on CI deploys without making the rest of the stack flaky.
4. **No new secrets in the repo.** Authentication uses the Yandex Cloud metadata service (`cloud_meta`), which means the prod VM has a service account attached at the infra level. No SA key file, no GH secret, no laptop secret.

## Non-goals

- **Alerting rules / notification channels.** Yandex Monitoring has native alerting; configuring it is per-instance console work, not repo code. The spec stops at "metrics arrive in Yandex Monitoring."
- **Container-level metrics (cAdvisor-style).** `linux_metrics` reads host procfs/sysfs — it gives us host totals, not per-container splits. Per-container CPU/RAM is a worthwhile follow-up but requires a different agent and is out of scope here.
- **Application-level metrics from siteapp / flasher / Caddy.** Unified Agent supports `metrics_pull` to scrape Prometheus-format endpoints, but none of our services currently expose one. Wiring app metrics is a future iteration.
- **Grafana ↔ Yandex Monitoring datasource integration.** Use Yandex Monitoring's native dashboards initially. If we later want a single pane of glass with Loki logs, we revisit.
- **Backfill or migration of historical data.** Metrics start when the agent starts; nothing retroactive.
- **Multi-VPS.** The stack currently runs on a single VPS. The design works unchanged when we add a second, but we don't pre-build for it.

## Design

### Component shape

A new compose service:

```yaml
unified-agent:
  image: __UNIFIED_AGENT_IMAGE__
  restart: unless-stopped
  command: ["unified_agent", "--config", "/etc/yandex/unified_agent/config.yml"]
  volumes:
    - ./unified-agent/config.yml:/etc/yandex/unified_agent/config.yml:ro
    - /proc:/host/proc:ro
    - /sys:/host/sys:ro
    - /:/host/root:ro,rslave
  pid: host
  network_mode: host
  read_only: true
  tmpfs:
    - /tmp
    - /var/lib/yandex/unified_agent
```

Notes on the placement:

- **`network_mode: host`**: required so `cloud_meta` can reach `169.254.169.254` (Yandex Cloud's metadata service); the bridge network the rest of the stack uses would mask it. This is the only service that breaks out of `labnet`, and it doesn't expose any ports, so the bridge-isolation property of the rest of the stack is preserved.
- **`pid: host`**: lets `linux_metrics` see real PIDs for the kernel/process stats it collects.
- **`/proc`, `/sys`, `/` mounted read-only**: standard pattern for a containerized node-exporter-style agent. `linux_metrics` is pointed at `/host/proc` and `/host/sys` via the config.
- **No published ports**: the agent only pushes outward. Nothing scrapes it.
- **`read_only: true` + `tmpfs`**: defense in depth; the agent only needs writable space for its in-memory buffer.

### Configuration

`compose/unified-agent/config.yml.tmpl` (rendered by `scripts/lib/render.sh` like every other template):

```yaml
status:
  port: 0  # disable the status HTTP server; we don't scrape it

agent_log:
  level: notice

main_thread_pool:
  threads: 2

storages:
  - name: main
    plugin: fs
    config:
      directory: /var/lib/yandex/unified_agent
      max_partition_size: 100mb

routes:
  - input:
      plugin: linux_metrics
      config:
        poll_period: 30s
        proc_directory: /host/proc
        sys_directory: /host/sys
        resources:
          cpu: advanced
          memory: advanced
          network: advanced
          storage: advanced
          io: advanced
          kernel: advanced
    channel:
      pipe:
        - filter:
            plugin: assign
            config:
              labels:
                host: __VPS_HOST__
                env: prod
      output:
        plugin: yc_metrics
        config:
          folder_id: __YC_FOLDER_ID__
          iam:
            cloud_meta: {}

  - input:
      plugin: agent_metrics
      config:
        poll_period: 60s
        namespace: ua
    channel:
      pipe:
        - filter:
            plugin: assign
            config:
              labels:
                host: __VPS_HOST__
                env: prod
      output:
        plugin: yc_metrics
        config:
          folder_id: __YC_FOLDER_ID__
          iam:
            cloud_meta: {}
```

Why this shape:

- **`resources: advanced` across the board** — gives us the full superset (CPU, load, RAM/swap, disk space, disk I/O, network bytes/packets/drops, TCP connection states, kernel counters) without per-metric tuning. The cost is a handful of extra series; for a single VPS this is negligible.
- **`poll_period: 30s`** for system metrics — granular enough to catch incidents, infrequent enough to keep series counts low.
- **`assign` filter adds `host` and `env` labels** at the agent so dashboards can filter cleanly when we eventually add a second VPS.
- **`agent_metrics` on a second route** — self-monitoring of the agent (delivery errors, queue sizes). Cheap insurance against silent failures.
- **`fs` storage with a 100MB cap on tmpfs** — gives the agent a small persistent-style buffer for retry on network blips, capped to avoid runaway disk use.

### Pins and config split

Following the existing `pins.yaml` / `config.yaml` convention:

- **`compose/pins.yaml`** gains:
  - `unified_agent_image: cr.yandex/yc/unified-agent:25.03.80` (pin to a specific version, **not** `latest` — same rule as every other image; Renovate manages the bump).
- **`config.yaml`** (gitignored, laptop-only) gains:
  - `yc_folder_id: b1g...` — the Yandex Cloud folder UID that owns the Monitoring workspace. Instance-specific, never committed.
- **`config.example.yaml`** documents the new field with a placeholder.
- **`config.ci.yaml.tmpl`** does **not** get the field. The render layer treats its absence as "unified-agent disabled" (see CI handling below).

### Render-layer changes

`scripts/lib/render.sh::render_compose` currently does a flat `__PLACEHOLDER__` substitution. It gains:

1. New placeholders `__UNIFIED_AGENT_IMAGE__`, `__YC_FOLDER_ID__` resolved from `pins.yaml` and `config.yaml`.
2. **Conditional inclusion** of the `unified-agent` service block: if `yc_folder_id` is empty (CI case), the block is stripped. Implementation option: bracket the block in `# >>>unified-agent` / `# <<<unified-agent` markers in the template and have render strip the range when the folder id is unset, mirroring the `LDS_STACK_ONLY` chisel-omission pattern already in `deploy.sh`.
3. New render function `render_unified_agent_config` for `compose/unified-agent/config.yml.tmpl` → staged `unified-agent/config.yml`. Skipped when the service is disabled.

### CI handling

- `config.ci.yaml.tmpl` keeps `yc_folder_id` unset → render strips the service block → `docker compose up -d` brings up the same stack minus unified-agent.
- The bats matrix in `pr-platform.yml` is unaffected: the smoke tests assert routing/wiring of Caddy/siteapp/flasher/grafana, none of which depend on unified-agent.
- Adding the service does not add a new required check.

### Prod infra (one-time, outside this repo)

1. Create a Yandex Cloud service account, e.g. `lab-bridge-monitoring-writer`.
2. Grant it `monitoring.editor` on the folder.
3. Attach the SA to the prod VM (instance-level — Compute Cloud → instance → Edit → Service account). After this, `cloud_meta` on the VM transparently mints IAM tokens for that SA.
4. Put the folder id into `config.yaml` on the laptop.
5. Run `task deploy`.

The infra steps live in a new section of `README.md` ("First-time setup: host monitoring"), not in the spec.

### Cloud portability

The lock-in is contained to two files:

- `compose/unified-agent/config.yml.tmpl` (Yandex-specific schema).
- The `unified-agent` block inside `compose/docker-compose.yml.tmpl` and its pin in `compose/pins.yaml`.

Migration playbook for a future move off Yandex Cloud:

- **AWS** → replace with the CloudWatch Agent container, point at the same `/host/proc` mount.
- **GCP** → replace with the Ops Agent container, same shape.
- **Self-hosted / vendor-neutral** → replace with `node_exporter` + Prometheus (Prometheus can live alongside or replace Loki's role for metrics; both are Grafana data sources).

The rest of the stack does not know unified-agent exists. No app code, no Caddy route, no Grafana provisioning, no siteapp/flasher contract references it. Renaming the service or swapping its image is a one-PR change.

### What we explicitly do NOT do

- **No `unified-agent` exposed to Caddy.** The agent has no UI; we don't route to it.
- **No Loki ingest from unified-agent.** Logs ≠ metrics; the two paths stay separate.
- **No new Grafana datasource for Yandex Monitoring.** Yandex's native dashboards are the initial UI. Adding a Grafana plugin is a follow-up if we want unified dashboards.
- **No `metrics_pull` input for app metrics.** Out of scope; revisit when siteapp/flasher expose `/metrics`.

## Testing

- **Unit / render-layer:** add a test under `tests/integration/test_render_*.bats` (or wherever render tests live — confirm during planning) that:
  - With `yc_folder_id` set, `unified-agent` appears in the rendered compose and the config file is produced.
  - With `yc_folder_id` empty, `unified-agent` is absent from rendered compose and no config file is produced.
- **Platform integration:** the existing `pr-platform / platform` bats matrix already covers "stack comes up cleanly" — that exercises the empty-folder-id (CI) path automatically.
- **Manual / post-deploy:** after first deploy, verify metrics in Yandex Monitoring console (folder → Monitoring → Metric explorer; the linux_metrics namespace should have CPU/RAM/disk series tagged with `host=<VPS_HOST>, env=prod`).

## Rollout

1. Land the spec + plan.
2. Implementation PR: adds the compose block, render changes, pins entry, config.example field, README section. Renders cleanly with and without `yc_folder_id`.
3. Squash-merge → release-please cuts the next patch version → CI deploys (without unified-agent).
4. Operator: set `yc_folder_id` in laptop `config.yaml`, attach the SA to the prod VM, run `task deploy`.
5. Verify metrics in Yandex Monitoring.

## Resolved decisions

- **Auth = `cloud_meta`.** Confirmed: prod VPS is a Yandex Cloud VM. No SA key file, no new secret in the laptop/CI flow.
- **Polling cadence = 30s system / 60s self-monitoring.** Confirmed.
- **`network_mode: host` for the unified-agent service only.** Confirmed; the rest of the stack stays on `labnet`.
- **Grafana ↔ Yandex Monitoring datasource = follow-up, not this PR.** Use YC Monitoring native dashboards initially.
