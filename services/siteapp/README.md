# siteapp

Tiny FastAPI service serving the lab-bridge VPS public surface:

- **`/docs/*`** — public Markdown docs, read-only from a mounted
  `public_docs/` (deployed by the `deploy-public-docs` CI workflow).
- **`/download/agent`** + **`/download/agent/windows/agent.exe`** —
  Windows-agent download page and binary.
- **`/api/agent/upload`** — bearer-token-auth upload endpoint used by
  SerialHop CI to publish a new agent build.
- **`/api/clients/`** — internal chisel-client roster (consumed by
  Jupyter notebooks running on the same VPS).
- **`/api/public/clients/{username}`**, **`/api/public/health`**,
  **`/api/public/server-info`** — SerialHop agent bootstrap APIs.

See `docs/superpowers/specs/2026-05-01-public-docs-and-agent-downloads-design.md`
for the original design and `docs/superpowers/specs/2026-05-16-siteapp-simplification-design.md`
for the admin-removal / docs-as-code rework.

## Local development

```bash
cd services/siteapp
uv sync
SITE_DATA=$(pwd)/sample_data \
SITEAPP_DOCS_DIR=$(pwd)/../../public_docs \
SITEAPP_CLIENTS_FILE=$(pwd)/sample_data/clients.json \
SITEAPP_CHISEL_LISTEN_PORT=8080 \
  uv run uvicorn app.main:app --reload
```
