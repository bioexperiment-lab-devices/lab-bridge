# Security model

This page is for auditors and operators who need to understand where lab-bridge's trust boundaries sit, what each one assumes, and how the long-lived secrets are managed. The deployment surface is intentionally small: a single VPS hosting one Caddy edge, one chisel server, and a handful of internal services on a private Docker network. Everything sensitive lives behind one of those two ingress points.

## No inbound ports on the lab network

The lab PC initiates the only network connection — a single outbound TCP session from SerialHop to the VPS chisel port. The lab network never accepts an inbound connection from the internet, so institutional firewalls do not need a hole punched, no port-forwarding rule is required on a campus router, and the lab does not need a static public IP. The single trust assumption is that the lab PC is allowed to make outbound TCP to the VPS chisel port; every site onboarded so far satisfies this by default.

## Chisel auth

The chisel server enforces a per-client `user`/`pass` allowlist. The list is rendered from `chisel_clients` in `config.yaml` via `compose/chisel-users.json.tmpl`; on the VPS the rendered file lives at `<stack-root>/chisel/users.json` and is mounted into the chisel container read-only. Per-lab credentials are minted with `task secrets:add-client`, which appends the entry to `chisel_clients` in `config.yaml` and prints the `chisel client` invocation for the operator to run on the lab PC (or paste into `SerialHop_config.yaml`). Rotation: re-run `task secrets:add-client` to issue fresh creds (deleting the old entry from `config.yaml` first if you want a hard cutover), then `task deploy` re-renders the allowlist on the VPS.

## Bearer tokens

- **Agent upload token** — protects `/api/agent/upload` on siteapp; consumed by the SerialHop release CI when it publishes a new agent build for `/download/agent`. Rotated with `task secrets:rotate-agent-upload-token`.
- **Flasher upload token** — protects firmware upload into `/flash/`; consumed by device-firmware CI and by manufacturers who push official images. Rotated with `task secrets:rotate-flasher-upload-token`.

Both tokens are static bearer credentials. Anyone holding the value can call the corresponding endpoint, so they live in CI secret stores on the consumer side and in `config.yaml` (laptop) plus matching GitHub Actions secrets (server side).

## TLS

Caddy obtains and renews Let's Encrypt certificates automatically on 80/443. There is no manual cert lifecycle to manage. Internal services have no public ports — Loki, Prometheus, Grafana, Authelia, siteapp, Flasher, and JupyterLab are reachable only via Caddy or via container DNS inside `labnet`.

## Secret split

Instance secrets — the Grafana admin password, Authelia signing keys, the chisel allowlist — live in two places that must stay in sync. The laptop holds the authoritative copy in `config.yaml` (gitignored, never checked in). GitHub Actions holds the same values as repository secrets so CI deploys can render the templates on the VPS. Sync is manual: when a secret rotates on the laptop, the matching GH Actions secret has to be updated by hand, or the next CI deploy will fail with mismatched values. The full deploy procedure is at [admin deploy](/docs/admin/deploy).

## Audit harness

`tests/security/` holds a pytest-based black-box probe suite. The driver is `scripts/security_audit.sh`, which runs the suite against a live deployment — typically preprod at `https://111.88.145.138/` — without needing source access on the target. The probes cover auth-bypass, header-smuggling, info-disclosure, and similar OWASP-shaped checks. Each run produces a timestamped report; the latest is in `docs/security/` in the repo, with a written remediation plan for every finding.
