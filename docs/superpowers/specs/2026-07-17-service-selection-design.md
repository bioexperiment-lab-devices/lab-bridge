# Service selection (optional-service deploys) — design

Date: 2026-07-17
Status: approved

## Problem

The stack always deploys all 13 containers. On a low-budget VPS the heavy
optional pieces (JupyterLab's ~4 GB scipy image, the 5-container monitoring
stack, Experiment Studio, the WebRTC streamer, the flasher) waste RAM/disk the
instance can't afford. Operators need a per-instance way to choose which
optional services deploy, configured outside git (instance-specific, like the
roster), while core plumbing stays mandatory.

## Decisions (agreed in brainstorming)

| Decision | Choice |
| --- | --- |
| Optional set | `jupyter`, `monitoring` (one toggle = grafana+loki+prometheus+node-exporter+cadvisor), `studio`, `streamer`, `flasher` |
| Mandatory core | `caddy`, `authelia`, `siteapp`, `chisel` — cannot be disabled |
| Config home | `disabled_services` list in the existing gitignored `config.yaml` |
| CI deploy source | GH Actions variable `LDS_DISABLED_SERVICES`, dual-managed with laptop config (same convention as secrets) |
| Disabled UX | Fully absent: routes stripped (path → styled 404), navbar entries hidden |
| Mechanism | Render-time filtering (yq surgery on rendered compose + marker-stripped Caddyfile); rejected compose profiles (no reliable teardown of deactivated services, depends_on breakage, still needs the Caddy/probe work) and compose-file overlays (template shredded into ~6 files, COMPOSE_FILE coupling, still needs depends_on pruning) |

## Config schema

```yaml
# config.yaml (gitignored) — absent key or [] = full stack (default)
# Allowed names: jupyter, monitoring, studio, streamer, flasher
disabled_services: [jupyter, monitoring]
```

- **Disabled list, not enabled map**: absent key = everything on, so every
  existing config (laptop, CI template, bats fixtures) works unchanged.
- `monitoring` is the only valid name for the observability stack; its five
  compose services are never toggled individually.
- `config.example.yaml` documents the key with the allowed names and the
  caveats (Loki log shipping, data retention — see below).

## Registry & validation (`scripts/lib/config.sh`)

Single source of truth for what is optional:

- `_OPTIONAL_SERVICES=(jupyter monitoring studio streamer flasher)`
- `_MONITORING_SERVICES=(grafana loki prometheus node-exporter cadvisor)`

`validate_config` additions:

- every `disabled_services` entry must be in `_OPTIONAL_SERVICES`; unknown
  names and core names (`caddy`, `authelia`, `siteapp`, `chisel`) fail with a
  clear per-entry error;
- duplicate entries are rejected.

`load_config` exports:

- `DISABLED_SERVICES` — the raw group names (space-separated, e.g.
  `jupyter monitoring`), for healthcheck/secret gating and Caddyfile marker
  stripping;
- `DISABLED_COMPOSE_SERVICES` — the compose-level expansion (e.g.
  `jupyter grafana loki prometheus node-exporter cadvisor`), for compose
  filtering.

Helper `service_disabled <name>` (checks `DISABLED_SERVICES`) keeps call
sites in `deploy.sh`/`render.sh` readable.

## Render changes (`scripts/lib/render.sh`)

### Compose filtering

`render_compose` renders the full template as today, then a new
`filter_compose <file>` step applies `DISABLED_COMPOSE_SERVICES` via `yq`:

1. `del(.services.<name>)` for each disabled compose service.
2. Prune deleted names from `services.caddy.depends_on` (compose refuses to
   start a service whose `depends_on` references an undefined service).
3. Prune every top-level `secrets:` entry no longer referenced by any
   remaining service (generic reference scan, not a hardcoded list). This
   covers `grafana_admin_password` + `grafana_oidc_secret` (monitoring off)
   and `flasher_upload_token` (flasher off) — their files are not staged when
   disabled, so a dangling entry would fail `docker compose up`.

Because the rendered file simply lacks the service, `docker compose up -d
--remove-orphans` on the VPS removes a newly-disabled container
automatically. `*_data` dirs are preserved (existing rsync excludes), so
re-enabling a service restores its state.

### Caddyfile marker stripping

Each optional service's route blocks in `compose/Caddyfile.tmpl` are wrapped
in markers:

```
# --- BEGIN svc:jupyter ---
handle /jupyter* { ... }
# --- END svc:jupyter ---
```

Marker map: `jupyter` → `/jupyter*` handle; `monitoring` → both `/grafana`
handles; `studio` → `/studio/*` handle; `streamer` → both `/streamer`
handles; `flasher` → both `/flash` handles. `render_caddyfile` deletes marked
ranges for disabled services (awk/sed range delete). Stripped paths fall
through to the existing catch-all → styled 404. Core routes carry no markers.

### Navbar hiding

Caddy's replace-response injection of the navbar `<script>` tag (which
already carries `data-version`) gains `data-disabled="<navbar-ids>"`,
substituted at render time. Mapping from config names to navbar ids:
`jupyter`→`jupyter`, `monitoring`→`grafana`, `studio`→`studio`,
`flasher`→`flasher`; `streamer` has no navbar entry. `navbar.js` reads the
attribute and filters its `SERVICES` list (and `PATH_RULES` stay harmless for
hidden entries). No runtime lookups.

## Deploy changes (`scripts/deploy.sh` + CI action)

Per disabled service, `deploy.sh`:

- **Secret staging**: skip the hard requirement + staging of
  `grafana/admin_password` and `grafana/oidc_secret` (monitoring),
  `flasher/upload_token` (flasher).
- **Config renders**: skip `render_loki_config`, `render_prometheus_config`,
  and the Grafana provisioning copy when monitoring is disabled.
- **Restart list**: build dynamically — always `caddy siteapp`; add
  `streamer` (enabled), `grafana` (monitoring enabled); full (non-stack-only)
  mode adds `chisel authelia` as today. `docker compose restart <unknown>`
  is an error, hence the gating.
- **Healthcheck probes**: skip `/jupyter/` (jupyter), `/grafana/api/health`
  (monitoring), `/flash/` + flasher API expectations (flasher),
  `/streamer/labs` (streamer), `/studio/` (studio). Core probes (home,
  authelia, docs, download, static, public API, server-info) always run.

CI (`.github/actions/deploy-stack/action.yml` + release-please.yml):

- `compose/config.ci.yaml.tmpl` gains
  `disabled_services: [${LDS_DISABLED_SERVICES}]` — empty var renders `[]`
  (full stack, today's behavior); `"jupyter, monitoring"` renders a valid
  YAML flow list.
- The action gains input `disabled_services` (default `""`), exported as
  `LDS_DISABLED_SERVICES` for envsubst; `release-please.yml` passes
  `${{ vars.LDS_DISABLED_SERVICES }}`.
- The post-deploy authenticated smoke step gates its per-service probes on
  the same input (same skip set as the healthcheck; check
  `scripts/post_deploy_smoke.sh` call sites during planning).
- **Dual management**: the GH variable must mirror the laptop
  `config.yaml` for the CI-deployed VPS, exactly like the existing secret
  pairs. Out-of-sync consequence (next release re-enables/removes a service)
  is documented next to the secrets dual-management note in README.

## Deliberately unchanged

- **Authelia config** keeps the grafana OIDC client and the access-control
  rules for disabled routes — both inert when the service is absent. Keeps
  `task secrets:bootstrap-authelia` unconditional.
- **Chisel client allow-lists** keep the `loki:3100` forward. With monitoring
  disabled a client's log push fails at connect time, harmlessly; documented
  as the "disabling monitoring drops client log shipping" caveat.
- **rsync excludes / data dirs** — disabling never deletes `*_data`;
  re-enable restores prior state.
- **LDS_STACK_ONLY / LDS_REQUIRE_VAULT semantics** — untouched; service
  selection is orthogonal to roster handling.

## Testing

1. **Cheap render assertions** (new bats file, joins the existing `cheap`
   matrix cell — no fake VPS): render with assorted `disabled_services`
   values and assert: compose lacks the disabled services, caddy
   `depends_on` pruned, unreferenced secrets pruned, Caddyfile lacks the
   marked routes but keeps core ones, navbar injection carries the right
   `data-disabled`, validation rejects core/unknown/duplicate names, absent
   key renders identically to today.
2. **Fake-VPS integration** (`tests/integration/test_service_selection.bats`,
   new `pr-platform.yml` matrix cell with the `compose_images_available`
   skip pattern): one bring-up with all five optional services disabled;
   assert the trimmed stack deploys healthy (core routes respond), disabled
   paths return the styled 404, disabled containers do not exist.
3. Existing suites untouched — default config = full stack.

No branch-protection change: only a new matrix cell inside `pr-platform`,
whose aggregator job is already the required check.

## Docs

- `config.example.yaml`: commented `disabled_services: []` block.
- README: "Optional services" subsection — allowed names, monitoring group
  semantics, Loki log-shipping caveat, data-preservation note, GH-variable
  dual management.
- CLAUDE.md config split: one line (`disabled_services` → config.yaml;
  optional-service registry → `scripts/lib/config.sh`).
- `docs/adding-a-service.md`: new step — decide mandatory vs optional; if
  optional, add registry entry, Caddyfile markers, navbar mapping, probe +
  secret gating, render-assertion coverage.

## Rollout

1. Develop on a branch; real-world verification against preprod
   (`khamit@111.88.145.138`): laptop-deploy with services disabled → verify
   absent + healthy core; re-enable → verify restored.
2. PR → full CI green → squash-merge.
3. Release deploy runs with `LDS_DISABLED_SERVICES` unset → production
   behavior unchanged (full stack). Setting the variable later is an
   independent, reversible operation.
