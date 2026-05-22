# Administrator guide

This section is for the server administrator who runs the lab-bridge VPS itself. The admin surface is small and deliberately laptop-driven: a `Taskfile.yml` at the repo root wraps every operation as a `task <name>` command, and an instance-local `config.yaml` (gitignored) carries the VPS hostname, retention knobs, secrets, and the chisel client roster. Day-to-day deploys land via CI on every release-please tag — laptop deploys are reserved for first-time VPS bring-up and recovery from a degraded state.

For how the pieces fit together (Caddy at the edge, Authelia gating protected routes, chisel multiplexing lab tunnels, Grafana provisioned against Loki and Prometheus) see [architecture](/docs/architecture/).

## Reading order

These pages are written to be read in order on a first pass. After that, treat them as reference.

- [Deploying lab-bridge](/docs/admin/deploy) — first-time VPS bring-up and how day-to-day deploys land via CI.
- [Registering a new lab](/docs/admin/labs) — registering a new lab and issuing per-lab chisel credentials.
- [Users and groups](/docs/admin/users-and-groups) — adding users and the `admins` / `researchers` groups.
- [Grafana dashboards](/docs/admin/grafana) — the bundled dashboards and when to look at each.
- [Flashing device firmware](/docs/admin/flashing) — the firmware push UI and firmware ingestion via the upload API.

## The Taskfile

Every admin operation is wrapped by a `task <name>` command — there are no bare shell scripts to run by hand. Run `task --list` from a fresh clone of the repo on your laptop to see the full menu.

Group prefixes used by this guide:

- `task doctor` — laptop prerequisite check.
- `task provision` — first-time VPS prep.
- `task deploy` — render + rsync + bring the stack up.
- `task secrets:*` — secret management (passwords, tokens, chisel credentials).
- `task users:*` — Authelia user management.
- `task ops:*` — logs and operational utilities.
