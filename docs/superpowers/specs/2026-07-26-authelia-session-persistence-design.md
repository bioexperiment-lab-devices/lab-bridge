# Authelia session persistence — design

**Status:** implemented
**Date:** 2026-07-26
**Fixes:** users are logged out on every deploy, and repeatedly during a working
session, even with "Keep me signed in" ticked.

## Symptom

> lab-bridge platform logs me out about every 15 minutes and on each redeploy no
> matter if "keep me signed in" is selected.

## Root cause

Authelia stores sessions **in the container's memory**. `session.redis` was never
configured, and Authelia 4.38 has exactly two session providers: in-memory
(default) and Redis. `storage.local` (`/data/db.sqlite3`) persists *user* data —
2FA devices, identity records — **not sessions**, so the `authelia_data` volume
does not help.

`scripts/deploy.sh` then bounces Authelia on every full deploy:

```sh
restart_services="caddy siteapp"
...
if [[ "${LDS_STACK_ONLY:-}" != "1" ]]; then
    restart_services+=" chisel authelia"      # deploy.sh:217-219
fi
... && docker compose restart $restart_services   # deploy.sh:220
```

That restart is legitimate — a single-file bind mount pins the original inode, so
a rsynced `configuration.yml` / `users_database.yml` is invisible to the running
process until it restarts. The bug is that restarting Authelia also **destroys
every session**, remembered or not.

Both reported symptoms are the same root cause:

- **"on each redeploy"** — every `task deploy` restarts Authelia → sessions wiped.
- **"about every 15 minutes"** — that *is* the deploy cadence during active work.
  Deploys observed on the preprod box on 2026-07-26: 02:41, 05:30, 05:36 (the last
  two six minutes apart). Each rsync at `/srv/lab-bridge` is immediately followed
  by an Authelia restart (`Created` unchanged, `StartedAt` advanced).

### Evidence: "keep me signed in" was never the problem

Measured against a throwaway `authelia/authelia:4.38.10` container with the
production config and shortened timers (`expiration: 2m`, `inactivity: 20s`,
`remember_me_duration: 2160h`):

| Scenario | Result |
| --- | --- |
| `keepMeLoggedIn=true`, idle past `inactivity` | **200** — remember-me bypasses inactivity |
| `keepMeLoggedIn=true`, idle past `expiration` | **200** — remember-me overrides expiration |
| `keepMeLoggedIn=false`, idle past `inactivity` | 401 — correct, by design |
| `keepMeLoggedIn=true`, after container restart | **401** — session lost |
| `Set-Cookie` with `keepMeLoggedIn=true` | `expires=` **+90 days**, persistent |

So the deprecated-but-auto-mapped `session.remember_me_duration` key works, the
cookie really is a 90-day persistent cookie, and the browser keeps sending it —
`/api/auth/whoami` 401s in the production log prove the browser presented a
cookie that the server no longer recognised. The client path is correct too:
`login.html` sends `keepMeLoggedIn: rememberEl.checked` (checked by default) and
the deployed siteapp forwards it verbatim (`auth.py:69`).

**Only a restart can end a remembered session.** Nothing else in the config can.

## Fix

Give Authelia a Redis-backed session store so sessions outlive the container.

1. **`redis` compose service** — `docker.io/library/redis:7.4-alpine`, pinned in
   `compose/images.yaml` (externally-released image, Renovate-managed), on
   `labnet`, **no published port**. `--appendonly yes` + a `./redis_data` bind
   mount so sessions also survive a Redis restart or host reboot.
2. **`session.redis`** in `services/authelia/config/configuration.yml.tmpl`
   pointing at `redis:6379`.
3. **`depends_on: redis: condition: service_healthy`** on authelia — Authelia
   exits at startup if its session provider is unreachable, so ordering matters
   on a cold `docker compose up`.

`deploy.sh` is deliberately **not** changed: restarting Authelia to pick up new
config/users files is correct behaviour, and once sessions live in Redis a
restart is no longer a logout event.

### Why not a Redis password

Redis is reachable only from `labnet`; no port is published to the host, and the
compose network is not shared with anything outside the stack. Adding a password
would mean another dual-managed secret (laptop + GH secret) for no reachable
attack surface. If Redis ever gets published or shared, add
`session.redis.password` with a docker secret at that point.

## Scope of session loss after this change

| Event | Sessions survive? |
| --- | --- |
| `task deploy` (full, laptop) | yes |
| CI stack-only deploy | yes |
| Authelia image bump / container recreate | yes |
| Redis container restart | yes (AOF) |
| `docker compose down -v` / volume wipe | no — by design |
| Session secret rotation | no — by design |

## Two bugs the new service surfaced

Adding redis was not self-contained — it tripped two latent assumptions in the
platform, both caught by CI rather than by review:

1. **`filter_compose` mangled the long-form `depends_on`.** It pruned every
   `depends_on` with `map(select(. != name))`, which is right for the short form
   (a sequence of names) but not the long form (a map keyed by name). yq's
   `map()` over a mapping returns a sequence of its *values*, so authelia's
   `depends_on: {redis: {condition: service_healthy}}` came out as
   `depends_on: [{condition: service_healthy}]` — invalid compose. Any instance
   with a non-empty `disabled_services` would have failed to come up. Latent
   until now: this is the file's first long-form `depends_on`. Fixed by
   branching on the node tag and using `with_entries` for the map form.

2. **`rsync --delete` wiped `redis_data`.** Every other runtime data dir is in
   `deploy.sh`'s exclude list; a new one is easy to forget. Without it the
   deploy deleted the session store mid-flight — redis went unhealthy and took
   authelia down with it — which would have reproduced the original bug through
   a different mechanism. There is now a cheap-tier test asserting the general
   invariant (every compose data bind-mount has a matching exclude), so the next
   service to add a volume cannot repeat it.

## Tests

- **Service e2e** (`services/authelia/tests/e2e/test_session_persistence.py`) —
  the behaviour test: log in with `keepMeLoggedIn`, restart the Authelia
  container, assert `/api/verify` still returns 200. Fails on `main` (401),
  passes with Redis. A companion test asserts a non-remembered session also
  survives, since Redis persistence is independent of remember-me.
- **Platform wiring** (`tests/integration/test_render.bats`) — the rendered
  compose emits a `redis` service with the pinned image and the rendered Authelia
  config points `session.redis.host` at it. Wiring only, per the three-tier rule.
