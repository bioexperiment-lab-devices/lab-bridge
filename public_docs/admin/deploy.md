# Deploying lab-bridge

## When to deploy from a laptop

There are two situations that call for a laptop-driven deploy:

1. **First-time VPS bring-up** — the walkthrough below. Nothing exists on the VPS yet; the laptop renders templates, rsyncs the stack, and brings it up for the first time.
2. **Recovery from a degraded state** — a network outage interrupted a CI deploy, you need to roll a config change forward by hand, or the stack is partially down and you want a clean re-render. Day-to-day deploys land via CI on release-please tag creation; laptop deploys are the fallback.

## Prerequisites

- SSH access to the VPS, key-based, with no password prompts (`ssh <vps-host>` should drop you straight into a shell).
- `task`, `yq` v4 (the mikefarah build, not the python wrapper), `openssl`, `ssh`, and `rsync` installed on your laptop. `task doctor` checks for these.
- A copy of `config.yaml` filled in for this VPS — `cp config.example.yaml config.yaml`, then edit `vps.*`, `chisel.*`, retention, and instance name. `config.yaml` is gitignored on purpose.

## First-time bring-up

The full sequence from a clean checkout on your laptop to a running stack on the VPS:

```bash title="laptop"
task doctor
cp config.example.yaml config.yaml             # then edit VPS details, ports, retention
task secrets:set-grafana-password
task secrets:bootstrap-authelia
task users:add -- admin admins                 # bootstrap admin
task secrets:rotate-agent-upload-token
task secrets:rotate-flasher-upload-token
task provision
task deploy
```

Step by step:

1. **`task doctor`** checks that your laptop has every tool the rest of the flow assumes — `task`, `yq` v4, `openssl`, `ssh`, `rsync`. Fix anything it flags before moving on; the later steps will fail less helpfully.
2. **`cp config.example.yaml config.yaml`** seeds the instance config. Edit it: `vps.host` (public IPv4), `vps.ssh_user`, `chisel.listen_port`, `instance_name`, and the retention knobs for loki/site data. `chisel_clients` stays `[]` for now; you'll fill it in once labs come online (see [registering a new lab](/docs/admin/labs)).
3. **`task secrets:set-grafana-password`** prompts for the password you'll use to sign in to Grafana the first time as the built-in `admin` user. Written to `compose/grafana/admin_password` with mode 0600.
4. **`task secrets:bootstrap-authelia`** generates Authelia's runtime secrets — JWT key, session secret, storage encryption key, OIDC HMAC, the RSA JWKS, and the Grafana OIDC client secret. Run this once per VPS; pass `--rotate` later if you ever need to invalidate everything.
5. **`task users:add -- admin admins`** creates the bootstrap admin user in Authelia's user database and prompts for a password. The `admins` group is what unlocks Flasher and the Grafana Admin role; without an admin user you can't reach `/flash/*`.
6. **`task secrets:rotate-agent-upload-token`** mints a fresh bearer token for the `/api/agent/upload` endpoint that SerialHop's release CI uses to publish new agent builds. The token is printed once — store it in your CI secret manager (GitHub Actions: `AGENT_UPLOAD_TOKEN`).
7. **`task secrets:rotate-flasher-upload-token`** does the same for Flasher's firmware upload API. Store the printed token as `FLASHER_UPLOAD_TOKEN` in the device manufacturer's CI secret store.
8. **`task provision`** is the first-time-only VPS prep: creates the deploy directories under `/srv/lab-bridge/`, sets ownership, configures the firewall, and logs Docker into GHCR using your CI pull token. It's idempotent — safe to re-run.
9. **`task deploy`** renders the compose templates from `compose/*.tmpl` plus your `config.yaml`, rsyncs them to the VPS, and runs `docker compose up -d`. The first run pulls every image, so it takes a few minutes.

> [!IMPORTANT]
> `config.yaml` is gitignored on purpose. It carries the VPS hostname, the chisel client passwords, the Authelia bootstrap material, and the chisel client roster. **Never commit it.** If you need to share configuration between two admins, share the file over an out-of-band channel (1Password, encrypted vault), not git.

## Verification

After `task deploy` returns, sanity-check the stack from your laptop and a browser:

- **`task logs -- siteapp`** — tail the siteapp container logs. You should see a clean uvicorn startup and no traceback.
- Visit `https://<vps-host>/` in a browser. Sign in with the bootstrap admin you created in step 5; you should land on the home page with the team navbar.
- Visit `https://<vps-host>/docs/`. The sidebar should render the four sections from the root manifest (researcher, operator, admin, architecture).
- Visit `https://<vps-host>/grafana/`. Authelia gates the route; after sign-in Grafana should load with the Admin role (because your user is in `admins`).

## Day-to-day deploys via CI

Once the stack is up, you should not run `task deploy` for routine changes. The flow is:

- Open a PR against `main` with a Conventional Commit title (`feat(siteapp): …`, `fix(flasher): …`). The repo is squash-merge only.
- release-please maintains an open release PR with the next version bump. Merging that release PR cuts a `vX.Y.Z` tag.
- The tag triggers `.github/workflows/release-please.yml`, which builds the service images, pushes them to GHCR with Sigstore attestations, and deploys the stack to the VPS (`LDS_STACK_ONLY=1` — no chisel roster touch).
- You do not need to run `task deploy` for normal changes — CI handles it. The release PR itself runs full CI as the pre-deploy integration test gate.

## Recovery operations

When something is wrong on the VPS, these are the entry points:

- **`task logs -- <service>`** — tail the recent logs for one service (e.g. `task logs -- siteapp`, `task logs -- caddy`). For one-off deep dives use the service-specific variants `task ops:logs:siteapp`, `task ops:logs:loki`, `task ops:logs:grafana`, `task ops:logs:flasher`.
- **`task ops:loki-disk`** — show Loki's data directory size and the configured retention window. If logs disappeared earlier than you expected, retention is the first thing to check.
- **`task ssh`** drops you on the VPS. From there `docker compose -f /srv/lab-bridge/docker-compose.yml ps` gives the live state of every container; `docker compose -f /srv/lab-bridge/docker-compose.yml logs -f <service>` is the unwrapped version of `task logs`.
- **`task deploy:rollback -- v0.16.1`** triggers a CI rollback to a prior tag. Use this when a release is bad and you want CI to redeploy the previous good image set.
