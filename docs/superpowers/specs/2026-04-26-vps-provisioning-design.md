# VPS Provisioning for Lab Devices Server — Design

**Date:** 2026-04-26
**Status:** Approved (pre-implementation)

## Purpose

Provision a single Ubuntu 24.04 VPS over SSH and run a three-container Docker
Compose stack that exposes a JupyterLab server to a small fixed team of
authenticated users, while letting NAT'd lab devices connect inbound through a
chisel reverse-tunnel server. Operations are driven from the operator's laptop
via a Taskfile that wraps bash scripts; nothing on the VPS holds operational
intelligence beyond what the scripts upload.

## Goals and non-goals

**Goals:**

- One-command provisioning of a fresh VPS to a working state.
- One-command deploy / redeploy after any config change.
- Per-user authentication for JupyterLab access.
- Per-device authentication for chisel clients with route restrictions.
- Real, browser-trusted TLS on a bare IP address with no domain name.
- Reproducible builds via pinned container images.
- All operator-side configuration in a single file with secrets kept out of git.

**Non-goals:**

- Multi-tenant JupyterLab (single shared workspace is sufficient).
- 2FA / OIDC / SSO (basic auth at the edge is sufficient for the team size).
- High availability, multi-VPS, blue/green deploys.
- Automated backup retention or off-site backup.
- Self-service device onboarding.

## High-level architecture

```
┌─────────────────────────────── VPS host ──────────────────────────────┐
│                                                                       │
│   :443 ──┐                  :8080 ──┐                                 │
│          │                          │                                 │
│   ┌──────▼──────┐         ┌─────────▼─────────┐    ┌───────────────┐  │
│   │   caddy     │ ──────► │     jupyter       │    │    chisel     │  │
│   │             │  proxy  │ (single jovyan    │    │ server        │  │
│   │ basic_auth  │         │  user, token off, │    │ users.json    │  │
│   │ acme(IP)    │         │  no listen on     │    │ listen 8080   │  │
│   │             │         │  host)            │    │ binds 9001…   │  │
│   └─────────────┘         └─────────┬─────────┘    │ inside cont.  │  │
│                                     │              └───────┬───────┘  │
│                                     └──── http://chisel:9001 ────────►│
│                                                                       │
│   bind mounts:                                                        │
│     /srv/jupyterlab/work     → jupyter:/home/jovyan/work              │
│     /srv/lab_devices_server/caddy_data → caddy:/data  (cert storage)  │
│     /srv/lab_devices_server/chisel/users.json → chisel:/etc/...       │
└───────────────────────────────────────────────────────────────────────┘
```

All three containers attach to one user-defined bridge network (`labnet`).

**Port topology:**

| Port | Where it lives | Published to host? | Public? |
|---|---|---|---|
| 443 | Caddy TLS listener | Yes | Yes — JupyterLab UI for users |
| 80 | Caddy HTTP-01 ACME challenge + redirect to 443 | Yes | Yes — required for ACME |
| `chisel.listen_port` (default 8080) | Chisel server's TCP listener for inbound client connections | Yes | Yes — lab-device chisel clients dial in |
| `chisel_clients[*].reverse_port` (e.g. 9001, 9002) | Bound *inside* the chisel container when a client requests a reverse tunnel | **No** | **No** — only reachable as `chisel:<port>` from other containers on `labnet` |
| 8888 | JupyterLab listener | **No** | **No** — Caddy reaches it as `jupyter:8888` |

ufw rules: allow 22/80/443/`chisel.listen_port`, default-deny inbound.

## Authentication model

**JupyterLab users (humans):**

- A small fixed team (2–10 people), each with their own credentials.
- Authentication is enforced at the Caddy edge via HTTP Basic Auth.
- JupyterLab itself runs with `--ServerApp.token=''` and
  `--ServerApp.password=''` — token and password disabled. Caddy is the sole
  gatekeeper.
- The shared workspace is a single bind-mounted host directory; every
  authenticated user lands as the same `jovyan` Linux user inside the
  container.
- Risk acknowledged: anyone who reaches port 8888 directly inside the docker
  network is in. Mitigated by never publishing 8888 and not running other
  containers on `labnet`.

**Chisel clients (lab devices):**

- Each device gets its own credential pair `name:password`.
- The chisel server's `users.json` restricts each credential to a single
  reverse-tunnel route (e.g. `microscope-1` may only request
  `R:0.0.0.0:9001`). A compromised device can therefore only bind its
  assigned port.
- Reverse-tunnel ports are not host-published, so even if a device pushes
  data through its tunnel, that data is only reachable from JupyterLab via
  the docker network.

## TLS

Caddy obtains a real, browser-trusted, short-lived certificate **for the IP
address** via Let's Encrypt's IP-cert profile (ACME, `tls-alpn-01` on 443 +
`http-01` on 80). The `caddy_data` bind mount persists issued certs across
container rebuilds to avoid re-hitting ACME rate limits.

If ACME issuance fails (rate limit, regional unavailability of the IP profile,
etc.), Caddy falls back to its internal CA. The deploy still succeeds; the
browser will show a cert warning until the operator investigates via
`task logs -- caddy` and re-runs deploy.

## Repository layout

```
lab_devices_server/
├── config.example.yaml           # committed, placeholder values + comments
├── config.yaml                   # GITIGNORED, the operator's source of truth
├── Taskfile.yml
├── compose/
│   ├── docker-compose.yml.tmpl   # rendered with image versions + paths
│   ├── Caddyfile.tmpl            # rendered with host IP, ACME email, basic_auth
│   └── chisel-users.json.tmpl    # rendered from chisel_clients
├── scripts/
│   ├── provision.sh              # idempotent first-time VPS setup
│   ├── deploy.sh                 # render + rsync + compose up
│   └── lib/                      # bcrypt helper, render helper, ssh wrapper
├── backups/                      # gitignored, populated by `task backup`
└── docs/
    └── superpowers/specs/        # this document
```

`config.yaml` is the single source of truth on the operator's laptop. It is
gitignored. `config.example.yaml` is committed with the same shape, but every
value is a placeholder and every section is annotated with a comment
explaining what to fill in.

Tasks that need `config.yaml` check for it first. If missing, they copy
`config.example.yaml` into place and ask the operator to fill it in:

```
$ task deploy
config.yaml not found. Created from config.example.yaml — please edit it
and re-run. Required fields: vps.host, caddy.acme_email, …
```

## Configuration schema

`config.yaml` (gitignored):

```yaml
vps:
  host: 111.88.145.138
  ssh_user: khamit
  ssh_port: 22
  remote_root: /srv/lab_devices_server
  notebooks_path: /srv/jupyterlab/work

caddy:
  acme_email: khamitov.personal@gmail.com

jupyter:
  image: quay.io/jupyter/scipy-notebook:2026-04-20

chisel:
  image: jpillora/chisel:1.10.1
  listen_port: 8080          # PUBLIC — lab-device chisel clients dial in here

# Caddy basic-auth users (managed via `task secrets:add-user`)
caddy_users:
  - name: alice
    password_hash: "$2a$14$..."
  - name: bob
    password_hash: "$2a$14$..."

# Lab devices that connect via chisel (managed via `task secrets:add-client`)
chisel_clients:
  - name: microscope-1
    reverse_port: 9001       # NOT host-published — only chisel:9001 inside labnet
    password: "k7Hf...32-char-random..."
  - name: oscilloscope-2
    reverse_port: 9002
    password: "j3Lp..."
```

`config.example.yaml` (committed): same shape, all values are obvious
placeholders (`vps.host: 0.0.0.0`,
`password_hash: "<run task secrets:add-user>"`, etc.), with comments above
each section explaining what to fill in.

## Provisioning flow (`task provision`)

Idempotent and safe to re-run.

1. SSH-reachability check (`ssh khamit@host true`) — fail fast with a clear
   message if the box isn't reachable.
2. Install Docker if not present (official `get.docker.com` script;
   `khamit` added to the `docker` group).
3. Install ufw if not present; set rules: allow 22/80/443/
   `chisel.listen_port`; default-deny inbound; enable.
4. Create directory tree under `vps.remote_root` and `vps.notebooks_path`,
   owned by `khamit` with permissions that let the `jovyan` UID inside the
   container write to the notebooks bind mount.
5. Print "✅ provisioned" and the next-step hint (`task deploy`).

Provisioning **does not** touch SSH config, **does not** disable root login,
and **does not** create users — `khamit` is assumed to exist with passwordless
sudo, per the operator's pre-existing setup.

## Deploy flow (`task deploy`)

The everyday command. Re-running after editing `config.yaml` is the standard
workflow for adding/removing users, rotating credentials, or upgrading
images.

1. **Validate locally.** `config.yaml` exists; required fields present; every
   `caddy_users[*].password_hash` looks like a bcrypt hash; every
   `chisel_clients[*]` has `name`, `reverse_port`, `password`; no two
   clients share a `reverse_port`. Fail loudly with a list of all problems
   before touching the VPS.
2. **Render templates locally** into a temp staging directory whose layout
   mirrors what should land on the VPS:

   ```
   staging/
     docker-compose.yml      # image versions and bind-mount paths
     Caddyfile               # host IP, ACME email, basic_auth user→hash,
                             # reverse_proxy to jupyter:8888 (WebSockets
                             # pass through automatically — kernels need it)
     chisel/
       users.json            # one entry per chisel_clients, route-restricted
   ```

3. **Rsync staging dir → `{remote_root}/`** with `--delete` *but* with
   `--exclude='caddy_data/'` (Caddy's persisted certs) so reissued certs
   survive deploys. The set of paths the deploy owns is exactly the three
   above; everything else under `{remote_root}` is runtime state and is
   excluded from rsync.
4. **`docker compose pull && docker compose up -d --remove-orphans`** over
   SSH.
5. **Health check.** Poll `https://{host}/` from the laptop with
   `--insecure` until it returns 401 (basic-auth challenge), or time out
   after 60s. A 401 confirms Caddy is up, TLS is serving, and basic_auth
   is wired.
6. Print "✅ deployed at https://{host}/".

**Failure modes:**

- Validation failure: nothing leaves the laptop; clear error tells the
  operator which fields to fix.
- rsync / SSH failure mid-deploy: containers keep running with the previous
  config (compose hasn't been touched yet). Re-run after fixing
  connectivity.
- `docker compose up` failure on the VPS: old containers stay until they
  crash on their own; new config files are on disk but not applied.
  Operator inspects with `task logs`.
- ACME issuance failure: Caddy falls back to internal CA; deploy still
  succeeds; browser shows cert warning until investigated.

## Taskfile surface

**Lifecycle:**

- `task provision` — first-time VPS setup.
- `task deploy` — render configs, rsync, compose up.
- `task restart` — `docker compose restart` over SSH.
- `task down` — `docker compose down` over SSH.
- `task destroy` — `docker compose down -v` and warn the operator about
  data loss.

**Secrets** (mutate `config.yaml` in place; do not auto-deploy):

- `task secrets:add-user -- alice` — prompt for password (no echo,
  confirm twice), bcrypt it (cost 14), append `{name, password_hash}` to
  `caddy_users`. Refuse if `alice` already exists.
- `task secrets:set-user-password -- alice` — same prompts; replace the
  hash for an existing user.
- `task secrets:rm-user -- alice` — remove the entry.
- `task secrets:add-client -- microscope-1 9001` — generate a 32-char
  random password (`openssl rand -base64 24`), append
  `{name, reverse_port, password}` to `chisel_clients`. Refuse if the
  name exists or the port is already taken. Print the chisel client
  invocation the operator needs to run on the device:

  ```
  ✅ Added microscope-1 (port 9001).
  Run on the device:
    chisel client https://111.88.145.138:8080 \
      microscope-1:k7Hf...32-char... \
      R:0.0.0.0:9001:localhost:80
  ```

- `task secrets:show-client -- microscope-1` — re-print the same
  invocation (for re-flashing a device). Reads from `config.yaml`; does
  not regenerate.
- `task secrets:rm-client -- microscope-1` — remove the entry.

YAML edits use `yq` so comments and field order in `config.yaml` are
preserved.

**Operations:**

- `task logs -- jupyter` (defaults to all if no service named).
- `task ps` — `docker compose ps` on the VPS.
- `task ssh` — interactive SSH session.
- `task backup` — `rsync -a --delete khamit@host:{notebooks_path}/ ./backups/notebooks-$(date +%Y%m%d-%H%M%S)/`.

**Hidden / internal helpers** (under `_render`, `_upload`, etc., not in the
main namespace) — used by the public tasks above; not intended for direct
operator invocation.

## Backups

- `task backup` is local-only by design. The operator decides whether to
  push backups elsewhere.
- No retention logic — that's `find ./backups -mtime +N -delete` if the
  operator ever wants it; out of scope.
- Caddy data (issued certs) is not backed up — they re-issue
  automatically.

## Image pinning

- `config.example.yaml` ships with specific tags
  (`jpillora/chisel:1.10.1`, `quay.io/jupyter/scipy-notebook:2026-04-20`),
  not `:latest`. Deploys are reproducible.
- Upgrading is an explicit edit-and-deploy: change the tag in
  `config.yaml`, run `task deploy`.
- Caddy itself uses the official `caddy:2` image — minor versions roll
  forward. If that ever bites, pin it too.

## Out of scope (explicit non-decisions)

- **JupyterHub / per-user workspaces.** Ruled out at the user-model
  question. Single shared workspace is sufficient for the team size.
- **2FA, OIDC, SSO.** Basic auth at the Caddy edge is sufficient. If 2FA
  becomes necessary later, an Authelia sidecar can be added without
  changing the rest of the architecture.
- **Multi-VPS, HA, blue/green.** A single VPS is the design point.
- **CI/CD.** The operator runs `task deploy` from their laptop. There is
  no remote CI in this design.
- **Secrets vaulting.** `config.yaml` is gitignored on the operator's
  laptop. Adopting `sops + age` later is a drop-in replacement for the
  file-on-disk model and does not change the rest of the architecture.

---

## Amendment 2026-04-27 — auth at JupyterLab, not Caddy

**Problem with the original design:** HTTP Basic Auth at the Caddy edge
re-prompts on every request that doesn't carry the cached `Authorization`
header. On mobile browsers (iOS Safari, Android Chrome) this includes
JupyterLab's WebSocket upgrade requests for kernels, so the auth dialog
re-appears every time a notebook is opened — sometimes mid-session.
Desktop browsers cache more aggressively and don't show the bug.

**Change:** Auth moves from the Caddy edge into JupyterLab itself.

- `compose/Caddyfile.tmpl` no longer contains a `basic_auth` block. Caddy
  is reduced to TLS termination + reverse_proxy.
- JupyterLab runs with `--ServerApp.password=<sha1:salt:digest>` (the
  format JupyterLab's `passwd_check` accepts). The hash is stored in
  `config.yaml` at `jupyter.password_hash` and rendered into the compose
  file at deploy time.
- One shared password for the whole team. Per-user identity is given up
  in exchange for a session-cookie auth flow that works on mobile.
- The hash is generated locally with `openssl` only — no extra prereq.

**Taskfile changes:** `secrets:add-user`, `secrets:set-user-password`,
`secrets:rm-user` are removed; replaced by `secrets:set-jupyter-password`
(prompts twice, hashes, writes to `config.yaml`). Chisel-related secrets
tasks are unchanged.

**Validation rule changes:** the `caddy_users` array is gone. Validation
now requires `jupyter.password_hash` to match `^sha1:[0-9a-f]+:[0-9a-f]{40}$`.

**Threat-model note:** SHA-1 with random salt is weaker than argon2 against
offline brute-force, but the server is behind real public-CA TLS, the
basic-auth user-set is "the team", and the password is not reused; argon2
would have required adding `jupyter_server` Python or a Docker invocation
as an operator-laptop prereq. If the threat model tightens later, swap in
an argon2 hasher behind the same `task secrets:set-jupyter-password` UX —
JupyterLab accepts both formats.
