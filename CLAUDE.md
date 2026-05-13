# CLAUDE.md — development flow rules

Non-obvious rules for this repo. Operational how-tos live in README; CI mechanics are in `.github/workflows/`.

Design + plan docs:
- `docs/superpowers/specs/2026-05-12-cicd-design.md`
- `docs/superpowers/plans/2026-05-12-cicd.md`

## Branch & release rules

- **`main` is protected. Squash-merge only, linear history.** No direct pushes, no merge-commit, no rebase-merge — release-please depends on squash. Required checks: `pr-title`, `verify`.
- **PR titles follow Conventional Commits** (`feat fix chore docs refactor test perf build ci revert`, scope optional). The title becomes the squash subject and is what release-please scans for the version bump.
- **Don't bump versions by hand.** release-please owns `compose/siteapp/VERSION`. Don't strip the `# x-release-please-version` annotation — it's the rewrite anchor.
- **Don't manually push release-tagged images to GHCR.** CI is the only path; manual pushes break the Sigstore attestation.

## Config split

- **Image pins, paths, ports, retention → `compose/pins.yaml`** (tracked). Not `config.yaml`.
- **Instance values + secrets + chisel roster → `config.yaml`** (gitignored, laptop only).
- **`compose/config.ci.yaml.tmpl`'s `chisel_clients` MUST stay `[]`.** The vault guard (`LDS_REQUIRE_VAULT=1`) fails the CI deploy if non-empty.

## Laptop vs CI surface

- **Roster ops (`task secrets:add-client`, etc.) are laptop-only.** CI never renders `chisel/users.json` or `siteapp/clients.json`; it rsyncs with those excluded and skips chisel restart.
- **CI deploys stack-only** on release-please tag creation (`LDS_STACK_ONLY=1`). Don't invoke `task deploy` from CI — the workflow already calls `scripts/deploy.sh` with the right env.
- **Secrets are dual-managed.** Laptop sets the value (`task secrets:set-*`); the matching GH secret must be updated by hand or the next CI deploy fails. No automatic sync.

## Testing

- **`verify` is path-gated** via `dorny/paths-filter@v3` — docs-only PRs skip all expensive steps. If you change `pr.yml`, everything re-runs.
- **siteapp bats suites (`tests/test_siteapp_*.bats`) are NOT run in CI** (too slow — each does a full fake-VPS deploy). If you touch `compose/siteapp/` routing/auth/upload/safety, run them locally before opening the PR:
  ```bash
  bats tests/test_siteapp_auth.bats tests/test_siteapp_routing.bats \
       tests/test_siteapp_safety.bats tests/test_siteapp_uploads.bats
  ```
- **Don't change `pr.yml`'s required checks** without updating branch protection's required-checks list in lockstep.

## Server-info API

Additive fields to `/api/public/server-info` are safe (Go client tolerates unknown keys). Document additions in `docs/superpowers/specs/2026-05-11-server-info-client-spec.md` in the same PR. Breaking changes require a major bump + client coordination.

## Spec/plan workflow

Anything touching more than 2–3 files: brainstorming → `docs/superpowers/specs/` → `docs/superpowers/plans/` → subagent-driven execution with two-stage review. The 2026-05-12 CI/CD overhaul is the canonical example.
