# Public docs rewrite — content design

**Date:** 2026-05-22
**Status:** Spec (pre-plan)
**Touches:** `public_docs/` (content + manifests). No code changes.

## Problem

`public_docs/` carries two stale full-platform overviews (`system-overview.md`,
`technical-overview.md`) plus a placeholder scaffold (`admin/`, `operator/`,
`researcher/`, `reference/`) whose section files are one-line stubs pointing
back at the overviews. The site has no real documentation: a researcher with
fresh credentials, a new lab operator, a server administrator, and a technical
auditor all land on the same two pages and have to read between the lines.

We need a documentation set that serves five concrete audiences with the
features `siteapp` already supports (markdown-it + GH alerts + mermaid +
syntax-highlighted code + per-directory `_nav.yaml` manifests, the last
landed in PR #128).

## Goals

1. **Five audience-shaped sections**, each reachable in one click from the
   `/docs/` landing page.
2. **First-time visitor** can understand what lab-bridge is and find their
   section in under a minute.
3. **Researcher** with credentials can run their first notebook in five
   minutes following one walkthrough.
4. **New lab operator** can install SerialHop on a Windows PC and verify
   their lab is online following one walkthrough.
5. **Server administrator** can find every routine operation (deploy, lab
   registration, user management, dashboards, firmware) without leaving the
   docs.
6. **Technical auditor / evaluator** can understand the network model, auth
   model, and security decisions in a self-contained `architecture/` section.
7. Replace the two overviews and the placeholder scaffold in one change. No
   transitional URLs — the legacy paths 404 after this lands.
8. **English-only**. No `*.ru.md` files. The lang toggle still works elsewhere
   on the site (home, download).

## Non-goals

- **`bioexperiment_suite` API reference.** The Researcher section is a
  task-oriented cookbook only. Method signatures, exception hierarchy, and
  byte-level protocol details stay in the `bioexperiment_suite` repo.
- **SerialHop internals.** The Operator section walks an operator through
  install + configuration. Build process, binary signing, run-mode internals,
  and the serial command vocabulary stay in the `serialhop` repo.
- **CI/CD mechanics.** release-please flow, branch protection, GHCR cleanup —
  those live in the repo's `docs/superpowers/specs/` and `CLAUDE.md` and are
  not part of the public-facing docs.
- **Russian translation.** Single-language EN. RU pages can be added later
  file-by-file by dropping `*.ru.md` next to the EN file.
- **Platform launcher links from `/docs/`.** JupyterLab / Grafana / Flasher /
  agent download links belong on `/` (the home page already has them), not in
  the docs sidebar.
- **New siteapp features.** No code changes. Everything below works with the
  current markdown renderer and manifest-driven nav.

## Audiences

| # | Audience                              | Entry section            | Reads also           |
|---|---------------------------------------|--------------------------|----------------------|
| 1 | First-time visitor                    | `/docs/` (Welcome)       | one role section     |
| 2 | Org evaluator (scientific/industrial) | `/docs/` → architecture  | admin/deploy         |
| 3 | Existing-install server admin         | `/docs/admin/`           | architecture         |
| 4 | New lab operator                      | `/docs/operator/`        | (none required)      |
| 5 | Researcher with credentials           | `/docs/researcher/`      | (none required)      |
| 6 | Technical auditor                     | `/docs/architecture/`    | admin/deploy         |

The five doc sections cover all six audiences. The auditor and evaluator share
`/docs/architecture/`; the evaluator additionally skims `/docs/admin/deploy.md`
for on-premises feasibility.

## Design

### Section structure

```
public_docs/
├── _nav.yaml                              # root: researcher, operator, admin, architecture
├── index.md                               # Welcome (docs navigation by role)
│
├── researcher/
│   ├── _nav.yaml                          # first-notebook, working-with-devices, experiments, troubleshooting
│   ├── index.md
│   ├── first-notebook.md
│   ├── working-with-devices.md
│   ├── experiments.md
│   └── troubleshooting.md
│
├── operator/
│   ├── _nav.yaml                          # setup-lab-pc, config
│   ├── index.md
│   ├── setup-lab-pc.md
│   └── config.md
│
├── admin/
│   ├── _nav.yaml                          # deploy, labs, users-and-groups, grafana, flashing
│   ├── index.md
│   ├── deploy.md
│   ├── labs.md
│   ├── users-and-groups.md
│   ├── grafana.md
│   └── flashing.md
│
└── architecture/
    ├── _nav.yaml                          # services, network, auth, security, data-flow
    ├── index.md
    ├── services.md
    ├── network.md
    ├── auth.md
    ├── security.md
    └── data-flow.md
```

21 markdown files (1 root + 5 researcher + 3 operator + 6 admin + 6 architecture)
plus 5 `_nav.yaml` manifests. The root `_nav.yaml` exists today
listing the legacy structure (`system-overview`, `technical-overview`,
`researcher`, `operator`, `admin`, `reference`) and is fully replaced by this
work.

### Page-by-page content

#### Welcome — `index.md`

**Audience:** first-time visitor.

- One-paragraph "what is lab-bridge" — three components, one outcome
  (researchers drive lab instruments from a shared notebook environment).
- Four role cards (researcher / lab operator / server admin / auditor) each
  linking to that section's index. Direct second-person ("If you've got
  credentials and want to run an experiment, start here").
- No links to JupyterLab/Grafana/Flasher/agent download — those live on `/`.
- One small mermaid diagram showing the three components (lab PC, VPS, user),
  adapted from the existing home-page topology block.

#### Researcher — `researcher/`

**Audience:** researcher with credentials.

- **`index.md`** — one-screen orientation: what you can do here, what each
  page covers, where the lab roster lives (the home page `/`).
- **`first-notebook.md`** — 5-minute walkthrough.
  1. Open JupyterLab.
  2. Visit `/` in a separate tab and read the lab name from the registered-labs
     panel. (No more `LAB_DEVICES_PORT`; identity is by lab username.)
  3. `from bioexperiment_suite.interfaces import LabDevicesClient`
  4. `LabDevicesClient.list_active_users()` to confirm the lab is online.
  5. `client = LabDevicesClient(user="<lab-name>")`, `devices = client.discover()`,
     do one trivial pump action and one densitometer temperature read. Success
     screen.
  - `[!NOTE]` block: discovery is destructive — it re-probes serial ports and
    rebuilds the device cache. Use `list_devices()` if a colleague's experiment
    might still be running.
- **`working-with-devices.md`** — cookbook recipes, one per common task:
  - Pump: set default flow rate, pour by volume, continuous rotation, stop.
  - Densitometer: read temperature, measure optical density (with the
    client-side 3-second sleep noted).
  - Valve: set position (placeholder — surface what's actually exposed).
  - Each recipe is 4–10 lines of Python with one-paragraph context. No method
    table; the focus is "here's the shape of the call".
- **`experiments.md`** — one short example using the `experiment/` module to
  chain steps, then a link to
  `https://github.com/khamitovdr/bio_tools/blob/main/examples/experiment_example.ipynb`
  for the full reference.
- **`troubleshooting.md`** — short, scoped to the researcher's view:
  - `discover()` returns no devices.
  - Lab appears in `list_registered_users()` but not in `list_active_users()`
    (lab offline → talk to the operator).
  - Common exceptions: `DeviceNotFound`, `DeviceBusy`, `DeviceUnreachable`,
    `TransportError`. One sentence each on what they mean and the typical
    cause. No exhaustive reference — that lives in the suite repo.

#### Lab Operator — `operator/`

**Audience:** new lab operator with a Windows PC and serial devices.

- **`index.md`** — one-time vs ongoing tasks. Reading order.
- **`setup-lab-pc.md`** — walkthrough.
  1. Ask the server admin to register the lab and provide chisel credentials.
  2. Download SerialHop from `/download/agent`. Verify SHA-256 with the value
     the admin gave you (referencing the download page's verification block).
  3. Install: double-click the `.exe` → control panel opens → click Install →
     approve UAC.
  4. **Before clicking Install** (`[!IMPORTANT]` alert), edit
     `SerialHop_config.yaml` next to the binary and paste the chisel
     `user`/`pass`/`host`/`port` you were given.
  5. Verify: visit `/` and confirm the lab shows ONLINE in the registered-labs
     panel; visit `/grafana/` and check the lab-client-logs dashboard shows
     traffic from your lab.
  - Sequence diagram (mermaid) of the install → first-tunnel handshake, adapted
    from the legacy `system-overview.md`.
- **`config.md`** — `SerialHop_config.yaml` keys reference, operator-facing.
  One row per key the operator should know:
  - `chisel.user` / `chisel.pass` / `chisel.host` / `chisel.port` /
    `chisel.remote_port`.
  - Log file rotation knobs.
  - Anything else needed to recover from a bad first-install (link back to
    `setup-lab-pc.md`).
  - **Out of scope:** run modes, build process, byte-level device protocol.
    These live in `serialhop`'s repo and are linked from the top of the page.

#### Server Administrator — `admin/`

**Audience:** server admin operating an existing lab-bridge install, plus the
on-prem evaluator who needs to see the operator surface.

- **`index.md`** — what the admin surface looks like: `Taskfile.yml` wraps
  shell scripts, `config.yaml` (gitignored) carries instance values + secrets,
  CI deploys on release-tag, laptop deploys for first bring-up and recovery.
  Pointer to `task --list`.
- **`deploy.md`** — first-time VPS bring-up walkthrough, derived from the
  README "Operations reference" block:
  ```bash
  task doctor
  cp config.example.yaml config.yaml         # fill in VPS details
  task secrets:set-grafana-password
  task secrets:bootstrap-authelia
  task users:add -- admin admins             # bootstrap admin
  task secrets:rotate-agent-upload-token
  task secrets:rotate-flasher-upload-token
  task provision
  task deploy
  ```
  Then verification: `task ops:logs -- siteapp`, visit `/`, sign in. Day-to-day
  deploys via CI (release-please tag → workflow → VPS).
- **`labs.md`** — register a new lab end-to-end:
  - `task secrets:add-client -- <lab-name> <remote-port>` — what each argument
    means.
  - The credential output: copy `user`/`pass`/`port` and hand to the operator
    out-of-band. The lab name is the identifier researchers use in
    `LabDevicesClient(user=...)`.
  - Where to verify it landed: home page roster (after operator installs),
    Grafana lab-client-logs dashboard filtered to the new lab.
- **`users-and-groups.md`** — derived from `docs/adding-a-user.md`:
  - Adding a researcher: `task users:add -- jane researchers`.
  - Adding an admin: `task users:add -- jane admins`.
  - The two groups and what each unlocks:
    - `researchers` — JupyterLab, Grafana (Viewer role).
    - `admins` — JupyterLab, Grafana (Admin role), Flasher.
  - Password rotation (`task users:set-password`), group changes
    (`task users:set-groups`), removal (`task users:rm`).
  - Forgotten-password and lost-bootstrap-admin recovery paths.
- **`grafana.md`** — pre-provisioned dashboards and when to use each:
  - **Lab client logs** — live tail of SerialHop log streams. Use when: a
    specific lab reports problems, or you want to see who's actively connected.
  - Whatever else is provisioned under `compose/grafana/` (verify against the
    current set; flag any drift). One paragraph per dashboard: what it shows,
    when to look.
  - One short subsection at the end: "Creating a new dashboard" — Grafana UI
    walkthrough, where dashboards are persisted, how to commit it back to
    `compose/grafana/dashboards/`.
- **`flashing.md`** — Flasher service walkthrough:
  - What it does: push firmware to a lab device through the existing chisel
    tunnel.
  - How firmware gets into Flasher: primarily by the device manufacturer (or
    their CI) uploading via the bearer-token API. The admin's job is then
    pushing the latest available build to a specific lab via the UI at
    `/flash/`. Manual upload through the UI is available but is the
    exceptional path.
  - End-to-end UI walkthrough: select firmware → select lab → push → verify
    the device reports the new version.

#### Architecture — `architecture/`

**Audience:** technical auditor, on-prem evaluator, and any admin who wants
the model rather than the recipes.

- **`index.md`** — single-stack philosophy (one Docker Compose stack behind
  one Caddy edge, lab PCs dial in, no inbound ports on the lab network).
  Component list with one-line role per component. Borrows the topology
  diagram from the legacy `technical-overview.md`.
- **`services.md`** — per-service responsibility, where each lives in the
  repo, what depends on what. Covers: `caddy`, `siteapp`, `authelia`,
  `flasher`, `jupyter`, `chisel`, `loki`, `grafana`, `prometheus`,
  `node-exporter`, `cadvisor`. One paragraph per service, max.
- **`network.md`** — the topology mermaid diagram (from
  `technical-overview.md`), plus:
  - Inbound surface: 80/443 (caddy) + chisel listen port. Nothing else.
  - Outbound surface from the lab PC: a single chisel session, carrying both
    reverse tunnels (device APIs published to `labnet`) and a forward tunnel
    (`127.0.0.1:3100 → loki:3100` for log shipping).
  - Internal `labnet` topology.
  - Route table (Path → Service → Auth), borrowed from the README.
- **`auth.md`** — the Authelia model:
  - Forward-auth at the Caddy edge for `/jupyter/*`, `/grafana/*`, `/flash/*`.
  - Group → permission mapping: `admins`, `researchers`.
  - OIDC handshake between Caddy/Grafana and Authelia, group claim mapping to
    Grafana roles (Viewer vs Admin).
  - The login form proxy at `/login`, `/logout`, `/api/auth/*`.
  - Mermaid sequence diagram of a first-time login.
- **`security.md`** — security decisions, an auditor-facing read:
  - Lab side: no inbound ports needed (chisel dials out). Implication: no
    institutional-firewall hole-punching, no port-forward.
  - Chisel auth: per-client user/password allowlist on the VPS. Where the
    allowlist lives (`compose/chisel/users.json`), how rotation works.
  - Bearer tokens: agent upload + flasher upload. Where they live, how to
    rotate.
  - TLS: Caddy + Let's Encrypt. Automatic renewal. Internal services have no
    public ports.
  - Secret split: laptop (`config.yaml`, gitignored) vs CI (GH secrets).
    Manual sync. Pointer to the dual-management caveat from CLAUDE.md.
  - Audit harness: pointer to `tests/security/` (pytest-based black-box
    probes) and the latest report in `docs/security/`. Brief description of
    what the harness covers.
- **`data-flow.md`** — end-to-end sequence diagram of a single device call
  (notebook → chisel reverse tunnel → SerialHop → serial → instrument →
  reply path), borrowed and updated from the legacy `system-overview.md`.
  One paragraph contextualising what's happening at each hop.

### Manifest content

```yaml title="public_docs/_nav.yaml"
- name: researcher
- name: operator
- name: admin
- name: architecture
```

```yaml title="public_docs/researcher/_nav.yaml"
- name: first-notebook
- name: working-with-devices
- name: experiments
- name: troubleshooting
```

```yaml title="public_docs/operator/_nav.yaml"
- name: setup-lab-pc
- name: config
```

```yaml title="public_docs/admin/_nav.yaml"
- name: deploy
- name: labs
- name: users-and-groups
- name: grafana
- name: flashing
```

```yaml title="public_docs/architecture/_nav.yaml"
- name: services
- name: network
- name: auth
- name: security
- name: data-flow
```

The root manifest **does not** list `index` — root `index.md` is auto-pinned
as the "Home" entry by `siteapp/app/nav.py`. Section `index.md` files are
implicit (the directory's sidebar entry IS the index URL); listing them
would render a duplicate entry.

The `title:` override is not used in this iteration. Each H1 is chosen to
also work as the sidebar label.

### Conventions

- **Voice.** Direct, second person, imperative for walkthroughs ("Open
  JupyterLab", "Edit `SerialHop_config.yaml`"). Declarative for architecture
  and security ("Caddy terminates TLS on 443 and proxies …").
- **Code blocks.** Use the `title=` attribute for file/context, e.g.
  `` ```yaml title="SerialHop_config.yaml" ``. Use language tags for syntax
  highlighting (`bash`, `python`, `yaml`).
- **Alerts.** `[!WARNING]` / `[!IMPORTANT]` reserved for foot-guns
  (e.g. "Edit `SerialHop_config.yaml` before clicking Install"). `[!NOTE]` /
  `[!TIP]` sparingly.
- **Diagrams.** Mermaid where they earn their keep — topology (`network.md`,
  `architecture/index.md`), sequence flows (`auth.md`, `data-flow.md`,
  `operator/setup-lab-pc.md`), and the home-page-style component graph on
  the Welcome page. Not in every page.
- **Anchors.** Auto-generated by markdown-it's anchors plugin. Author H2/H3s
  with stable slugs in mind (no rephrasing without checking inbound links).
- **Cross-section links.** Use absolute `/docs/...` URLs (e.g.
  `[lab name](/docs/researcher/first-notebook)`) so they survive the docs
  being mounted under different prefixes in dev vs prod.

### Legacy cleanup

Deleted in the same change:

- `public_docs/system-overview.md`, `system-overview.ru.md`
- `public_docs/technical-overview.md`, `technical-overview.ru.md`
- `public_docs/index.ru.md`
- `public_docs/admin/index.ru.md`
- `public_docs/operator/setup-lab-pc.md`, `setup-lab-pc.ru.md`,
  `index.ru.md`
- `public_docs/researcher/first-notebook.md`, `first-notebook.ru.md`,
  `index.ru.md`
- `public_docs/reference/` (whole directory — `index.md`, `index.ru.md`)
- `public_docs/icons/` if no surviving doc references the SVGs (the Welcome
  rewrite drops them; verify nothing else under `public_docs/` links them).

No transitional redirects. The legacy URLs (`/docs/system-overview`,
`/docs/technical-overview`, `/docs/reference/`) 404 after this lands. None of
them are linked from outside the docs site (verified against `siteapp/app/`
and root `README.md`; the home page links to `/lab`, `/grafana/`,
`/download/agent`, and `/docs/` only).

### Test updates

Two siteapp test files reference the legacy doc URLs and need touching in
the same commit that deletes them:

- **`services/siteapp/tests/e2e/test_docs_page.py`** — two tests
  (`test_doc_page_has_new_layout`, `test_doc_with_code_block_emits_figure`)
  fetch `/docs/system-overview` and `/docs/technical-overview`. They
  currently soft-skip on non-200, so they won't fail after deletion — they
  silently no-op. Repoint each at a new doc that exercises the same feature:
  any doc with the new layout for the first; a doc with a fenced code block
  carrying `title="…"` for the second (`/docs/operator/config` or
  `/docs/admin/deploy` works).
- **`services/siteapp/tests/test_nav.py`** — `_sample_nav()` is a synthetic
  fixture mentioning `/docs/system-overview` as URL data. Tests don't
  require the file to exist; they'll pass unchanged. Update the fixture to
  use a current URL (e.g. `/docs/architecture`) so the fixture isn't
  misleading.

## Implementation phasing

The plan splits into five commits to keep each diff small and a malformed
`_nav.yaml` from boot-failing siteapp at any intermediate step:

1. **Architecture section** — write all six pages + `architecture/_nav.yaml`.
   Root manifest is updated to add `architecture` and remove the
   `system-overview` / `technical-overview` / `reference` entries; the
   corresponding legacy files (`system-overview.md`, `technical-overview.md`,
   `reference/`, and all their `.ru.md` pairs) are deleted in the same
   commit. Update `services/siteapp/tests/e2e/test_docs_page.py` and
   `services/siteapp/tests/test_nav.py` per the **Test updates** section.
   Architecture is the source of truth other pages will cross-link into,
   so it lands first.
2. **Admin section** — write `index.md`, `deploy.md`, `labs.md`,
   `users-and-groups.md`, `grafana.md`, `flashing.md` + manifest. Replaces the
   admin placeholder.
3. **Operator section** — write `index.md`, `setup-lab-pc.md`, `config.md` +
   manifest. Replaces the operator placeholder.
4. **Researcher section** — write `index.md`, `first-notebook.md`,
   `working-with-devices.md`, `experiments.md`, `troubleshooting.md` +
   manifest. Replaces the researcher placeholder.
5. **Welcome page rewrite** — rewrite root `index.md` to the docs-navigation
   shape (no platform launcher links). Delete `public_docs/icons/` if unused.

Each commit ships a coherent section the reader can use end-to-end, even
mid-rewrite. `docs_lint` runs in CI on each commit and catches missing
manifest entries.

## Verification

- **`docs_lint`** must pass on every commit: `cd services/siteapp && uv run
  python -m app.docs_lint ../../public_docs`.
- **Local boot smoke** — `cd services/siteapp && uv run uvicorn app.main:app`
  starts cleanly (siteapp calls `build_nav()` at import; a broken manifest
  crashes here).
- **Visual pass** — for each new page: render locally, confirm sidebar order
  matches the manifest, confirm mermaid diagrams render, confirm alerts and
  code blocks look right. Spot-check on preprod after deploy.
- **Link audit** — no `/docs/system-overview`, `/docs/technical-overview`,
  or `/docs/reference/` links anywhere in the repo after the rewrite. Grep
  in the same commit that deletes them.

## Risks

- **Content drift with `bioexperiment_suite` / `serialhop`.** The cookbook
  recipes and SerialHop config keys can go stale when the upstream repos
  evolve. Mitigation: keep recipes minimal (small surface), link out for
  reference content, and verify the snippet shape against the current
  `bioexperiment_suite` API before each commit. The cookbook is task-oriented
  precisely so a method renaming doesn't invalidate it.
- **Sidebar order off by one.** `_nav.yaml` is the single source of truth;
  `docs_lint` will catch missing/unknown names but not misordering. Mitigation:
  visually confirm the sidebar order after each commit on preprod.
- **Legacy file deletion racing with external links.** External docs/blog
  posts may link to `/docs/system-overview`. We've never published the URL
  outside the repo, so the risk is low. If it surfaces later, add a short
  redirect handler in `siteapp/app/docs.py`.
- **`docs_lint` failing in CI on an intermediate commit.** Mitigation: each
  commit's `_nav.yaml` change is paired with the file additions/deletions in
  the same commit. The lint step in `pr-siteapp.yml` runs against the PR's
  squash result, so the granularity of intermediate commits doesn't matter
  for CI — but local pre-commit runs of `docs_lint` are recommended.
