# caddy

Custom Caddy build for lab-bridge: stock Caddy plus the
[`caddyserver/replace-response`](https://github.com/caddyserver/replace-response)
plugin, which Caddy uses to inject the platform navbar `<script>` tag on
every `text/html` response.

## Why custom?

Stock `caddy:2` cannot rewrite response bodies. The platform navbar is
delivered as a single JS bundle (`compose/shell/navbar.js`) and injected
into every HTML page via `replace-response`. The plugin must be compiled
into the Caddy binary at build time.

## Bumping the plugin

The plugin version is pinned in `Dockerfile` via `REPLACE_RESPONSE_VERSION`.
Renovate raises PRs when new tags appear; `tests/e2e/` exercises the
injection path so regressions surface before merge.

## Running e2e locally

From the repo root:

    docker build -t lab-bridge-caddy:e2e services/caddy

Then, from `services/caddy/`:

    uv sync
    uv run pytest tests/e2e/ -v
