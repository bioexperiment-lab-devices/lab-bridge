# streamer

Live WebRTC video streaming for lab-bridge. Ingests via WHIP from SerialHop,
fans out to browser viewers via WHEP.

- Wire protocol (SerialHop-facing): `docs/superpowers/specs/2026-05-24-serialhop-streaming-protocol.md`
- Server design: `docs/superpowers/specs/2026-05-24-video-streaming-design.md`

## Local dev

```bash
cd services/streamer
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

## Tests

```bash
uv run pytest              # unit
uv run pytest tests/e2e/   # e2e (needs Docker)
```
