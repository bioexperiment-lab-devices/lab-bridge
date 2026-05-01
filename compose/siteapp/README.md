# siteapp

Tiny FastAPI service that serves public docs (`/docs/*`), the agent download
page (`/download/*`), and an admin upload UI (`/admin/*`) for the
`lab-bridge` VPS stack.

See `docs/superpowers/specs/2026-05-01-public-docs-and-agent-downloads-design.md`
for the design.

## Local development

```bash
cd compose/siteapp
uv sync
SITE_DATA=$(pwd)/sample_data uv run uvicorn app.main:app --reload
```
