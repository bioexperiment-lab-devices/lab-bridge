# Adding a new service

Step-by-step checklist for adding service N+1 to the lab-bridge stack. Follow the steps in order — later steps depend on earlier ones.

For the rationale behind this layout, see `docs/superpowers/specs/2026-05-15-per-service-isolation-design.md`. The invariants the new service must preserve are summarised in `CLAUDE.md` (section "Architecture philosophy").

## Mental model

A new service is a containerised app behind Caddy on the docker-compose stack. It owns:

- Its source tree at `services/<name>/`
- Its own version, changelog, image, CI workflow, release-please component, release-build job
- Its own service-level e2e harness (pytest + `docker compose`)

The platform (compose templates, scripts, integration tests) gets two small touches: a compose service definition + a Caddy route. **No other platform code needs to know about the new service.**

This walkthrough uses `<name>` as the placeholder for your service name (e.g. `notifier`, `metrics`). Keep names lowercase, single-word, dash-free.

## 1. Create the service tree

```
services/<name>/
  Dockerfile
  VERSION                       # "0.1.0 # x-release-please-version"
  CHANGELOG.md                  # "# Changelog\n" (release-please appends on bumps)
  pyproject.toml
  uv.lock
  build.sh                      # copy services/siteapp/build.sh and substitute
  .python-version
  .gitignore
  .dockerignore
  app/
    __init__.py
    main.py                     # FastAPI factory; expose /healthz at minimum
    config.py                   # env-var → Settings
    ...
  tests/
    __init__.py
    conftest.py
    test_*.py                   # unit tests (pytest)
    e2e/                        # service-level e2e — see step 6
```

Mirror `services/siteapp/` or `services/flasher/` as your reference depending on whether you need a SPA (flasher pattern) or just HTTP (siteapp pattern).

**Minimum contract for the service container:**

- Exposes `/healthz` returning 200 with `{"status": "ok"}` (used by `docker-compose` healthcheck + post-deploy probe).
- Reads `LAB_BRIDGE_VERSION` and `LAB_BRIDGE_GIT_SHA` env vars (set as build-args in CI) and surfaces them on `/healthz` or a `/version` endpoint.
- All configuration via env vars (no `config.yaml` lookup inside the container).

## 2. Add the service to `compose/docker-compose.yml.tmpl`

Insert a service block. Mirror the siteapp pattern:

```yaml
  <name>:
    image: __<NAME>_IMAGE__
    restart: unless-stopped
    environment:
      LAB_BRIDGE_VERSION: __LAB_BRIDGE_VERSION__   # optional, only if you want it visible to the app
      <NAME>_CLIENTS_FILE: /etc/<name>/clients.json    # if you need the chisel roster
      # ...other env vars
    volumes:
      - ./<name>/clients.json:/etc/<name>/clients.json:ro   # if needed
    networks: [labnet]
```

Also add `<name>` to Caddy's `depends_on` list at the top of the file.

## 3. Add a Caddy route in `compose/Caddyfile.tmpl`

Pick a public URL prefix (`/<name>/*`) and route it to the service. Use the existing `flasher` block as a template if you need basic_auth gating, or the `/api/public/*` block if it's an unauthenticated public route.

## 4. Render plumbing in `scripts/lib/render.sh`

Add a `_<name>_image()` function (copy `_siteapp_image`) and add `__<NAME>_IMAGE__` to the `render_compose` sed substitution list.

## 5. Deploy script touches

`scripts/deploy.sh`:

- Add `<name>` to `restart_services` if the service consumes a bind-mounted config file whose changes need an explicit container restart.
- Add a healthcheck probe in the route-reachability loop near line 117. For a basic_auth-gated route, expect `401` without creds; for a public route, expect `200`.

## 6. Service-level e2e harness

```
services/<name>/tests/e2e/
  __init__.py
  conftest.py           # session fixture: docker compose up -d --wait
  compose.yaml          # single-service compose for the harness (no Caddy, no chisel)
  fixtures/             # minimal test fixtures (rosters, tokens, etc.)
  test_*.py             # service-behavior tests via httpx against 127.0.0.1:<bound-port>
```

Mirror `services/siteapp/tests/e2e/` exactly. Key points:

- One container per test session (session-scoped pytest fixture).
- Stub upstream deps (chisel, SerialHop, etc.) with a tiny FastAPI app or `httpx` mocks. **Never reach the real stack from a service e2e.**
- Mark `pyproject.toml`'s `[tool.pytest.ini_options]` with `norecursedirs = ["tests/e2e"]` so default unit runs don't accidentally pick up the e2e suite.
- Image tag selection: read `<NAME>_TEST_IMAGE` env var (default `lab-bridge-<name>:e2e`). CI sets this to the just-built `lab-bridge-<name>:pr-<n>`.

## 7. Per-service CI workflow

Create `.github/workflows/pr-<name>.yml` by copying `pr-siteapp.yml` (no SPA) or `pr-flasher.yml` (has SPA build steps) and substituting paths.

Key rules:

- **No workflow-level `paths:` filter.** Always trigger on `pull_request`.
- Use `dorny/paths-filter@v3` internally; filter set must include `services/<name>/**` AND `.github/workflows/pr-<name>.yml`.
- Every substantive step gated by `if: steps.changed.outputs.src == 'true'`.
- Job ID = `<name>` (so required-check name is `pr-<name> / <name>`).
- Concurrency group: `pr-<name>-${{ github.event.pull_request.number }}` with `cancel-in-progress: true`.

## 8. release-please wiring

Add a package entry to `release-please-config.json`:

```json
"services/<name>": {
  "package-name": "<name>",
  "release-type": "simple",
  "include-component-in-tag": true,
  "tag-separator": "-",
  "extra-files": [
    { "type": "generic", "path": "VERSION" }
  ]
}
```

**Update the platform `.` package's `exclude-paths`** to include `services/<name>` — otherwise commits touching the new service would also bump platform:

```json
".": {
  ...
  "exclude-paths": ["services/siteapp", "services/flasher", "services/<name>"]
}
```

Add a matching entry to `.release-please-manifest.json`:

```json
"services/<name>": "0.1.0"
```

## 9. release-build job in `.github/workflows/release-please.yml`

Add a `release-build-<name>` job mirroring `release-build-siteapp`:

- `needs: release-please`
- `if: |
    (github.event_name == 'push' && needs.release-please.outputs.<name>_released == 'true')
    || (github.event_name == 'workflow_dispatch' && startsWith(github.event.inputs.rollback_to, '<name>-v'))`
- Resolve ref, checkout tag, GHCR login, buildx setup, build & push image at `ghcr.io/${{ github.repository_owner }}/lab-bridge-<name>:<version>`, attest provenance, call the composite action `./.github/actions/deploy-stack`.
- Decide on `verify_<thing>_version`: only siteapp's release surfaces version via `/api/public/server-info`. If your new service exposes a similar endpoint, pass its version through to the composite action so the deploy is verified post-merge.

Also add the corresponding outputs to the `release-please` job:

```yaml
<name>_released: ${{ steps.rp.outputs['services/<name>--release_created'] }}
<name>_tag:      ${{ steps.rp.outputs['services/<name>--tag_name'] }}
<name>_version:  ${{ steps.rp.outputs['services/<name>--version'] }}
```

## 10. pins.yaml + Taskfile

`compose/pins.yaml`: add `<name>_image_repo: ghcr.io/<owner>/lab-bridge-<name>`.

`Taskfile.yml`: add a `<name>:build-and-push` task (mirror `siteapp:build-and-push`) and an `ops:logs:<name>` task.

## 11. Integration tier touches (light)

If the new service is on the public Caddy surface, add ONE routing assertion to `tests/integration/test_routes_smoke.bats`:

```bash
@test "/<name>/ routes correctly" {
    code="$(_through_caddy 'https://127.0.0.1/<name>/')"
    [[ "$code" == "200" || "$code" == "401" ]] || { echo "got: $code"; false; }
}
```

**Do not add a new bats file for service-behavior tests.** That tier exists only for cross-service wiring; behavior tests belong in `services/<name>/tests/e2e/`.

If the new service has fake-VPS-driven tests (rare), add a matrix cell in `pr-platform.yml`'s `bats` job:

```yaml
- suite: <name>
  files: tests/integration/test_<name>.bats
```

And remember the `compose_images_available` skip pattern in the bats file's `setup_file()`.

## 12. Helpers and image loading

If `test_deploy.bats` / `test_ops.bats` / `test_routes_smoke.bats` need the new service's image inside the fake-VPS:

- `tests/integration/helpers.bash`: add `load_<name>_test_image()` mirroring `load_siteapp_test_image()`.
- Each fake-VPS-bringing bats file's `setup_file()`: call the loader.

## 13. CLAUDE.md path-rule check

Anything in `CLAUDE.md` that enumerates per-service items (e.g. workflow names, e2e locations)? Update in the same PR to include the new service. The "Architecture philosophy" section should not need touching — it's pattern-based, not service-enumerated.

## 14. Branch protection (manual GitHub UI step, post-merge)

Once the PR adding the service lands, update branch protection on `main`:

- **Add required check:** `pr-<name> / <name>`

The PR's description should call this out so the operator does it immediately after merge.

## What you should NOT do

- **Don't put service source under `compose/<name>/`.** The old layout. Migration in `2026-05-15-per-service-isolation-design.md` deliberately moved away from this.
- **Don't add fake-VPS-stack tests for service behavior.** They belong in service e2e.
- **Don't share `setup_file` across bats files.** Each bats file is its own lifecycle; matrix parallelism gives you cheap per-file fake-VPS bring-ups.
- **Don't combine release PRs across services.** `separate-pull-requests: true` is load-bearing.
- **Don't add a workflow-level `paths:` filter** on `pr-<name>.yml`. Required checks must always report; internal step gating gives you the same skip behavior without breaking branch protection.
- **Don't manually bump VERSION files or push release-tagged images.** release-please owns those.

## Reference services

- `services/siteapp/` — HTTP + docs portal + admin upload. Has CSRF, basic_auth (Caddy edge), bearer-token API. Reference for: pure HTTP service.
- `services/flasher/` — HTTP + React SPA + upstream HTTP client (SerialHop) + job tracker. Reference for: SPA-bearing service + stub-upstream e2e pattern.
