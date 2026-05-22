# Services

Every service in lab-bridge lives at `services/<name>/` with its own `Dockerfile`, `pyproject.toml`, unit tests, service-level e2e suite, and dedicated CI workflow. Compose templates, Caddy config, provisioning manifests, and pinned image digests live separately under `compose/`. The sections below describe each service in the order it sits in the request path, from the public edge inward.

## Caddy

Caddy is the TLS edge. It listens on 80 and 443, obtains and renews Let's Encrypt certificates automatically, and proxies every HTTP route per the table in [network topology](/docs/architecture/network). It also runs the `forward_auth` checks against Authelia for protected routes and injects the shared navbar into every HTML response so each upstream UI carries the same chrome. Source lives at `services/caddy/`.

## siteapp

`siteapp` is the FastAPI service at `services/siteapp/`. It serves the home page at `/`, the public docs under `/docs/` (rendered from `public_docs/` with per-directory `_nav.yaml` manifests), the agent installer at `/download/agent`, and the login form at `/login`. It also exposes the public read-only API at `/api/public/*` and the bearer-protected `/api/agent/upload` endpoint that SerialHop release CI uses to publish new agent builds.

## Authelia

Authelia at `services/authelia/` is the identity provider for the whole stack. Caddy gates `/flash/*`, `/grafana/*`, and `/jupyter/*` by calling Authelia via `forward_auth` on every request. Grafana additionally completes an OIDC handshake against Authelia so it can read group claims and assign Grafana roles. The user database and session config live in `compose/authelia/`.

## Flasher

`flasher` at `services/flasher/` is the firmware library and flashing UI, mounted at `/flash/*` and restricted to the `admins` group. Administrators browse available firmware, pick a target device on a specific lab PC, and trigger a flash. The actual write happens on the lab PC: flasher pushes the image over the chisel reverse tunnel and SerialHop programs the instrument.

## JupyterLab

JupyterLab is the shared notebook environment at `/jupyter/*` and the primary research surface — this is where `bioexperiment_suite` notebooks run. It is provided as an upstream image with no custom code in `services/`; everything lab-specific is configured at compose time. Any authenticated Authelia user can sign in.

## chisel

The public `chisel` server is what makes the lab-PC-as-client model work. Each SerialHop instance opens one outbound TCP session to it; over that session chisel publishes the lab's REST API into `labnet` (so `jupyter` and `flasher` can call it by container DNS) and carries a forward tunnel `lab_pc:127.0.0.1:3100 → loki:3100` for log shipping. The per-client allowlist is rendered from `chisel_clients` in `config.yaml` via `compose/chisel-users.json.tmpl` and mounted into the container on the VPS.

## Loki

Loki is the log aggregator. It has no published port and only listens on `labnet`. SerialHop instances stream their logs into it over the chisel forward tunnel, and Grafana reads them for the lab-client-logs dashboard.

## Grafana

Grafana is internal-only and reached via `/grafana/*`. Its Loki and Prometheus datasources are provisioned at boot, and dashboards under `compose/grafana/provisioning/dashboards/` are deployed automatically. Roles are mapped from the OIDC `groups` claim returned by Authelia — `researchers` get the Viewer role, `admins` get the Admin role.

## Prometheus

Prometheus scrapes metrics from every service on `labnet` plus the host exporters. It has no published port; Grafana is the only consumer.

## node-exporter

`node-exporter` exposes host metrics for the VPS itself — CPU, memory, disk, network — to Prometheus.

## cAdvisor

`cadvisor` exposes per-container resource metrics for every service on `labnet`, so dashboards can break out CPU and memory usage by service.
