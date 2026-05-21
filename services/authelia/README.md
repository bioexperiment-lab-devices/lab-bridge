# services/authelia

Authelia identity provider for lab-bridge. Single-factor (username + password),
file-backed users, two fixed groups (`admins`, `researchers`).

See `docs/superpowers/specs/2026-05-20-unified-authelia-auth-design.md` for the
overall design.

## Building locally

```bash
bash services/authelia/build.sh
```

Pushes `${AUTHELIA_IMAGE_REPO}:$(cat VERSION)` to GHCR.

## E2E tests

```bash
cd services/authelia && uv run pytest tests/e2e/
```

The fixture compose file spins up an Authelia container with a seeded users
file. Each test hits the container directly over HTTP.

## User management

Out-of-band, via the platform:

```bash
task users:add USER
task users:rm USER
task users:set-password USER
task users:set-groups USER
task users:list
```
