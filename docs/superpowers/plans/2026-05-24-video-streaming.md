# Video streaming (streamer service) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a new `streamer` service that ingests WebRTC video from SerialHop via WHIP, fans out to ≤3 viewers per stream via WHEP, with control plane riding the existing chisel reverse tunnel.

**Architecture:** Self-contained FastAPI + aiortc service at `services/streamer/`. Discovers armed translations by polling each lab's `/api/translations` over chisel. On first viewer arrival, issues a `start` command to SerialHop (chisel) and waits for the WHIP publisher to attach; debounces a `stop` command after the last viewer leaves. No siteapp coupling; Caddy exposes `/streamer/*` (Authelia-gated, except `/streamer/whip/*` which uses one-shot bearer tokens). UDP 50000-50100 mapped on the host for RTP. In-memory state only.

**Tech Stack:** Python 3.13, FastAPI, aiortc (PyAV + libsrtp + libavcodec), httpx, ulid-py, pytest-asyncio, Docker, Caddy 2, Authelia.

**Spec:** [`docs/superpowers/specs/2026-05-24-video-streaming-design.md`](../specs/2026-05-24-video-streaming-design.md)

**Reference services:** `services/siteapp/`, `services/flasher/`. Follow `docs/adding-a-service.md` for every step that has an existing template.

---

## Task 1: Write the SerialHop-facing protocol spec

A standalone reference document so SerialHop developers can implement against this protocol without reading the server-side implementation spec. Pure contract — no how-to.

**Files:**
- Create: `docs/superpowers/specs/2026-05-24-serialhop-streaming-protocol.md`

- [ ] **Step 1: Write the spec file**

Save the following content verbatim:

````markdown
# SerialHop video streaming protocol — reference

**Status:** stable contract (target lab-bridge v0.21+)
**Date:** 2026-05-24
**Audience:** SerialHop developers implementing the lab-side of video
streaming
**Related:**
- `docs/superpowers/specs/2026-05-24-video-streaming-design.md` (server-side
  implementation spec — not required reading for SerialHop devs)

This document defines every wire-level detail SerialHop needs to participate
in lab-bridge video streaming. If something is not in this document, it is
not part of the contract.

## Architectural picture

```
  ┌─ SerialHop (your code) ──────────┐
  │                                  │
  │  Local HTTP API (chisel-tunnel)  │     POST /start  ┌─ lab-bridge ──┐
  │   GET  /api/translations         │ ◄──────────────  │  streamer     │
  │   POST /api/translations/{id}/   │     POST /stop   │               │
  │        start                     │ ◄──────────────  │               │
  │   POST /api/translations/{id}/   │                  │               │
  │        stop                      │                  │               │
  │                                  │                  │               │
  │  WHIP publisher (outbound)       │ ──── WHIP ────►  │  /streamer/   │
  │   POST {whip_url}                │     SDP + RTP    │   whip/{sid}  │
  │   bearer = {whip_token}          │                  │               │
  │                                  │                  └───────────────┘
  │  Camera capture pipeline         │
  └──────────────────────────────────┘
```

Two communication channels:

1. **Control plane** — server → SerialHop, over the existing chisel reverse
   tunnel. SerialHop runs an HTTP server on its existing local port; lab-bridge
   reaches it as `http://chisel:<reverse_port>`.
2. **Media plane** — SerialHop → server, direct outbound HTTPS+UDP to the
   lab-bridge public address. WebRTC over UDP for media; WHIP signaling over
   HTTPS.

There is no SerialHop-initiated connection on the control plane. SerialHop
does not poll, does not push events, does not maintain a websocket. It only
*responds* to control requests and *initiates* WHIP media publishes.

## 1. Control plane — HTTP endpoints SerialHop must serve

All three endpoints are served on the chisel-tunnel port. They are
**unauthenticated**: trust is the chisel-tunnel scope (only lab-bridge
containers can reach them, and SerialHop already authenticated to chisel
with its client password). Do not implement bearer/basic auth on these.

Content type: `application/json` for all request and response bodies.

### 1.1 `GET /api/translations`

Returns the set of currently-armed translations (cameras the operator has
toggled "Allow streaming" on).

**Request:** none.

**Response 200:**
```json
{
  "translations": [
    { "id": "cam-0", "label": "Microscope side view" },
    { "id": "cam-1", "label": "Plate reader top" }
  ]
}
```

- `translations`: array (may be empty).
- Each element: `{ "id": <string>, "label": <string> }`.
- `id`: stable identifier across SerialHop restarts. Required to be unique
  within this SerialHop. The combination `(chisel_username, id)` is the
  server-wide key.
- `label`: human-readable name shown to viewers.
- You **may** include additional fields per element; the server tolerates
  them and ignores unknown keys. Future spec versions may add fields
  (`has_audio`, `resolution_hint`, …); plan for this.

Translations that are configured but **not armed** must NOT appear in the
response.

**Failure semantics:** any non-200 response, timeout, or connection error is
treated by the server as "this lab has no translations". The lab card is
shown as inactive on the viewer picker. Aim to respond within 1 second.

### 1.2 `POST /api/translations/{id}/start`

The server calls this when the first viewer arrives for translation `{id}`.

**Request body:**
```json
{
  "session_id":  "01HXYZ8K2NQM4R6V9P3T1W5Z7B",
  "whip_url":    "https://lab.example.com/streamer/whip/01HXYZ8K2NQM4R6V9P3T1W5Z7B",
  "whip_token":  "tk_F2k9q...base64url...",
  "ice_servers": []
}
```

| Field | Type | Meaning |
|---|---|---|
| `session_id` | ULID string | Opaque to SerialHop. Store it; you need it on stop (1.3) and to disambiguate sessions over time. A new `session_id` = a new session, even if `{id}` is the same. |
| `whip_url` | absolute HTTPS URL | The WHIP endpoint to POST your SDP offer to. Treat as opaque; do NOT parse or derive. |
| `whip_token` | string | One-shot bearer. Send as `Authorization: Bearer <whip_token>` on the WHIP POST. Single-use, ≤60 s validity. |
| `ice_servers` | array of `RTCIceServer` objects | STUN/TURN configuration for your WebRTC peer connection. May be empty (v1 ships `[]`). Pass through to `RTCPeerConnection` as-is. |

**Response codes:**

| Code | When |
|---|---|
| 202 Accepted | SerialHop will publish. Response body: empty or `{}`. SerialHop now opens WHIP (see Section 2). |
| 404 Not Found | `{id}` is unknown to SerialHop. Body: `{ "error": "unknown translation" }`. |
| 409 Conflict | `{id}` is already publishing under a different active session. **Do not start a new capture.** Response body: `{ "session_id": "<current>" }`. |
| 503 Service Unavailable | Camera busy / hardware failure. Body: `{ "error": "<human description>" }`. |

**Idempotency:** if you receive `start` with a `session_id` you already
recognise as the active session for `{id}`, respond 202 with empty body
(no-op). This handles client retries.

**Required SerialHop behaviour on 202:**

1. Persist `session_id` → `(camera, capture_state)` mapping until the
   matching stop arrives or the session ends.
2. Open the camera (or attach to an already-open capture).
3. Begin WHIP publish (Section 2). You have ≤10 seconds from 202 before
   the server times out and abandons the session.

### 1.3 `POST /api/translations/{id}/stop`

The server calls this after the last viewer leaves and a debounce window
(5 s) expires.

**Request body:**
```json
{ "session_id": "01HXYZ8K2NQM4R6V9P3T1W5Z7B" }
```

**Response codes:**

| Code | When |
|---|---|
| 204 No Content | Stopped (or already stopped — idempotent). |
| 409 Conflict | The provided `session_id` does NOT match the currently-active session for `{id}`. **You must ignore the stop.** Response body: `{ "active_session_id": "<current>" }`. |

**Why the 409 guard matters:** see this race —

```
streamer:                                  SerialHop:
  POST stop (sid=A) ────────╮               currently publishing A
                            │
  last viewer leaves                        ↓
  new viewer arrives                        ↓
  POST start (sid=B) ───────┼──►            stops A, starts publishing B
                            │
  (stale stop A arrives) ───╯               checks sid != B → 409, ignores
```

Without the guard the stale `stop` would kill `B`. With it, SerialHop
preserves the new session.

**Required SerialHop behaviour on 204:**

1. Close the WHIP peer connection (DELETE the WHIP resource — see 2.4).
2. Release the camera if no other translation uses it.
3. Drop the `session_id` → state mapping.

## 2. Media plane — WHIP publisher

SerialHop is a WHIP client (RFC 9725). On receipt of `start` (1.2 with 202),
SerialHop initiates a WebRTC publish to `whip_url`.

### 2.1 Connection setup

1. Construct an `RTCPeerConnection` (or your stack's equivalent), passing
   `ice_servers` from the start request as ICE configuration.
2. Add **one** video sender. The track source is the selected camera. Track
   direction: `sendonly`.
3. Do **not** add any audio sender in v1.
4. Generate an SDP offer.

### 2.2 Codec requirements (v1)

The server's WHEP subscribers (browsers) must be able to decode whatever
codec you negotiate. Supported codecs in v1, by priority preference:

1. **H.264 Constrained Baseline (profile-level-id=42e01f)** — preferred.
2. **VP8** — fallback.

Either is acceptable; offer both in the SDP and let SDP negotiation pick.
The server's answer will indicate the chosen codec. Resolution and framerate
are negotiated at the codec layer (no protocol-level constraint); reasonable
defaults are 1280×720 at 15-30 fps.

Bitrate: include a `b=AS:1500` (or equivalent) line for ~1.5 Mbps target.
Higher is fine if your uplink supports it.

### 2.3 Signaling — POST `{whip_url}`

```
POST {whip_url} HTTP/1.1
Authorization: Bearer {whip_token}
Content-Type: application/sdp
Content-Length: <…>

<SDP offer body>
```

**Response 201:**
```
HTTP/1.1 201 Created
Content-Type: application/sdp
Location: {whip_url}                 # echo of the request URL

<SDP answer body>
```

Apply the SDP answer as the remote description. ICE candidates are
exchanged in-SDP (no trickle ICE required in v1; full SDP is fine).

**Error responses on WHIP POST:**

| Code | Meaning | What to do |
|---|---|---|
| 401 Unauthorized | Bearer missing or wrong | Do not retry — the token is one-shot. Wait for a fresh `start`. |
| 404 Not Found | `session_id` unknown to server (e.g. server restarted between `start` and your WHIP arriving) | Drop the session locally; wait for a fresh `start`. |
| 410 Gone | Token already redeemed (replay) | Drop the session; wait for a fresh `start`. |
| 5xx | Server-side issue | Retry once with backoff; if still failing, drop the session. |

### 2.4 Tear-down — DELETE `{whip_url}`

When you want to stop publishing (received `stop`, or SerialHop is shutting
down), DELETE the WHIP resource:

```
DELETE {whip_url} HTTP/1.1
Authorization: Bearer {whip_token}
```

Response: `204 No Content` (or `404` if the server already cleaned up).

Then close the `RTCPeerConnection`.

### 2.5 ICE / NAT

The server is publicly addressable. Its ICE candidate set will contain
`<vps_public_ip>:<udp_port>/udp` host candidates in the 50000-50100 range.
Your outbound UDP from the lab network must be able to reach those ports.

You do not need to be reachable from the public internet. Your candidates
can be host (LAN) candidates plus optionally STUN-discovered server-reflexive
candidates if `ice_servers` contains a STUN URL. In v1, `ice_servers=[]` is
shipped; your peer connection will simply use host candidates.

Standard NAT pinhole behaviour: once you send a UDP packet to the server's
address:port from your private address:port, the NAT mapping holds for the
session's duration. Standard symmetric NATs are fine for outbound-initiated
flows.

### 2.6 Track lifecycle

- **Send the very first video frame within 5 seconds** of receiving the 201
  WHIP response, ideally as fast as possible. The server's viewers are
  blocked waiting for the first frame and the WHEP handler has a 10-second
  publish-ready timeout.
- Keep RTP flowing for the entire session lifetime. If your camera drops a
  frame, send a keyframe at the earliest opportunity to recover viewer
  decoders.
- Send a keyframe on subscribe (the server may relay a PLI/FIR to you;
  honour it). Some implementations periodically emit keyframes every 2-5 s
  — that's acceptable too.

## 3. Lifecycle from SerialHop's perspective

```
  operator arms cam-0
        │
        ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ /api/translations returns cam-0 in armed list (you owe this │
  │ until operator disarms)                                     │
  └─────────────────────────────────────────────────────────────┘
        │
        ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ server may call POST /api/translations/cam-0/start          │
  │   { session_id: A, whip_url: …, whip_token: … }             │
  │ respond 202                                                  │
  └─────────────────────────────────────────────────────────────┘
        │
        ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ open camera; POST {whip_url} with SDP offer; get answer      │
  │ stream video over WebRTC                                     │
  └─────────────────────────────────────────────────────────────┘
        │
        ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ at some later point: POST /api/translations/cam-0/stop       │
  │   { session_id: A }                                          │
  │ respond 204; DELETE {whip_url}; close PC; release camera     │
  └─────────────────────────────────────────────────────────────┘
        │
        ▼
  back to armed-but-idle (return in /api/translations again)
```

**Operator disarms while publishing:**
1. Stop returning cam-0 from `/api/translations`.
2. DELETE `{whip_url}` proactively.
3. Close the camera.
4. Drop `session_id` mapping.

The server will detect the dropped publisher via WebRTC connection state and
tear down subscribers. You do **not** need to notify the server out-of-band.

**Server restart while publishing:**

Your WHIP peer connection will detect failure (ICE failed / DTLS closed).
Treat this the same as "operator disarmed": DELETE `{whip_url}` (it will
likely 404, fine), close the PC, release the camera, drop state. Wait for a
fresh `start`.

## 4. Trust model

- **Control plane (1.1–1.3):** SerialHop accepts requests without auth on
  the chisel-tunnel port. The chisel reverse tunnel itself is the auth
  boundary — only lab-bridge containers can reach you, and the chisel
  daemon authenticated your tunnel with the password from chisel's
  `users.json`.
- **WHIP (2.3):** `Authorization: Bearer {whip_token}` is required. The
  token is bound to a single `session_id` and is single-use. Do not log
  whip tokens.

If a control-plane request arrives over a non-chisel transport (e.g.
SerialHop's local UI port is reachable from elsewhere), that's a SerialHop
misconfiguration; the protocol assumes the chisel-tunnel scope is the only
ingress.

## 5. What SerialHop must NOT do

- Do not open additional chisel tunnels for video. Media goes outbound to
  the lab-bridge public address; control rides the existing tunnel.
- Do not POST to `whip_url` more than once per `whip_token`. Replay = 410.
- Do not send audio in v1. Audio support is reserved for a future protocol
  version (this spec covers v1 only).
- Do not authenticate the control-plane endpoints (1.1–1.3) with bearer or
  basic auth — they are deliberately unauthenticated within the chisel
  scope.
- Do not poll the server for state. The server initiates every control
  action. Your only outbound HTTP to lab-bridge is the WHIP POST and DELETE.
- Do not persist `session_id`, `whip_url`, or `whip_token` across SerialHop
  restarts. They are per-session and become invalid on restart.

## 6. Versioning

This document describes **protocol v1**. Future changes will follow
additive semantics:

- New optional fields may be added to existing request/response bodies;
  SerialHop must tolerate unknown fields it doesn't understand.
- New endpoints may be added; SerialHop must respond 404 to any path not
  in this spec, and the server treats 404 as "feature unsupported".

If a future spec adds an `audio` field to `/api/translations` entries, a
SerialHop that ignores it remains correct for video-only streaming.

Breaking changes (incompatible response shapes, removed endpoints) will be
versioned via a request `X-Lab-Bridge-Protocol-Version` header; SerialHop
that does not understand the version should fall back to v1 behaviour.

## 7. Conformance checklist

A SerialHop implementation conforms to this spec if:

- [ ] `GET /api/translations` returns 200 with the documented shape; empty
      array when no translations are armed.
- [ ] `POST /api/translations/{id}/start` returns 202 for valid armed
      translations, 404 for unknown, 409 for already-publishing, 503 for
      hardware unavailable.
- [ ] On 202, WHIP publish begins within 10 seconds.
- [ ] WHIP uses `Authorization: Bearer {whip_token}` exactly once per
      session.
- [ ] SDP offer is sendonly video, H.264 or VP8.
- [ ] First video frame arrives within 5 seconds of WHIP 201.
- [ ] `POST /api/translations/{id}/stop` returns 204 for matching
      `session_id`, 409 for mismatched.
- [ ] On 204, DELETE `{whip_url}` and close the camera.
- [ ] Operator disarm proactively tears down publish + DELETEs `{whip_url}`.

````

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-05-24-serialhop-streaming-protocol.md
git commit -m "$(cat <<'EOF'
docs(streamer): SerialHop-facing protocol spec

Standalone reference for lab-side implementers. Defines the three control
endpoints, the WHIP publish behaviour, lifecycle, and the conformance
checklist — all without requiring readers to consult the server-side
implementation spec.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Scaffold the streamer service tree

Create the directory layout and minimal-runnable container per `docs/adding-a-service.md`. No business logic yet; just enough to build the image and serve `/healthz`.

**Files:**
- Create: `services/streamer/Dockerfile`
- Create: `services/streamer/pyproject.toml`
- Create: `services/streamer/.python-version`
- Create: `services/streamer/.gitignore`
- Create: `services/streamer/.dockerignore`
- Create: `services/streamer/README.md`
- Create: `services/streamer/build.sh`
- Create: `services/streamer/app/__init__.py`
- Create: `services/streamer/app/main.py`
- Create: `services/streamer/app/config.py`
- Create: `services/streamer/tests/__init__.py`
- Create: `services/streamer/tests/conftest.py`

- [ ] **Step 1: Write `services/streamer/.python-version`**

```
3.13
```

- [ ] **Step 2: Write `services/streamer/.gitignore`**

```
.venv/
.ruff_cache/
__pycache__/
*.pyc
```

- [ ] **Step 3: Write `services/streamer/.dockerignore`**

```
.venv/
.ruff_cache/
.pytest_cache/
__pycache__/
tests/
```

- [ ] **Step 4: Write `services/streamer/pyproject.toml`**

```toml
[project]
name = "streamer"
version = "0.1.0"
description = "Live WebRTC video streaming for lab-bridge."
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.115,<0.116",
    "uvicorn[standard]>=0.30,<0.31",
    "httpx>=0.27,<0.29",
    "aiortc>=1.9,<2.0",
    "python-ulid>=2.7,<3.0",
    "jinja2>=3.1,<4",
    "pydantic>=2.7,<3",
    "pydantic-settings>=2.4,<3",
]

[dependency-groups]
dev = [
    "pytest>=8.3,<9",
    "pytest-asyncio>=0.24,<0.25",
    "ruff>=0.6,<0.13",
    "respx>=0.21,<0.22",
]

[tool.pytest.ini_options]
addopts = "-q"
asyncio_mode = "auto"
norecursedirs = ["tests/e2e"]
pythonpath = ["tests/e2e"]

[tool.ruff]
line-length = 100
target-version = "py313"
```

- [ ] **Step 5: Write `services/streamer/app/__init__.py`**

Empty file.

- [ ] **Step 6: Write `services/streamer/app/config.py`**

```python
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration; populated from environment variables."""

    model_config = SettingsConfigDict(env_prefix="STREAMER_", env_file=None)

    clients_file: Path = Path("/etc/streamer/clients.json")
    chisel_host: str = "chisel"

    public_ip: str = "127.0.0.1"
    udp_port_range: str = "50000-50100"

    publish_ready_timeout_s: float = 10.0
    drain_debounce_s: float = 5.0
    discovery_cache_ttl_s: float = 10.0
    discovery_request_timeout_s: float = 1.0
    whip_token_validity_s: float = 60.0
    max_subscribers_per_session: int = 3

    lab_bridge_version: str = Field(default="dev", alias="LAB_BRIDGE_VERSION")
    lab_bridge_git_sha: str = Field(default="unknown", alias="LAB_BRIDGE_GIT_SHA")


def load_settings() -> Settings:
    return Settings()
```

- [ ] **Step 7: Write `services/streamer/app/main.py`**

```python
from __future__ import annotations

from fastapi import FastAPI

from app.config import load_settings

settings = load_settings()

app = FastAPI(title="lab-bridge streamer")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {
        "status": "ok",
        "version": settings.lab_bridge_version,
        "git_sha": settings.lab_bridge_git_sha,
    }
```

- [ ] **Step 8: Write `services/streamer/tests/__init__.py`**

Empty file.

- [ ] **Step 9: Write `services/streamer/tests/conftest.py`**

```python
"""Shared pytest configuration for unit tests."""
```

- [ ] **Step 10: Write `services/streamer/Dockerfile`**

```dockerfile
# syntax=docker/dockerfile:1.7
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# aiortc native deps: PyAV needs libav*, aiortc needs libsrtp + libvpx + libopus.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libavdevice59 libavfilter9 libavformat60 libavcodec60 libavutil58 \
    libswscale7 libswresample4 \
    libsrtp2-1 libopus0 libvpx7 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app

RUN useradd --uid 10001 --create-home streamer && \
    mkdir -p /data && \
    chown -R streamer:streamer /app /data
USER streamer

ENV PYTHONPATH=/app

ARG LAB_BRIDGE_VERSION=dev
ARG LAB_BRIDGE_GIT_SHA=unknown
ENV LAB_BRIDGE_VERSION=$LAB_BRIDGE_VERSION \
    LAB_BRIDGE_GIT_SHA=$LAB_BRIDGE_GIT_SHA

EXPOSE 8000
EXPOSE 50000-50100/udp
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
    CMD python -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').status==200 else 1)" || exit 1

CMD ["uv", "run", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 11: Write `services/streamer/build.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

VERSION="$(awk 'NF { print $1; exit }' "$REPO_ROOT/VERSION")"
GIT_SHA="$(git -C "$REPO_ROOT" rev-parse --short=7 HEAD 2>/dev/null || echo unknown)"

: "${STREAMER_IMAGE_REPO:=$(yq e '.streamer_image_repo' "$REPO_ROOT/compose/pins.yaml")}"
STREAMER_IMAGE="${STREAMER_IMAGE_REPO}:${VERSION}"

cd "$SCRIPT_DIR"
docker buildx build \
    --platform linux/amd64 \
    --build-arg "LAB_BRIDGE_VERSION=${VERSION}" \
    --build-arg "LAB_BRIDGE_GIT_SHA=${GIT_SHA}" \
    --tag "$STREAMER_IMAGE" \
    --push \
    .
echo
echo "Pushed $STREAMER_IMAGE"
echo "Version is managed by release-please — do not bump VERSION manually."
```

Make executable:

```bash
chmod +x services/streamer/build.sh
```

- [ ] **Step 12: Write `services/streamer/README.md`**

```markdown
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
```

- [ ] **Step 13: Generate `uv.lock`**

```bash
cd services/streamer && uv sync
```

- [ ] **Step 14: Sanity-check the scaffold**

```bash
cd services/streamer && uv run pytest -v
```

Expected: pytest discovers 0 tests, exits 0 ("no tests ran").

```bash
cd services/streamer && uv run python -c "from app.main import app; print('ok')"
```

Expected: `ok`.

- [ ] **Step 15: Commit**

```bash
git add services/streamer
git commit -m "$(cat <<'EOF'
feat(streamer): scaffold service tree

Minimal-runnable container with /healthz endpoint. Mirrors siteapp/flasher
layout per docs/adding-a-service.md. No business logic yet.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Roster loader (`roster.py`)

Parse `clients.json` into a `{lab_name → port}` map. Mirrors `services/siteapp/app/clients.py:load_roster` semantics.

**Files:**
- Create: `services/streamer/app/roster.py`
- Test: `services/streamer/tests/test_roster.py`

- [ ] **Step 1: Write the failing test**

`services/streamer/tests/test_roster.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.roster import load_roster


def _write(tmp_path: Path, content: object) -> Path:
    p = tmp_path / "clients.json"
    p.write_text(json.dumps(content), encoding="utf-8")
    return p


def test_load_roster_returns_name_to_port(tmp_path: Path) -> None:
    p = _write(tmp_path, {"alice": {"port": 8089}, "bob": {"port": 8090}})
    assert load_roster(p) == {"alice": 8089, "bob": 8090}


def test_load_roster_ignores_other_entry_fields(tmp_path: Path) -> None:
    p = _write(tmp_path, {"alice": {"port": 8089, "password_sha256": "abc"}})
    assert load_roster(p) == {"alice": 8089}


def test_load_roster_rejects_non_object_root(tmp_path: Path) -> None:
    p = _write(tmp_path, [{"alice": 1}])
    with pytest.raises(ValueError, match="JSON object"):
        load_roster(p)


def test_load_roster_rejects_non_object_entry(tmp_path: Path) -> None:
    p = _write(tmp_path, {"alice": 8089})
    with pytest.raises(ValueError, match="must be object"):
        load_roster(p)


def test_load_roster_rejects_bool_port(tmp_path: Path) -> None:
    p = _write(tmp_path, {"alice": {"port": True}})
    with pytest.raises(ValueError, match="port must be int"):
        load_roster(p)


def test_load_roster_rejects_str_port(tmp_path: Path) -> None:
    p = _write(tmp_path, {"alice": {"port": "8089"}})
    with pytest.raises(ValueError, match="port must be int"):
        load_roster(p)


def test_load_roster_missing_file_raises_oserror(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        load_roster(tmp_path / "nope.json")
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd services/streamer && uv run pytest tests/test_roster.py -v
```

Expected: ImportError / ModuleNotFoundError for `app.roster`.

- [ ] **Step 3: Write the implementation**

`services/streamer/app/roster.py`:

```python
"""Parse the rendered clients.json roster into a name → port map."""

from __future__ import annotations

import json
from pathlib import Path


def load_roster(path: Path) -> dict[str, int]:
    """Read clients.json and return {name: port}.

    Raises OSError on missing/unreadable file. Raises ValueError on
    malformed JSON or per-entry shape problems. Mirrors
    ``services/siteapp/app/clients.py:load_roster`` validation rules.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("clients.json must be a JSON object")
    out: dict[str, int] = {}
    for name, entry in raw.items():
        if not isinstance(entry, dict):
            raise ValueError(f"roster value must be object, got: {name}={entry!r}")
        port = entry.get("port")
        # bool is a subclass of int — reject explicitly.
        if isinstance(port, bool) or not isinstance(port, int):
            raise ValueError(f"roster port must be int, got: {name}.port={port!r}")
        out[name] = port
    return out
```

- [ ] **Step 4: Run tests, verify pass**

```bash
cd services/streamer && uv run pytest tests/test_roster.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add services/streamer/app/roster.py services/streamer/tests/test_roster.py
git commit -m "feat(streamer): roster loader for clients.json"
```

---

## Task 4: WHIP token generator (`tokens.py`)

One-shot bearer tokens for WHIP. Generate, validate, expire, burn.

**Files:**
- Create: `services/streamer/app/tokens.py`
- Test: `services/streamer/tests/test_tokens.py`

- [ ] **Step 1: Write the failing test**

`services/streamer/tests/test_tokens.py`:

```python
from __future__ import annotations

import time

import pytest

from app.tokens import WhipToken, generate_whip_token


def test_generate_returns_distinct_tokens() -> None:
    a = generate_whip_token(validity_s=60.0)
    b = generate_whip_token(validity_s=60.0)
    assert a.value != b.value
    assert a.value.startswith("tk_")
    assert len(a.value) > 30


def test_token_validates_correct_bearer() -> None:
    t = generate_whip_token(validity_s=60.0)
    assert t.matches(t.value) is True


def test_token_rejects_wrong_bearer() -> None:
    t = generate_whip_token(validity_s=60.0)
    assert t.matches("tk_wrong") is False


def test_token_rejects_after_burn() -> None:
    t = generate_whip_token(validity_s=60.0)
    t.burn()
    assert t.matches(t.value) is False


def test_token_burn_is_idempotent() -> None:
    t = generate_whip_token(validity_s=60.0)
    t.burn()
    t.burn()
    assert t.matches(t.value) is False


def test_token_rejects_after_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_now = [1000.0]
    monkeypatch.setattr("app.tokens.time.monotonic", lambda: fake_now[0])
    t = generate_whip_token(validity_s=60.0)
    fake_now[0] = 1059.9
    assert t.matches(t.value) is True
    fake_now[0] = 1060.1
    assert t.matches(t.value) is False


def test_token_constant_time_compare() -> None:
    # Smoke check that we use secrets.compare_digest under the hood:
    # different-length comparisons must not raise.
    t = generate_whip_token(validity_s=60.0)
    assert t.matches("") is False
    assert t.matches("tk_") is False
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd services/streamer && uv run pytest tests/test_tokens.py -v
```

Expected: ImportError for `app.tokens`.

- [ ] **Step 3: Write the implementation**

`services/streamer/app/tokens.py`:

```python
"""One-shot WHIP bearer tokens.

A token is generated server-side when a Session is created, sent to
SerialHop in the start command, and validated on the WHIP POST. After
first successful match the token is *burned* (cannot match again).
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass


_TOKEN_PREFIX = "tk_"


@dataclass
class WhipToken:
    value: str
    created_at: float
    validity_s: float
    _burned: bool = False

    def matches(self, candidate: str) -> bool:
        if self._burned:
            return False
        if time.monotonic() - self.created_at > self.validity_s:
            return False
        return secrets.compare_digest(self.value, candidate)

    def burn(self) -> None:
        self._burned = True

    @property
    def is_burned(self) -> bool:
        return self._burned


def generate_whip_token(*, validity_s: float) -> WhipToken:
    raw = secrets.token_urlsafe(32)
    return WhipToken(
        value=f"{_TOKEN_PREFIX}{raw}",
        created_at=time.monotonic(),
        validity_s=validity_s,
    )
```

- [ ] **Step 4: Run tests, verify pass**

```bash
cd services/streamer && uv run pytest tests/test_tokens.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add services/streamer/app/tokens.py services/streamer/tests/test_tokens.py
git commit -m "feat(streamer): one-shot WHIP token primitives"
```

---

## Task 5: Discovery (`discovery.py`)

Poll each lab's `/api/translations` over the chisel tunnel; cache with TTL; force-refresh on demand.

**Files:**
- Create: `services/streamer/app/discovery.py`
- Test: `services/streamer/tests/test_discovery.py`

- [ ] **Step 1: Write the failing test**

`services/streamer/tests/test_discovery.py`:

```python
from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from app.discovery import DiscoveryCache, TranslationDescriptor


def _make_cache(
    roster: dict[str, int],
    *,
    ttl_s: float = 10.0,
    request_timeout_s: float = 1.0,
) -> DiscoveryCache:
    return DiscoveryCache(
        roster=roster,
        chisel_host="chisel",
        ttl_s=ttl_s,
        request_timeout_s=request_timeout_s,
    )


@respx.mock
async def test_fetches_armed_translations_per_lab() -> None:
    respx.get("http://chisel:8089/api/translations").mock(
        return_value=httpx.Response(
            200,
            json={
                "translations": [
                    {"id": "cam-0", "label": "Side"},
                    {"id": "cam-1", "label": "Top"},
                ]
            },
        )
    )
    cache = _make_cache({"alice": 8089})

    result = await cache.list("alice")

    assert result == [
        TranslationDescriptor(id="cam-0", label="Side"),
        TranslationDescriptor(id="cam-1", label="Top"),
    ]


@respx.mock
async def test_unknown_lab_returns_empty() -> None:
    cache = _make_cache({"alice": 8089})
    assert await cache.list("ghost") == []


@respx.mock
async def test_lab_offline_returns_empty() -> None:
    respx.get("http://chisel:8089/api/translations").mock(
        side_effect=httpx.ConnectError("no tunnel")
    )
    cache = _make_cache({"alice": 8089})
    assert await cache.list("alice") == []


@respx.mock
async def test_lab_500_returns_empty() -> None:
    respx.get("http://chisel:8089/api/translations").mock(
        return_value=httpx.Response(500, text="boom")
    )
    cache = _make_cache({"alice": 8089})
    assert await cache.list("alice") == []


@respx.mock
async def test_results_cached_within_ttl() -> None:
    route = respx.get("http://chisel:8089/api/translations").mock(
        return_value=httpx.Response(
            200,
            json={"translations": [{"id": "cam-0", "label": "Side"}]},
        )
    )
    cache = _make_cache({"alice": 8089}, ttl_s=60.0)

    await cache.list("alice")
    await cache.list("alice")

    assert route.call_count == 1


@respx.mock
async def test_force_refresh_bypasses_cache() -> None:
    payloads = [
        {"translations": [{"id": "cam-0", "label": "Side"}]},
        {"translations": [{"id": "cam-0", "label": "Side"}, {"id": "cam-1", "label": "Top"}]},
    ]
    call_count = {"n": 0}

    def _handler(_request: httpx.Request) -> httpx.Response:
        idx = call_count["n"]
        call_count["n"] += 1
        return httpx.Response(200, json=payloads[min(idx, len(payloads) - 1)])

    respx.get("http://chisel:8089/api/translations").mock(side_effect=_handler)
    cache = _make_cache({"alice": 8089}, ttl_s=60.0)

    first = await cache.list("alice")
    refreshed = await cache.list("alice", force_refresh=True)

    assert len(first) == 1
    assert len(refreshed) == 2


@respx.mock
async def test_malformed_response_returns_empty() -> None:
    respx.get("http://chisel:8089/api/translations").mock(
        return_value=httpx.Response(200, text="not json")
    )
    cache = _make_cache({"alice": 8089})
    assert await cache.list("alice") == []


@respx.mock
async def test_translations_field_must_be_array() -> None:
    respx.get("http://chisel:8089/api/translations").mock(
        return_value=httpx.Response(200, json={"translations": "nope"})
    )
    cache = _make_cache({"alice": 8089})
    assert await cache.list("alice") == []
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd services/streamer && uv run pytest tests/test_discovery.py -v
```

Expected: ImportError for `app.discovery`.

- [ ] **Step 3: Write the implementation**

`services/streamer/app/discovery.py`:

```python
"""Per-lab discovery cache for armed translations.

For each lab in the roster, the cache periodically polls
``http://chisel:<port>/api/translations`` and returns the parsed list of
TranslationDescriptors. Any failure (connection error, non-200, malformed
body) is normalized to an empty list — that lab's card grays out on the
picker. Refresh is lazy: the cache is updated on read when stale, or
explicitly on force_refresh=True.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class TranslationDescriptor:
    id: str
    label: str


@dataclass
class _CacheEntry:
    fetched_at: float
    value: list[TranslationDescriptor]


class DiscoveryCache:
    def __init__(
        self,
        *,
        roster: dict[str, int],
        chisel_host: str,
        ttl_s: float,
        request_timeout_s: float,
    ) -> None:
        self._roster = roster
        self._host = chisel_host
        self._ttl_s = ttl_s
        self._timeout_s = request_timeout_s
        self._cache: dict[str, _CacheEntry] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def list(
        self, lab_name: str, *, force_refresh: bool = False
    ) -> list[TranslationDescriptor]:
        if lab_name not in self._roster:
            return []
        if not force_refresh:
            entry = self._cache.get(lab_name)
            if entry is not None and time.monotonic() - entry.fetched_at < self._ttl_s:
                return entry.value
        lock = self._locks.setdefault(lab_name, asyncio.Lock())
        async with lock:
            if not force_refresh:
                entry = self._cache.get(lab_name)
                if entry is not None and time.monotonic() - entry.fetched_at < self._ttl_s:
                    return entry.value
            value = await self._fetch(lab_name)
            self._cache[lab_name] = _CacheEntry(fetched_at=time.monotonic(), value=value)
            return value

    async def _fetch(self, lab_name: str) -> list[TranslationDescriptor]:
        port = self._roster[lab_name]
        url = f"http://{self._host}:{port}/api/translations"
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                resp = await client.get(url)
        except (httpx.HTTPError, OSError):
            return []
        if resp.status_code != 200:
            return []
        try:
            payload: Any = resp.json()
        except ValueError:
            return []
        if not isinstance(payload, dict):
            return []
        items = payload.get("translations")
        if not isinstance(items, list):
            return []
        out: list[TranslationDescriptor] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            tid = item.get("id")
            label = item.get("label")
            if not isinstance(tid, str) or not isinstance(label, str):
                continue
            out.append(TranslationDescriptor(id=tid, label=label))
        return out
```

- [ ] **Step 4: Run tests, verify pass**

```bash
cd services/streamer && uv run pytest tests/test_discovery.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add services/streamer/app/discovery.py services/streamer/tests/test_discovery.py
git commit -m "feat(streamer): per-lab translation discovery cache"
```

---

## Task 6: Control plane client (`control.py`)

Issue start/stop commands to SerialHop over the chisel reverse tunnel. Translates HTTP responses into typed exceptions.

**Files:**
- Create: `services/streamer/app/control.py`
- Test: `services/streamer/tests/test_control.py`

- [ ] **Step 1: Write the failing test**

`services/streamer/tests/test_control.py`:

```python
from __future__ import annotations

import httpx
import pytest
import respx

from app.control import (
    CameraBusy,
    ControlError,
    ControlPlaneClient,
    StartResult,
    UnknownTranslation,
)


def _client(roster: dict[str, int]) -> ControlPlaneClient:
    return ControlPlaneClient(
        roster=roster,
        chisel_host="chisel",
        request_timeout_s=2.0,
    )


@respx.mock
async def test_start_202_returns_started() -> None:
    route = respx.post("http://chisel:8089/api/translations/cam-0/start").mock(
        return_value=httpx.Response(202, json={})
    )
    result = await _client({"alice": 8089}).start(
        lab_name="alice",
        translation_id="cam-0",
        session_id="01ABC",
        whip_url="https://lab/streamer/whip/01ABC",
        whip_token="tk_xyz",
    )
    assert isinstance(result, StartResult)
    assert result.session_id == "01ABC"
    assert route.called
    req = route.calls[0].request
    body = httpx.Response(200, content=req.content).json()
    assert body == {
        "session_id": "01ABC",
        "whip_url": "https://lab/streamer/whip/01ABC",
        "whip_token": "tk_xyz",
        "ice_servers": [],
    }


@respx.mock
async def test_start_404_raises_unknown_translation() -> None:
    respx.post("http://chisel:8089/api/translations/ghost/start").mock(
        return_value=httpx.Response(404, json={"error": "unknown translation"})
    )
    with pytest.raises(UnknownTranslation):
        await _client({"alice": 8089}).start(
            lab_name="alice",
            translation_id="ghost",
            session_id="01",
            whip_url="https://lab/streamer/whip/01",
            whip_token="tk",
        )


@respx.mock
async def test_start_503_raises_camera_busy() -> None:
    respx.post("http://chisel:8089/api/translations/cam-0/start").mock(
        return_value=httpx.Response(503, json={"error": "camera busy"})
    )
    with pytest.raises(CameraBusy):
        await _client({"alice": 8089}).start(
            lab_name="alice",
            translation_id="cam-0",
            session_id="01",
            whip_url="https://lab/streamer/whip/01",
            whip_token="tk",
        )


@respx.mock
async def test_start_connection_error_raises_control_error() -> None:
    respx.post("http://chisel:8089/api/translations/cam-0/start").mock(
        side_effect=httpx.ConnectError("no tunnel")
    )
    with pytest.raises(ControlError):
        await _client({"alice": 8089}).start(
            lab_name="alice",
            translation_id="cam-0",
            session_id="01",
            whip_url="https://lab/streamer/whip/01",
            whip_token="tk",
        )


@respx.mock
async def test_start_unknown_lab_raises_control_error() -> None:
    with pytest.raises(ControlError, match="unknown lab"):
        await _client({"alice": 8089}).start(
            lab_name="ghost",
            translation_id="cam-0",
            session_id="01",
            whip_url="https://lab/streamer/whip/01",
            whip_token="tk",
        )


@respx.mock
async def test_stop_204_returns_silently() -> None:
    route = respx.post("http://chisel:8089/api/translations/cam-0/stop").mock(
        return_value=httpx.Response(204)
    )
    await _client({"alice": 8089}).stop(
        lab_name="alice", translation_id="cam-0", session_id="01"
    )
    assert route.called
    body = httpx.Response(200, content=route.calls[0].request.content).json()
    assert body == {"session_id": "01"}


@respx.mock
async def test_stop_409_returns_silently() -> None:
    # Stale stop is the server's problem; SerialHop ignoring it is correct.
    respx.post("http://chisel:8089/api/translations/cam-0/stop").mock(
        return_value=httpx.Response(409, json={"active_session_id": "02"})
    )
    await _client({"alice": 8089}).stop(
        lab_name="alice", translation_id="cam-0", session_id="01"
    )


@respx.mock
async def test_stop_connection_error_is_swallowed() -> None:
    # Best-effort: if the lab is gone, we can't reach it anyway.
    respx.post("http://chisel:8089/api/translations/cam-0/stop").mock(
        side_effect=httpx.ConnectError("no tunnel")
    )
    await _client({"alice": 8089}).stop(
        lab_name="alice", translation_id="cam-0", session_id="01"
    )
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd services/streamer && uv run pytest tests/test_control.py -v
```

Expected: ImportError for `app.control`.

- [ ] **Step 3: Write the implementation**

`services/streamer/app/control.py`:

```python
"""Issue start/stop commands to SerialHop over the chisel reverse tunnel."""

from __future__ import annotations

from dataclasses import dataclass

import httpx


class ControlError(Exception):
    """Generic control-plane failure (network, unknown lab, malformed reply)."""


class UnknownTranslation(ControlError):
    """SerialHop returned 404 — translation id not recognised."""


class CameraBusy(ControlError):
    """SerialHop returned 503 — camera hardware not available."""


@dataclass(frozen=True)
class StartResult:
    """Outcome of a successful start (202) or already-running (409)."""

    session_id: str


class ControlPlaneClient:
    def __init__(
        self,
        *,
        roster: dict[str, int],
        chisel_host: str,
        request_timeout_s: float,
    ) -> None:
        self._roster = roster
        self._host = chisel_host
        self._timeout_s = request_timeout_s

    async def start(
        self,
        *,
        lab_name: str,
        translation_id: str,
        session_id: str,
        whip_url: str,
        whip_token: str,
        ice_servers: list[dict[str, object]] | None = None,
    ) -> StartResult:
        url = self._url(lab_name, translation_id, "start")
        body = {
            "session_id": session_id,
            "whip_url": whip_url,
            "whip_token": whip_token,
            "ice_servers": list(ice_servers or []),
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                resp = await client.post(url, json=body)
        except (httpx.HTTPError, OSError) as exc:
            raise ControlError(f"start failed: {exc.__class__.__name__}") from exc

        if resp.status_code == 202:
            return StartResult(session_id=session_id)
        if resp.status_code == 404:
            raise UnknownTranslation(translation_id)
        if resp.status_code == 503:
            raise CameraBusy(translation_id)
        raise ControlError(f"unexpected start status: {resp.status_code}")

    async def stop(
        self, *, lab_name: str, translation_id: str, session_id: str
    ) -> None:
        url = self._url(lab_name, translation_id, "stop")
        body = {"session_id": session_id}
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                await client.post(url, json=body)
        except (httpx.HTTPError, OSError):
            # Best-effort: a lab that's gone can't be told anything anyway.
            return

    def _url(self, lab_name: str, translation_id: str, action: str) -> str:
        port = self._roster.get(lab_name)
        if port is None:
            raise ControlError(f"unknown lab: {lab_name}")
        return f"http://{self._host}:{port}/api/translations/{translation_id}/{action}"
```

- [ ] **Step 4: Run tests, verify pass**

```bash
cd services/streamer && uv run pytest tests/test_control.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add services/streamer/app/control.py services/streamer/tests/test_control.py
git commit -m "feat(streamer): chisel-tunnel control plane client"
```

---

## Task 7: Session manager state machine (`session_manager.py`)

In-memory state, lock-per-key for first-viewer race, debounced shutdown.

**Files:**
- Create: `services/streamer/app/session_manager.py`
- Test: `services/streamer/tests/test_session_manager.py`

- [ ] **Step 1: Write the failing test**

`services/streamer/tests/test_session_manager.py`:

```python
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.session_manager import Session, SessionManager, SessionState


@pytest.fixture
def manager() -> SessionManager:
    return SessionManager(whip_token_validity_s=60.0)


def test_create_session_yields_unique_session_id(manager: SessionManager) -> None:
    a = manager.create(lab_name="alice", translation_id="cam-0")
    b = manager.create(lab_name="alice", translation_id="cam-1")
    assert a.session_id != b.session_id


def test_create_session_initial_state_is_created(manager: SessionManager) -> None:
    s = manager.create(lab_name="alice", translation_id="cam-0")
    assert s.state == SessionState.CREATED
    assert s.publish_token is not None
    assert s.publisher_track is None


def test_get_returns_existing(manager: SessionManager) -> None:
    s = manager.create(lab_name="alice", translation_id="cam-0")
    assert manager.get("alice", "cam-0") is s


def test_get_returns_none_when_missing(manager: SessionManager) -> None:
    assert manager.get("alice", "cam-0") is None


def test_get_by_session_id(manager: SessionManager) -> None:
    s = manager.create(lab_name="alice", translation_id="cam-0")
    assert manager.get_by_session_id(s.session_id) is s


def test_get_by_session_id_returns_none_when_missing(manager: SessionManager) -> None:
    assert manager.get_by_session_id("01NOPE") is None


def test_drop_removes_session(manager: SessionManager) -> None:
    s = manager.create(lab_name="alice", translation_id="cam-0")
    manager.drop(s)
    assert manager.get("alice", "cam-0") is None
    assert manager.get_by_session_id(s.session_id) is None


def test_mark_publishing_transitions_state(manager: SessionManager) -> None:
    s = manager.create(lab_name="alice", translation_id="cam-0")
    s.mark_publishing(track=object())
    assert s.state == SessionState.PUBLISHING
    assert s.publisher_track is not None


def test_publish_ready_event_set_on_mark_publishing(manager: SessionManager) -> None:
    s = manager.create(lab_name="alice", translation_id="cam-0")
    assert not s.publish_ready.is_set()
    s.mark_publishing(track=object())
    assert s.publish_ready.is_set()


def test_subscriber_register_and_remove(manager: SessionManager) -> None:
    s = manager.create(lab_name="alice", translation_id="cam-0")
    s.mark_publishing(track=object())
    sub_id = s.add_subscriber(object())
    assert s.subscriber_count() == 1
    s.remove_subscriber(sub_id)
    assert s.subscriber_count() == 0


async def test_lock_serializes_concurrent_creates(manager: SessionManager) -> None:
    """Two concurrent first-viewer arrivals must result in one session."""
    started: list[str] = []

    async def viewer() -> None:
        async with manager.lock_for("alice", "cam-0"):
            existing = manager.get("alice", "cam-0")
            if existing is None:
                s = manager.create(lab_name="alice", translation_id="cam-0")
                started.append(s.session_id)
            await asyncio.sleep(0.01)

    await asyncio.gather(viewer(), viewer(), viewer())
    assert len(started) == 1
    assert manager.get("alice", "cam-0") is not None


async def test_drain_scheduling_emits_stop_after_debounce() -> None:
    fired: list[Session] = []

    async def _on_drain(session: Session) -> None:
        fired.append(session)

    manager = SessionManager(whip_token_validity_s=60.0)
    s = manager.create(lab_name="alice", translation_id="cam-0")
    s.mark_publishing(track=object())
    sub_id = s.add_subscriber(object())
    s.remove_subscriber(sub_id)

    manager.schedule_drain(s, debounce_s=0.05, on_expire=_on_drain)
    await asyncio.sleep(0.02)
    assert fired == []
    await asyncio.sleep(0.06)
    assert fired == [s]


async def test_drain_cancelled_by_new_subscriber() -> None:
    fired: list[Session] = []

    async def _on_drain(session: Session) -> None:
        fired.append(session)

    manager = SessionManager(whip_token_validity_s=60.0)
    s = manager.create(lab_name="alice", translation_id="cam-0")
    s.mark_publishing(track=object())
    sub_id = s.add_subscriber(object())
    s.remove_subscriber(sub_id)

    manager.schedule_drain(s, debounce_s=0.1, on_expire=_on_drain)
    await asyncio.sleep(0.02)
    manager.cancel_drain(s)
    s.add_subscriber(object())
    await asyncio.sleep(0.15)
    assert fired == []
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd services/streamer && uv run pytest tests/test_session_manager.py -v
```

Expected: ImportError for `app.session_manager`.

- [ ] **Step 3: Write the implementation**

`services/streamer/app/session_manager.py`:

```python
"""In-memory Session state with locks, transitions, and debounced shutdown."""

from __future__ import annotations

import asyncio
import enum
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from ulid import ULID

from app.tokens import WhipToken, generate_whip_token


class SessionState(enum.Enum):
    CREATED = "created"
    PUBLISHING = "publishing"
    DRAINING = "draining"


@dataclass
class Session:
    lab_name: str
    translation_id: str
    session_id: str
    publish_token: WhipToken
    state: SessionState = SessionState.CREATED
    publisher_pc: Any | None = None
    publisher_track: Any | None = None
    publish_ready: asyncio.Event = field(default_factory=asyncio.Event)
    subscribers: dict[str, Any] = field(default_factory=dict)

    def mark_publishing(self, *, track: Any) -> None:
        self.publisher_track = track
        self.state = SessionState.PUBLISHING
        self.publish_ready.set()

    def add_subscriber(self, pc: Any) -> str:
        sub_id = str(ULID())
        self.subscribers[sub_id] = pc
        return sub_id

    def remove_subscriber(self, sub_id: str) -> None:
        self.subscribers.pop(sub_id, None)

    def subscriber_count(self) -> int:
        return len(self.subscribers)


class SessionManager:
    """Owns the (lab, translation_id) → Session map and per-key locks."""

    def __init__(self, *, whip_token_validity_s: float) -> None:
        self._whip_token_validity_s = whip_token_validity_s
        self._sessions_by_key: dict[tuple[str, str], Session] = {}
        self._sessions_by_id: dict[str, Session] = {}
        self._locks: dict[tuple[str, str], asyncio.Lock] = {}
        self._drain_tasks: dict[str, asyncio.Task[None]] = {}

    def lock_for(self, lab_name: str, translation_id: str) -> asyncio.Lock:
        key = (lab_name, translation_id)
        return self._locks.setdefault(key, asyncio.Lock())

    def get(self, lab_name: str, translation_id: str) -> Session | None:
        return self._sessions_by_key.get((lab_name, translation_id))

    def get_by_session_id(self, session_id: str) -> Session | None:
        return self._sessions_by_id.get(session_id)

    def create(self, *, lab_name: str, translation_id: str) -> Session:
        session = Session(
            lab_name=lab_name,
            translation_id=translation_id,
            session_id=str(ULID()),
            publish_token=generate_whip_token(validity_s=self._whip_token_validity_s),
        )
        self._sessions_by_key[(lab_name, translation_id)] = session
        self._sessions_by_id[session.session_id] = session
        return session

    def drop(self, session: Session) -> None:
        self._sessions_by_key.pop((session.lab_name, session.translation_id), None)
        self._sessions_by_id.pop(session.session_id, None)
        task = self._drain_tasks.pop(session.session_id, None)
        if task is not None and not task.done():
            task.cancel()

    def schedule_drain(
        self,
        session: Session,
        *,
        debounce_s: float,
        on_expire: Callable[[Session], Awaitable[None]],
    ) -> None:
        self.cancel_drain(session)
        session.state = SessionState.DRAINING

        async def _runner() -> None:
            try:
                await asyncio.sleep(debounce_s)
            except asyncio.CancelledError:
                return
            await on_expire(session)

        self._drain_tasks[session.session_id] = asyncio.create_task(_runner())

    def cancel_drain(self, session: Session) -> None:
        task = self._drain_tasks.pop(session.session_id, None)
        if task is not None and not task.done():
            task.cancel()
```

- [ ] **Step 4: Run tests, verify pass**

```bash
cd services/streamer && uv run pytest tests/test_session_manager.py -v
```

Expected: 13 passed.

- [ ] **Step 5: Commit**

```bash
git add services/streamer/app/session_manager.py services/streamer/tests/test_session_manager.py
git commit -m "feat(streamer): session state machine"
```

---

## Task 8: Auth helper (`auth.py`)

Extract user + groups from Caddy/Authelia `Remote-*` headers; gate routes to researchers/admins.

**Files:**
- Create: `services/streamer/app/auth.py`
- Test: `services/streamer/tests/test_auth.py`

- [ ] **Step 1: Write the failing test**

`services/streamer/tests/test_auth.py`:

```python
from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.auth import RequiredGroupsDep, get_remote_identity


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/me")
    def me(identity=RequiredGroupsDep) -> dict[str, object]:
        return {"user": identity.user, "groups": identity.groups}

    return app


def test_identity_extracted_from_headers() -> None:
    client = TestClient(_app())
    r = client.get("/me", headers={"Remote-User": "alice", "Remote-Groups": "researchers,admins"})
    assert r.status_code == 200
    assert r.json() == {"user": "alice", "groups": ["researchers", "admins"]}


def test_missing_user_rejected() -> None:
    client = TestClient(_app())
    r = client.get("/me")
    assert r.status_code == 401


def test_user_without_required_group_rejected() -> None:
    client = TestClient(_app())
    r = client.get("/me", headers={"Remote-User": "alice", "Remote-Groups": "guests"})
    assert r.status_code == 403


def test_empty_groups_header_rejected() -> None:
    client = TestClient(_app())
    r = client.get("/me", headers={"Remote-User": "alice"})
    assert r.status_code == 403


def test_researcher_alone_allowed() -> None:
    client = TestClient(_app())
    r = client.get("/me", headers={"Remote-User": "bob", "Remote-Groups": "researchers"})
    assert r.status_code == 200
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd services/streamer && uv run pytest tests/test_auth.py -v
```

Expected: ImportError for `app.auth`.

- [ ] **Step 3: Write the implementation**

`services/streamer/app/auth.py`:

```python
"""Identity extraction from Caddy/Authelia forward_auth Remote-* headers."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException


_ALLOWED_GROUPS = {"researchers", "admins"}


@dataclass(frozen=True)
class Identity:
    user: str
    groups: list[str]


def get_remote_identity(
    remote_user: str | None = Header(default=None, alias="Remote-User"),
    remote_groups: str | None = Header(default=None, alias="Remote-Groups"),
) -> Identity:
    if not remote_user:
        raise HTTPException(status_code=401, detail="unauthenticated")
    groups = [g.strip() for g in (remote_groups or "").split(",") if g.strip()]
    if not (_ALLOWED_GROUPS & set(groups)):
        raise HTTPException(status_code=403, detail="forbidden")
    return Identity(user=remote_user, groups=groups)


RequiredGroupsDep = Depends(get_remote_identity)
```

- [ ] **Step 4: Run tests, verify pass**

```bash
cd services/streamer && uv run pytest tests/test_auth.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add services/streamer/app/auth.py services/streamer/tests/test_auth.py
git commit -m "feat(streamer): Authelia identity dependency"
```

---

## Task 9: SFU primitives (`sfu.py`)

Thin wrapper around aiortc for publisher and subscriber peer-connection creation. The deep behaviour (track forwarding, ICE) is exercised by the e2e suite; unit tests here cover ICE candidate hint plumbing only.

**Files:**
- Create: `services/streamer/app/sfu.py`
- Test: `services/streamer/tests/test_sfu.py`

- [ ] **Step 1: Write the failing test**

`services/streamer/tests/test_sfu.py`:

```python
from __future__ import annotations

import pytest

from app.sfu import (
    parse_udp_port_range,
    rewrite_sdp_with_public_ip,
)


def test_parse_udp_port_range() -> None:
    assert parse_udp_port_range("50000-50100") == (50000, 50100)


def test_parse_udp_port_range_rejects_single() -> None:
    with pytest.raises(ValueError):
        parse_udp_port_range("50000")


def test_parse_udp_port_range_rejects_inverted() -> None:
    with pytest.raises(ValueError):
        parse_udp_port_range("50100-50000")


def test_rewrite_sdp_replaces_internal_candidate_addresses() -> None:
    sdp = (
        "v=0\r\n"
        "a=candidate:1 1 udp 1 172.18.0.3 50001 typ host\r\n"
        "a=candidate:2 1 udp 1 192.168.10.5 50002 typ host\r\n"
    )
    out = rewrite_sdp_with_public_ip(sdp, public_ip="1.2.3.4")
    assert "172.18.0.3" not in out
    assert "192.168.10.5" not in out
    assert "1.2.3.4 50001" in out
    assert "1.2.3.4 50002" in out


def test_rewrite_sdp_leaves_non_candidate_lines_intact() -> None:
    sdp = (
        "v=0\r\n"
        "m=video 9 UDP/TLS/RTP/SAVPF 96\r\n"
        "a=candidate:1 1 udp 1 10.0.0.1 50001 typ host\r\n"
    )
    out = rewrite_sdp_with_public_ip(sdp, public_ip="1.2.3.4")
    assert "v=0\r\n" in out
    assert "m=video 9 UDP/TLS/RTP/SAVPF 96\r\n" in out
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd services/streamer && uv run pytest tests/test_sfu.py -v
```

Expected: ImportError for `app.sfu`.

- [ ] **Step 3: Write the implementation**

`services/streamer/app/sfu.py`:

```python
"""aiortc plumbing: peer connection factory + SDP candidate rewrite.

The streamer container sees host ICE candidates with internal Docker
addresses. We rewrite host-type candidate addresses to ``public_ip`` so
external peers (SerialHop, browsers) connect to the routable VPS address.
The host's UDP port mapping (50000-50100/udp) preserves the port unchanged.
"""

from __future__ import annotations

import re

from aiortc import RTCPeerConnection


_CANDIDATE_RE = re.compile(
    r"^(a=candidate:\S+ \d+ \S+ \d+ )(\S+)( \d+ typ host.*)$",
    flags=re.MULTILINE,
)


def parse_udp_port_range(spec: str) -> tuple[int, int]:
    """Parse "low-high" into (low, high) with low<high."""
    parts = spec.split("-")
    if len(parts) != 2:
        raise ValueError(f"udp_port_range must be 'low-high', got {spec!r}")
    low, high = int(parts[0]), int(parts[1])
    if low >= high:
        raise ValueError(f"udp_port_range low must be < high, got {spec!r}")
    return low, high


def rewrite_sdp_with_public_ip(sdp: str, *, public_ip: str) -> str:
    """Replace the address in every host-type ICE candidate with public_ip."""

    def _swap(match: re.Match[str]) -> str:
        return f"{match.group(1)}{public_ip}{match.group(3)}"

    return _CANDIDATE_RE.sub(_swap, sdp)


def new_peer_connection() -> RTCPeerConnection:
    """Fresh peer connection. ICE servers empty in v1; rewrite handles NAT."""
    return RTCPeerConnection()
```

- [ ] **Step 4: Run tests, verify pass**

```bash
cd services/streamer && uv run pytest tests/test_sfu.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add services/streamer/app/sfu.py services/streamer/tests/test_sfu.py
git commit -m "feat(streamer): aiortc plumbing + SDP public-IP rewrite"
```

---

## Task 10: WHIP handler (`whip.py`)

Public endpoint where SerialHop pushes media. Bearer auth + one-shot redemption + aiortc track wiring.

**Files:**
- Create: `services/streamer/app/whip.py`
- Test: `services/streamer/tests/test_whip.py`

- [ ] **Step 1: Write the failing test**

`services/streamer/tests/test_whip.py`:

```python
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.session_manager import SessionManager
from app.whip import make_router


@pytest.fixture
def manager() -> SessionManager:
    return SessionManager(whip_token_validity_s=60.0)


@pytest.fixture
def app(manager: SessionManager) -> FastAPI:
    fast = FastAPI()
    fast.include_router(make_router(manager=manager, public_ip="1.2.3.4"))
    return fast


def test_whip_404_when_session_unknown(app: FastAPI) -> None:
    client = TestClient(app)
    r = client.post(
        "/streamer/whip/01NOPE",
        headers={"Authorization": "Bearer tk_anything", "Content-Type": "application/sdp"},
        content="v=0\r\n",
    )
    assert r.status_code == 404


def test_whip_401_when_bearer_missing(app: FastAPI, manager: SessionManager) -> None:
    s = manager.create(lab_name="alice", translation_id="cam-0")
    client = TestClient(app)
    r = client.post(
        f"/streamer/whip/{s.session_id}",
        headers={"Content-Type": "application/sdp"},
        content="v=0\r\n",
    )
    assert r.status_code == 401


def test_whip_401_when_bearer_wrong(app: FastAPI, manager: SessionManager) -> None:
    s = manager.create(lab_name="alice", translation_id="cam-0")
    client = TestClient(app)
    r = client.post(
        f"/streamer/whip/{s.session_id}",
        headers={"Authorization": "Bearer tk_wrong", "Content-Type": "application/sdp"},
        content="v=0\r\n",
    )
    assert r.status_code == 401


def test_whip_410_when_token_already_burned(app: FastAPI, manager: SessionManager) -> None:
    s = manager.create(lab_name="alice", translation_id="cam-0")
    s.publish_token.burn()
    client = TestClient(app)
    r = client.post(
        f"/streamer/whip/{s.session_id}",
        headers={
            "Authorization": f"Bearer {s.publish_token.value}",
            "Content-Type": "application/sdp",
        },
        content="v=0\r\n",
    )
    assert r.status_code == 410


def test_whip_201_negotiates_and_burns_token(app: FastAPI, manager: SessionManager) -> None:
    s = manager.create(lab_name="alice", translation_id="cam-0")
    bearer = s.publish_token.value

    fake_pc = MagicMock()
    fake_pc.setRemoteDescription = AsyncMock()
    fake_pc.createAnswer = AsyncMock(return_value=MagicMock(sdp="v=0\r\n", type="answer"))
    fake_pc.setLocalDescription = AsyncMock()
    fake_pc.localDescription = MagicMock(sdp="v=0\r\na=candidate:1 1 udp 1 10.0.0.1 50001 typ host\r\n")

    with patch("app.whip.new_peer_connection", return_value=fake_pc):
        client = TestClient(app)
        r = client.post(
            f"/streamer/whip/{s.session_id}",
            headers={"Authorization": f"Bearer {bearer}", "Content-Type": "application/sdp"},
            content="v=0\r\n",
        )

    assert r.status_code == 201
    assert r.headers["Content-Type"].startswith("application/sdp")
    assert r.headers["Location"] == f"/streamer/whip/{s.session_id}"
    assert "1.2.3.4" in r.text  # candidate rewritten
    assert s.publish_token.matches(bearer) is False  # burned
    fake_pc.setRemoteDescription.assert_awaited_once()
    fake_pc.setLocalDescription.assert_awaited_once()


def test_whip_delete_204(app: FastAPI, manager: SessionManager) -> None:
    s = manager.create(lab_name="alice", translation_id="cam-0")
    s.publisher_pc = MagicMock()
    s.publisher_pc.close = AsyncMock()
    s.publish_token.burn()  # bearer no longer matches; DELETE uses session_id only
    client = TestClient(app)
    r = client.request(
        "DELETE",
        f"/streamer/whip/{s.session_id}",
        headers={"Authorization": "Bearer ignored"},
    )
    assert r.status_code == 204
    s.publisher_pc.close.assert_awaited_once()


def test_whip_delete_404_when_unknown(app: FastAPI) -> None:
    client = TestClient(app)
    r = client.request("DELETE", "/streamer/whip/01NOPE")
    assert r.status_code == 404
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd services/streamer && uv run pytest tests/test_whip.py -v
```

Expected: ImportError for `app.whip`.

- [ ] **Step 3: Write the implementation**

`services/streamer/app/whip.py`:

```python
"""WHIP ingest endpoint (RFC 9725) — SerialHop publishes media here."""

from __future__ import annotations

from typing import Any

from aiortc import RTCSessionDescription
from fastapi import APIRouter, Header, HTTPException, Path, Request, Response

from app.session_manager import Session, SessionManager
from app.sfu import new_peer_connection, rewrite_sdp_with_public_ip


def _parse_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        return ""
    return authorization.split(None, 1)[1].strip()


def make_router(*, manager: SessionManager, public_ip: str) -> APIRouter:
    router = APIRouter()

    @router.post("/streamer/whip/{session_id}")
    async def whip_post(
        request: Request,
        session_id: str = Path(..., min_length=1, max_length=64),
        authorization: str | None = Header(default=None),
    ) -> Response:
        session = manager.get_by_session_id(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="unknown session")

        bearer = _parse_bearer(authorization)
        if not session.publish_token.matches(bearer):
            if session.publish_token.is_burned:
                raise HTTPException(status_code=410, detail="token already redeemed")
            raise HTTPException(status_code=401, detail="invalid bearer")

        session.publish_token.burn()

        offer_sdp = (await request.body()).decode("utf-8")

        pc = new_peer_connection()
        session.publisher_pc = pc

        @pc.on("track")
        def _on_track(track: Any) -> None:
            session.mark_publishing(track=track)

        await pc.setRemoteDescription(RTCSessionDescription(sdp=offer_sdp, type="offer"))
        await pc.setLocalDescription(await pc.createAnswer())

        answer = rewrite_sdp_with_public_ip(pc.localDescription.sdp, public_ip=public_ip)

        return Response(
            content=answer,
            media_type="application/sdp",
            status_code=201,
            headers={"Location": f"/streamer/whip/{session_id}"},
        )

    @router.delete("/streamer/whip/{session_id}")
    async def whip_delete(
        session_id: str = Path(..., min_length=1, max_length=64),
    ) -> Response:
        session = manager.get_by_session_id(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="unknown session")
        if session.publisher_pc is not None:
            await session.publisher_pc.close()
            session.publisher_pc = None
        return Response(status_code=204)

    return router


def session_for_delete(manager: SessionManager, session_id: str) -> Session | None:
    """Public helper for tests / e2e shutdown hooks."""
    return manager.get_by_session_id(session_id)
```

- [ ] **Step 4: Run tests, verify pass**

```bash
cd services/streamer && uv run pytest tests/test_whip.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add services/streamer/app/whip.py services/streamer/tests/test_whip.py
git commit -m "feat(streamer): WHIP ingest endpoint"
```

---

## Task 11: WHEP handler (`whep.py`)

Public endpoint where browsers subscribe. Authelia-gated. Spawns publisher if none, waits for track, attaches subscriber.

**Files:**
- Create: `services/streamer/app/whep.py`
- Test: `services/streamer/tests/test_whep.py`

- [ ] **Step 1: Write the failing test**

`services/streamer/tests/test_whep.py`:

```python
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.discovery import DiscoveryCache, TranslationDescriptor
from app.session_manager import SessionManager
from app.whep import make_router


class _StubDiscovery:
    def __init__(self, armed: dict[str, list[TranslationDescriptor]]) -> None:
        self._armed = armed

    async def list(
        self, lab_name: str, *, force_refresh: bool = False
    ) -> list[TranslationDescriptor]:
        return list(self._armed.get(lab_name, []))


class _StubControl:
    def __init__(self, *, raise_on_start: Exception | None = None) -> None:
        self.starts: list[dict[str, str]] = []
        self.stops: list[dict[str, str]] = []
        self._raise_on_start = raise_on_start

    async def start(self, **kwargs: object) -> object:
        if self._raise_on_start is not None:
            raise self._raise_on_start
        self.starts.append({k: str(v) for k, v in kwargs.items()})
        return MagicMock(session_id=kwargs["session_id"])

    async def stop(self, **kwargs: object) -> None:
        self.stops.append({k: str(v) for k, v in kwargs.items()})


@pytest.fixture
def manager() -> SessionManager:
    return SessionManager(whip_token_validity_s=60.0)


def _app(
    manager: SessionManager,
    discovery: object,
    control: object,
    *,
    public_ip: str = "1.2.3.4",
    publish_ready_timeout_s: float = 0.2,
    drain_debounce_s: float = 0.1,
    max_subscribers: int = 3,
) -> FastAPI:
    fast = FastAPI()
    fast.dependency_overrides = {}
    # Bypass Authelia for unit tests by faking the identity dependency.
    from app.auth import get_remote_identity, Identity

    def _fake_identity() -> Identity:
        return Identity(user="alice", groups=["researchers"])

    fast.dependency_overrides[get_remote_identity] = _fake_identity
    fast.include_router(
        make_router(
            manager=manager,
            discovery=discovery,
            control=control,
            public_ip=public_ip,
            publish_ready_timeout_s=publish_ready_timeout_s,
            drain_debounce_s=drain_debounce_s,
            max_subscribers_per_session=max_subscribers,
            base_url="https://lab.example.com",
        )
    )
    return fast


def _fake_pc() -> MagicMock:
    pc = MagicMock()
    pc.setRemoteDescription = AsyncMock()
    pc.createAnswer = AsyncMock(return_value=MagicMock(sdp="v=0\r\n", type="answer"))
    pc.setLocalDescription = AsyncMock()
    pc.localDescription = MagicMock(sdp="v=0\r\n")
    pc.addTrack = MagicMock()
    pc.close = AsyncMock()
    return pc


def test_whep_404_when_translation_not_armed(manager: SessionManager) -> None:
    app = _app(manager, _StubDiscovery({}), _StubControl())
    r = TestClient(app).post(
        "/streamer/whep/alice/cam-0",
        headers={"Content-Type": "application/sdp"},
        content="v=0\r\n",
    )
    assert r.status_code == 404


def test_whep_502_when_control_unreachable(manager: SessionManager) -> None:
    from app.control import ControlError

    discovery = _StubDiscovery({"alice": [TranslationDescriptor(id="cam-0", label="Side")]})
    control = _StubControl(raise_on_start=ControlError("no tunnel"))
    app = _app(manager, discovery, control)
    r = TestClient(app).post(
        "/streamer/whep/alice/cam-0",
        headers={"Content-Type": "application/sdp"},
        content="v=0\r\n",
    )
    assert r.status_code == 502


def test_whep_503_when_camera_busy(manager: SessionManager) -> None:
    from app.control import CameraBusy

    discovery = _StubDiscovery({"alice": [TranslationDescriptor(id="cam-0", label="Side")]})
    control = _StubControl(raise_on_start=CameraBusy("camera busy"))
    app = _app(manager, discovery, control)
    r = TestClient(app).post(
        "/streamer/whep/alice/cam-0",
        headers={"Content-Type": "application/sdp"},
        content="v=0\r\n",
    )
    assert r.status_code == 503


def test_whep_504_when_publisher_never_arrives(manager: SessionManager) -> None:
    discovery = _StubDiscovery({"alice": [TranslationDescriptor(id="cam-0", label="Side")]})
    control = _StubControl()
    app = _app(manager, discovery, control, publish_ready_timeout_s=0.05)

    with patch("app.whep.new_peer_connection", return_value=_fake_pc()):
        r = TestClient(app).post(
            "/streamer/whep/alice/cam-0",
            headers={"Content-Type": "application/sdp"},
            content="v=0\r\n",
        )
    assert r.status_code == 504


def test_whep_first_viewer_triggers_start(manager: SessionManager) -> None:
    discovery = _StubDiscovery({"alice": [TranslationDescriptor(id="cam-0", label="Side")]})
    control = _StubControl()
    app = _app(manager, discovery, control, publish_ready_timeout_s=0.05)

    with patch("app.whep.new_peer_connection", return_value=_fake_pc()):
        TestClient(app).post(
            "/streamer/whep/alice/cam-0",
            headers={"Content-Type": "application/sdp"},
            content="v=0\r\n",
        )
    assert len(control.starts) == 1
    assert control.starts[0]["lab_name"] == "alice"
    assert control.starts[0]["translation_id"] == "cam-0"


def test_whep_201_when_publisher_already_attached(manager: SessionManager) -> None:
    discovery = _StubDiscovery({"alice": [TranslationDescriptor(id="cam-0", label="Side")]})
    control = _StubControl()
    s = manager.create(lab_name="alice", translation_id="cam-0")
    s.mark_publishing(track=MagicMock())

    fake_pc = _fake_pc()
    app = _app(manager, discovery, control)
    with patch("app.whep.new_peer_connection", return_value=fake_pc):
        r = TestClient(app).post(
            "/streamer/whep/alice/cam-0",
            headers={"Content-Type": "application/sdp"},
            content="v=0\r\n",
        )
    assert r.status_code == 201
    assert r.headers["Location"].startswith("/streamer/whep/alice/cam-0/")
    fake_pc.addTrack.assert_called_once()


def test_whep_429_when_max_subscribers(manager: SessionManager) -> None:
    discovery = _StubDiscovery({"alice": [TranslationDescriptor(id="cam-0", label="Side")]})
    control = _StubControl()
    s = manager.create(lab_name="alice", translation_id="cam-0")
    s.mark_publishing(track=MagicMock())
    s.subscribers["a"] = MagicMock()

    app = _app(manager, discovery, control, max_subscribers=1)
    with patch("app.whep.new_peer_connection", return_value=_fake_pc()):
        r = TestClient(app).post(
            "/streamer/whep/alice/cam-0",
            headers={"Content-Type": "application/sdp"},
            content="v=0\r\n",
        )
    assert r.status_code == 429


def test_whep_delete_removes_subscriber(manager: SessionManager) -> None:
    discovery = _StubDiscovery({"alice": [TranslationDescriptor(id="cam-0", label="Side")]})
    control = _StubControl()
    s = manager.create(lab_name="alice", translation_id="cam-0")
    sub_pc = MagicMock()
    sub_pc.close = AsyncMock()
    s.subscribers["sub-A"] = sub_pc

    app = _app(manager, discovery, control)
    r = TestClient(app).request("DELETE", "/streamer/whep/alice/cam-0/sub-A")
    assert r.status_code == 204
    assert "sub-A" not in s.subscribers
    sub_pc.close.assert_awaited_once()
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd services/streamer && uv run pytest tests/test_whep.py -v
```

Expected: ImportError for `app.whep`.

- [ ] **Step 3: Write the implementation**

`services/streamer/app/whep.py`:

```python
"""WHEP egress endpoint — browser viewers subscribe here."""

from __future__ import annotations

import asyncio
from typing import Protocol

from aiortc import RTCSessionDescription
from fastapi import APIRouter, HTTPException, Path, Request, Response
from ulid import ULID

from app.auth import RequiredGroupsDep
from app.control import CameraBusy, ControlError
from app.discovery import TranslationDescriptor
from app.session_manager import Session, SessionManager
from app.sfu import new_peer_connection, rewrite_sdp_with_public_ip


class _DiscoveryLike(Protocol):
    async def list(
        self, lab_name: str, *, force_refresh: bool = False
    ) -> list[TranslationDescriptor]: ...


class _ControlLike(Protocol):
    async def start(self, **kwargs: object) -> object: ...
    async def stop(self, **kwargs: object) -> None: ...


def make_router(
    *,
    manager: SessionManager,
    discovery: _DiscoveryLike,
    control: _ControlLike,
    public_ip: str,
    publish_ready_timeout_s: float,
    drain_debounce_s: float,
    max_subscribers_per_session: int,
    base_url: str,
) -> APIRouter:
    router = APIRouter()

    async def _stop_session(session: Session) -> None:
        try:
            await control.stop(
                lab_name=session.lab_name,
                translation_id=session.translation_id,
                session_id=session.session_id,
            )
        finally:
            if session.publisher_pc is not None:
                await session.publisher_pc.close()
            for pc in list(session.subscribers.values()):
                await pc.close()
            session.subscribers.clear()
            manager.drop(session)

    @router.post("/streamer/whep/{lab}/{translation_id}")
    async def whep_post(
        request: Request,
        lab: str = Path(..., min_length=1, max_length=128),
        translation_id: str = Path(..., min_length=1, max_length=128),
        _identity=RequiredGroupsDep,
    ) -> Response:
        offer_sdp = (await request.body()).decode("utf-8")

        async with manager.lock_for(lab, translation_id):
            session = manager.get(lab, translation_id)
            if session is None:
                armed = await discovery.list(lab)
                if not any(t.id == translation_id for t in armed):
                    raise HTTPException(status_code=404, detail="translation not armed")
                session = manager.create(lab_name=lab, translation_id=translation_id)
                whip_url = f"{base_url}/streamer/whip/{session.session_id}"
                try:
                    await control.start(
                        lab_name=lab,
                        translation_id=translation_id,
                        session_id=session.session_id,
                        whip_url=whip_url,
                        whip_token=session.publish_token.value,
                    )
                except CameraBusy:
                    manager.drop(session)
                    raise HTTPException(status_code=503, detail="camera unavailable")
                except ControlError:
                    manager.drop(session)
                    raise HTTPException(status_code=502, detail="lab unreachable")

        manager.cancel_drain(session)

        try:
            await asyncio.wait_for(
                session.publish_ready.wait(), timeout=publish_ready_timeout_s
            )
        except asyncio.TimeoutError:
            # Best-effort cleanup; drop session so next viewer retries fresh.
            await _stop_session(session)
            raise HTTPException(status_code=504, detail="publisher did not attach")

        if session.subscriber_count() >= max_subscribers_per_session:
            raise HTTPException(status_code=429, detail="max subscribers reached")

        sub_pc = new_peer_connection()
        sub_pc.addTrack(session.publisher_track)

        @sub_pc.on("connectionstatechange")
        def _on_state() -> None:
            state = getattr(sub_pc, "connectionState", "")
            if state in ("failed", "closed"):
                _remove_subscriber_sync(session, sub_pc)

        await sub_pc.setRemoteDescription(
            RTCSessionDescription(sdp=offer_sdp, type="offer")
        )
        await sub_pc.setLocalDescription(await sub_pc.createAnswer())

        sub_id = str(ULID())
        session.subscribers[sub_id] = sub_pc

        answer = rewrite_sdp_with_public_ip(
            sub_pc.localDescription.sdp, public_ip=public_ip
        )
        return Response(
            content=answer,
            media_type="application/sdp",
            status_code=201,
            headers={
                "Location": f"/streamer/whep/{session.lab_name}/{session.translation_id}/{sub_id}"
            },
        )

    @router.delete("/streamer/whep/{lab}/{translation_id}/{sub_id}")
    async def whep_delete(
        lab: str,
        translation_id: str,
        sub_id: str,
        _identity=RequiredGroupsDep,
    ) -> Response:
        session = manager.get(lab, translation_id)
        if session is not None:
            pc = session.subscribers.pop(sub_id, None)
            if pc is not None:
                await pc.close()
            if session.subscriber_count() == 0:
                manager.schedule_drain(
                    session,
                    debounce_s=drain_debounce_s,
                    on_expire=_stop_session,
                )
        return Response(status_code=204)

    def _remove_subscriber_sync(session: Session, pc: object) -> None:
        for sub_id, candidate in list(session.subscribers.items()):
            if candidate is pc:
                session.subscribers.pop(sub_id, None)
                break
        if session.subscriber_count() == 0:
            manager.schedule_drain(
                session,
                debounce_s=drain_debounce_s,
                on_expire=_stop_session,
            )

    return router
```

- [ ] **Step 4: Run tests, verify pass**

```bash
cd services/streamer && uv run pytest tests/test_whep.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add services/streamer/app/whep.py services/streamer/tests/test_whep.py
git commit -m "feat(streamer): WHEP egress endpoint with debounced drain"
```

---

## Task 12: HTML pages + static assets + JSON API (`pages.py`)

Server-rendered picker and viewing pages; the JSON endpoints the SPA consumes.

**Files:**
- Create: `services/streamer/app/pages.py`
- Create: `services/streamer/app/templates.py`
- Create: `services/streamer/app/templates/base.html`
- Create: `services/streamer/app/templates/labs.html`
- Create: `services/streamer/app/templates/lab.html`
- Create: `services/streamer/app/static/streamer.css`
- Create: `services/streamer/app/static/streamer.js`
- Test: `services/streamer/tests/test_pages.py`

- [ ] **Step 1: Write the failing test**

`services/streamer/tests/test_pages.py`:

```python
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import Identity, get_remote_identity
from app.discovery import TranslationDescriptor
from app.pages import make_router


class _StubDiscovery:
    def __init__(self, armed: dict[str, list[TranslationDescriptor]]) -> None:
        self._armed = armed

    async def list(
        self, lab_name: str, *, force_refresh: bool = False
    ) -> list[TranslationDescriptor]:
        return list(self._armed.get(lab_name, []))


def _app(armed: dict[str, list[TranslationDescriptor]], roster: dict[str, int]) -> FastAPI:
    fast = FastAPI()
    fast.dependency_overrides[get_remote_identity] = lambda: Identity(
        user="alice", groups=["researchers"]
    )
    fast.include_router(
        make_router(roster=roster, discovery=_StubDiscovery(armed))
    )
    return fast


def test_picker_lists_all_roster_labs() -> None:
    app = _app(armed={}, roster={"alice": 8089, "bob": 8090})
    r = TestClient(app).get("/streamer/labs")
    assert r.status_code == 200
    body = r.text
    assert "alice" in body
    assert "bob" in body


def test_picker_active_when_translations_exist() -> None:
    armed = {"alice": [TranslationDescriptor(id="cam-0", label="Side")]}
    app = _app(armed=armed, roster={"alice": 8089, "bob": 8090})
    r = TestClient(app).get("/streamer/labs")
    body = r.text
    assert "data-lab=\"alice\"" in body
    assert "data-active=\"true\"" in body
    assert "data-active=\"false\"" in body  # bob


def test_api_labs_returns_active_state() -> None:
    armed = {"alice": [TranslationDescriptor(id="cam-0", label="Side")]}
    app = _app(armed=armed, roster={"alice": 8089, "bob": 8090})
    r = TestClient(app).get("/streamer/api/labs")
    assert r.status_code == 200
    payload = {row["name"]: row for row in r.json()}
    assert payload["alice"]["active"] is True
    assert payload["alice"]["translation_count"] == 1
    assert payload["bob"]["active"] is False
    assert payload["bob"]["translation_count"] == 0


def test_api_lab_translations() -> None:
    armed = {
        "alice": [
            TranslationDescriptor(id="cam-0", label="Side"),
            TranslationDescriptor(id="cam-1", label="Top"),
        ]
    }
    app = _app(armed=armed, roster={"alice": 8089})
    r = TestClient(app).get("/streamer/api/labs/alice/translations")
    assert r.status_code == 200
    assert r.json() == [
        {"id": "cam-0", "label": "Side"},
        {"id": "cam-1", "label": "Top"},
    ]


def test_api_lab_translations_unknown_lab_404() -> None:
    app = _app(armed={}, roster={"alice": 8089})
    r = TestClient(app).get("/streamer/api/labs/ghost/translations")
    assert r.status_code == 404


def test_lab_viewing_page_contains_translation_grid_stub() -> None:
    armed = {"alice": [TranslationDescriptor(id="cam-0", label="Side")]}
    app = _app(armed=armed, roster={"alice": 8089})
    r = TestClient(app).get("/streamer/labs/alice")
    assert r.status_code == 200
    assert "data-lab=\"alice\"" in r.text
    assert "streamer.js" in r.text


def test_lab_viewing_page_unknown_lab_404() -> None:
    app = _app(armed={}, roster={"alice": 8089})
    r = TestClient(app).get("/streamer/labs/ghost")
    assert r.status_code == 404
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd services/streamer && uv run pytest tests/test_pages.py -v
```

Expected: ImportError for `app.pages`.

- [ ] **Step 3: Create the templates module + Jinja root**

`services/streamer/app/templates.py`:

```python
from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

TEMPLATE_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
```

- [ ] **Step 4: Write `services/streamer/app/templates/base.html`**

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{% block title %}lab-bridge streaming{% endblock %}</title>
<link rel="stylesheet" href="/streamer/_static/streamer.css">
</head>
<body>
{% block body %}{% endblock %}
</body>
</html>
```

- [ ] **Step 5: Write `services/streamer/app/templates/labs.html`**

```html
{% extends "base.html" %}
{% block title %}Live streams — lab-bridge{% endblock %}
{% block body %}
<main class="streamer-picker">
  <h1>Live streams</h1>
  <p class="hint">Pick a lab to watch. Inactive labs have no streams armed by the operator.</p>
  <ul class="lab-grid" id="lab-grid">
    {% for lab in labs %}
    <li class="lab-card"
        data-lab="{{ lab.name }}"
        data-active="{{ 'true' if lab.active else 'false' }}">
      {% if lab.active %}
      <a href="/streamer/labs/{{ lab.name }}">
        <span class="lab-name">{{ lab.name }}</span>
        <span class="lab-count">{{ lab.translation_count }} stream{{ '' if lab.translation_count == 1 else 's' }}</span>
      </a>
      {% else %}
      <div class="lab-inactive">
        <span class="lab-name">{{ lab.name }}</span>
        <span class="lab-status">no streams allowed by operator</span>
      </div>
      {% endif %}
    </li>
    {% endfor %}
  </ul>
</main>
<script>
  // 15 s background poll for newly-armed translations.
  setInterval(async () => {
    try {
      const resp = await fetch("/streamer/api/labs");
      if (!resp.ok) return;
      const labs = await resp.json();
      for (const lab of labs) {
        const card = document.querySelector(`[data-lab="${lab.name}"]`);
        if (card && card.getAttribute("data-active") !== String(lab.active)) {
          window.location.reload();
          return;
        }
      }
    } catch (e) {
      // Ignored; will retry on next interval.
    }
  }, 15000);
</script>
{% endblock %}
```

- [ ] **Step 6: Write `services/streamer/app/templates/lab.html`**

```html
{% extends "base.html" %}
{% block title %}{{ lab_name }} — streams{% endblock %}
{% block body %}
<main class="streamer-lab" data-lab="{{ lab_name }}">
  <header>
    <a href="/streamer/labs">← all labs</a>
    <h1>{{ lab_name }}</h1>
  </header>
  <section class="grid" id="tile-grid">
    {% for t in translations %}
    <article class="tile" data-translation-id="{{ t.id }}">
      <video autoplay muted playsinline controls></video>
      <footer>
        <span class="label">{{ t.label }}</span>
        <span class="state" data-state="connecting">connecting…</span>
      </footer>
    </article>
    {% endfor %}
  </section>
  {% if not translations %}
  <p class="empty">No streams currently armed on this lab. Ask the operator to enable a camera.</p>
  {% endif %}
</main>
<script src="/streamer/_static/streamer.js" defer></script>
{% endblock %}
```

- [ ] **Step 7: Write `services/streamer/app/static/streamer.css`**

```css
:root {
  --bg: #0f1115;
  --fg: #e8eaed;
  --muted: #8b95a5;
  --accent: #7aa2ff;
  --inactive: #2a2f37;
  --tile-bg: #1a1d23;
}

body {
  background: var(--bg);
  color: var(--fg);
  font: 14px/1.5 system-ui, sans-serif;
  margin: 0;
}

main {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

.lab-grid {
  list-style: none;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.lab-card a, .lab-inactive {
  display: block;
  padding: 16px;
  border-radius: 8px;
  text-decoration: none;
  color: inherit;
}

.lab-card[data-active="true"] a {
  background: var(--tile-bg);
  border: 1px solid var(--accent);
}

.lab-card[data-active="false"] .lab-inactive {
  background: var(--inactive);
  color: var(--muted);
  cursor: not-allowed;
}

.lab-name { display: block; font-weight: 600; }
.lab-count, .lab-status { display: block; font-size: 12px; color: var(--muted); margin-top: 4px; }

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  gap: 12px;
}

.tile {
  background: var(--tile-bg);
  border-radius: 8px;
  overflow: hidden;
}

.tile video {
  width: 100%;
  aspect-ratio: 16 / 9;
  background: #000;
  display: block;
}

.tile footer {
  display: flex;
  justify-content: space-between;
  padding: 8px 12px;
  font-size: 12px;
}

.state[data-state="live"] { color: #5eba7d; }
.state[data-state="connecting"] { color: var(--muted); }
.state[data-state="retrying"] { color: #e1a948; }
.state[data-state="ended"] { color: #d75050; }

.empty {
  margin-top: 32px;
  color: var(--muted);
  text-align: center;
}
```

- [ ] **Step 8: Write `services/streamer/app/static/streamer.js`**

```javascript
(function () {
  "use strict";

  const root = document.querySelector(".streamer-lab");
  if (!root) return;
  const labName = root.dataset.lab;
  const tiles = root.querySelectorAll(".tile");

  const RETRY_BACKOFF_MS = [2000, 5000, 15000];

  function setState(tile, state) {
    const el = tile.querySelector(".state");
    el.dataset.state = state;
    el.textContent = state === "live" ? "live"
      : state === "retrying" ? "retrying…"
      : state === "ended" ? "ended"
      : "connecting…";
  }

  async function attach(tile, attempt) {
    const translationId = tile.dataset.translationId;
    setState(tile, attempt > 0 ? "retrying" : "connecting");
    const pc = new RTCPeerConnection();
    pc.addTransceiver("video", { direction: "recvonly" });

    pc.ontrack = (e) => {
      tile.querySelector("video").srcObject = e.streams[0];
    };
    pc.onconnectionstatechange = () => {
      const cs = pc.connectionState;
      if (cs === "connected") setState(tile, "live");
      else if (cs === "failed" || cs === "closed") setState(tile, "ended");
    };

    await pc.setLocalDescription(await pc.createOffer());

    let resp;
    try {
      resp = await fetch(`/streamer/whep/${labName}/${translationId}`, {
        method: "POST",
        headers: { "Content-Type": "application/sdp" },
        body: pc.localDescription.sdp,
      });
    } catch (e) {
      scheduleRetry(tile, attempt);
      return;
    }

    if (resp.status === 504 || resp.status === 502) {
      scheduleRetry(tile, attempt);
      return;
    }
    if (!resp.ok) {
      setState(tile, "ended");
      return;
    }

    tile.dataset.subscriberLocation = resp.headers.get("Location") || "";
    const answerSdp = await resp.text();
    await pc.setRemoteDescription({ type: "answer", sdp: answerSdp });
    tile._pc = pc;
  }

  function scheduleRetry(tile, attempt) {
    if (attempt >= RETRY_BACKOFF_MS.length) {
      setState(tile, "ended");
      return;
    }
    setState(tile, "retrying");
    setTimeout(() => attach(tile, attempt + 1), RETRY_BACKOFF_MS[attempt]);
  }

  tiles.forEach((t) => attach(t, 0));

  window.addEventListener("pagehide", () => {
    tiles.forEach((t) => {
      if (t.dataset.subscriberLocation) {
        fetch(t.dataset.subscriberLocation, {
          method: "DELETE",
          keepalive: true,
        });
      }
    });
  });
})();
```

- [ ] **Step 9: Write `services/streamer/app/pages.py`**

```python
"""Server-rendered viewer pages + JSON API for the SPA."""

from __future__ import annotations

from typing import Protocol

from fastapi import APIRouter, HTTPException, Path, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.auth import RequiredGroupsDep
from app.discovery import TranslationDescriptor
from app.templates import templates


class _DiscoveryLike(Protocol):
    async def list(
        self, lab_name: str, *, force_refresh: bool = False
    ) -> list[TranslationDescriptor]: ...


def make_router(
    *, roster: dict[str, int], discovery: _DiscoveryLike
) -> APIRouter:
    router = APIRouter()

    @router.get("/streamer/labs", response_class=HTMLResponse)
    async def labs_picker(request: Request, _identity=RequiredGroupsDep) -> HTMLResponse:
        labs = []
        for name in sorted(roster.keys()):
            translations = await discovery.list(name)
            labs.append(
                {
                    "name": name,
                    "active": len(translations) > 0,
                    "translation_count": len(translations),
                }
            )
        return templates.TemplateResponse(request, "labs.html", {"labs": labs})

    @router.get("/streamer/labs/{name}", response_class=HTMLResponse)
    async def lab_view(
        request: Request,
        name: str = Path(..., min_length=1, max_length=128),
        _identity=RequiredGroupsDep,
    ) -> HTMLResponse:
        if name not in roster:
            raise HTTPException(status_code=404, detail="unknown lab")
        translations = await discovery.list(name, force_refresh=True)
        return templates.TemplateResponse(
            request,
            "lab.html",
            {"lab_name": name, "translations": translations},
        )

    @router.get("/streamer/api/labs")
    async def api_labs(_identity=RequiredGroupsDep) -> JSONResponse:
        out = []
        for name in sorted(roster.keys()):
            translations = await discovery.list(name)
            out.append(
                {
                    "name": name,
                    "active": len(translations) > 0,
                    "translation_count": len(translations),
                }
            )
        return JSONResponse(out)

    @router.get("/streamer/api/labs/{name}/translations")
    async def api_lab_translations(
        name: str = Path(..., min_length=1, max_length=128),
        _identity=RequiredGroupsDep,
    ) -> JSONResponse:
        if name not in roster:
            raise HTTPException(status_code=404, detail="unknown lab")
        translations = await discovery.list(name, force_refresh=True)
        return JSONResponse([{"id": t.id, "label": t.label} for t in translations])

    return router
```

- [ ] **Step 10: Run tests, verify pass**

```bash
cd services/streamer && uv run pytest tests/test_pages.py -v
```

Expected: 7 passed.

- [ ] **Step 11: Run full unit suite**

```bash
cd services/streamer && uv run pytest -v
```

Expected: all unit tests pass.

- [ ] **Step 12: Commit**

```bash
git add services/streamer/app services/streamer/tests/test_pages.py
git commit -m "feat(streamer): viewer pages + JSON API"
```

---

## Task 13: Wire up `main.py` (assemble the FastAPI app)

Build the final app with all routers, static files, and lifespan-managed shared state.

**Files:**
- Modify: `services/streamer/app/main.py`
- Create: `services/streamer/tests/test_main.py`

- [ ] **Step 1: Write the failing test**

`services/streamer/tests/test_main.py`:

```python
from __future__ import annotations

from fastapi.testclient import TestClient


def test_healthz_ok() -> None:
    from app.main import app

    r = TestClient(app).get("/healthz")
    assert r.status_code == 200
    payload = r.json()
    assert payload["status"] == "ok"
    assert "version" in payload


def test_static_assets_mounted() -> None:
    from app.main import app

    r = TestClient(app).get("/streamer/_static/streamer.css")
    assert r.status_code == 200
    assert "lab-grid" in r.text
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd services/streamer && uv run pytest tests/test_main.py -v
```

Expected: static asset test fails (404).

- [ ] **Step 3: Replace `services/streamer/app/main.py`**

```python
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import load_settings
from app.control import ControlPlaneClient
from app.discovery import DiscoveryCache
from app.pages import make_router as make_pages_router
from app.roster import load_roster
from app.session_manager import SessionManager
from app.templates import STATIC_DIR
from app.whep import make_router as make_whep_router
from app.whip import make_router as make_whip_router


def _build_base_url(public_ip: str) -> str:
    return f"https://{public_ip}"


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield


settings = load_settings()


def _roster() -> dict[str, int]:
    try:
        return load_roster(settings.clients_file)
    except OSError:
        return {}


roster = _roster()

discovery = DiscoveryCache(
    roster=roster,
    chisel_host=settings.chisel_host,
    ttl_s=settings.discovery_cache_ttl_s,
    request_timeout_s=settings.discovery_request_timeout_s,
)
control = ControlPlaneClient(
    roster=roster,
    chisel_host=settings.chisel_host,
    request_timeout_s=2.0,
)
manager = SessionManager(whip_token_validity_s=settings.whip_token_validity_s)

app = FastAPI(title="lab-bridge streamer", lifespan=_lifespan)

app.mount("/streamer/_static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(
    make_whip_router(manager=manager, public_ip=settings.public_ip)
)
app.include_router(
    make_whep_router(
        manager=manager,
        discovery=discovery,
        control=control,
        public_ip=settings.public_ip,
        publish_ready_timeout_s=settings.publish_ready_timeout_s,
        drain_debounce_s=settings.drain_debounce_s,
        max_subscribers_per_session=settings.max_subscribers_per_session,
        base_url=_build_base_url(settings.public_ip),
    )
)
app.include_router(
    make_pages_router(roster=roster, discovery=discovery)
)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {
        "status": "ok",
        "version": settings.lab_bridge_version,
        "git_sha": settings.lab_bridge_git_sha,
    }
```

- [ ] **Step 4: Run all unit tests**

```bash
cd services/streamer && uv run pytest -v
```

Expected: every unit test passes.

- [ ] **Step 5: Lint**

```bash
cd services/streamer && uv run ruff check app tests && uv run ruff format --check app tests
```

Expected: clean. If `ruff format --check` fails, run `uv run ruff format app tests` and re-stage.

- [ ] **Step 6: Local container smoke**

```bash
cd services/streamer && docker build -t lab-bridge-streamer:dev .
docker run --rm -p 8000:8000 \
  -e STREAMER_CLIENTS_FILE=/tmp/clients.json \
  -e STREAMER_PUBLIC_IP=127.0.0.1 \
  -v /dev/null:/tmp/clients.json:ro \
  lab-bridge-streamer:dev &
sleep 3
curl -fsS http://127.0.0.1:8000/healthz
kill %1
```

Expected: `{"status":"ok",…}`.

- [ ] **Step 7: Commit**

```bash
git add services/streamer/app/main.py services/streamer/tests/test_main.py
git commit -m "feat(streamer): wire FastAPI app with all routers"
```

---

## Task 14: e2e harness — compose file + SerialHop stub

Spin up the streamer container alongside a stub SerialHop in a single docker-compose, behind a session-scoped pytest fixture.

**Files:**
- Create: `services/streamer/tests/e2e/__init__.py`
- Create: `services/streamer/tests/e2e/compose.yaml`
- Create: `services/streamer/tests/e2e/conftest.py`
- Create: `services/streamer/tests/e2e/stub_serialhop.py`
- Create: `services/streamer/tests/e2e/stub_serialhop.Dockerfile`

- [ ] **Step 1: Write `services/streamer/tests/e2e/__init__.py`**

Empty file.

- [ ] **Step 2: Write `services/streamer/tests/e2e/stub_serialhop.py`**

```python
"""Stub SerialHop for streamer e2e tests.

Mirrors the SerialHop-facing protocol (see
docs/superpowers/specs/2026-05-24-serialhop-streaming-protocol.md) with
test-time fixtures: armed translations come from STUB_ARMED env (JSON),
and recorded /start /stop calls can be inspected via /__/calls.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response

ARMED = json.loads(os.environ.get("STUB_ARMED", "[]"))
BEHAVIOUR = os.environ.get("STUB_BEHAVIOUR", "normal")  # normal|camera-busy|unknown

app = FastAPI()
recorded: dict[str, list[dict[str, Any]]] = {"starts": [], "stops": []}
active_sessions: dict[str, str] = {}  # translation_id → session_id


@app.get("/api/translations")
def translations() -> dict[str, list[dict[str, str]]]:
    return {"translations": ARMED}


@app.post("/api/translations/{tid}/start")
async def start(tid: str, request: Request) -> Response:
    body = await request.json()
    recorded["starts"].append({"tid": tid, **body})

    if BEHAVIOUR == "unknown":
        raise HTTPException(status_code=404, detail="unknown translation")
    if BEHAVIOUR == "camera-busy":
        raise HTTPException(status_code=503, detail="camera busy")

    sid = body["session_id"]
    # Idempotent retry: same session_id is a no-op (still 202, no new publisher).
    if active_sessions.get(tid) == sid:
        return Response(status_code=202)
    # Replace-on-conflict: drop any previous session for this tid.
    active_sessions[tid] = sid

    # Spawn an outbound WHIP publisher in the background.
    asyncio.create_task(_publish(body["whip_url"], body["whip_token"]))
    return Response(status_code=202)


@app.post("/api/translations/{tid}/stop")
async def stop(tid: str, request: Request) -> Response:
    body = await request.json()
    recorded["stops"].append({"tid": tid, **body})
    current = active_sessions.get(tid)
    if current is not None and current != body.get("session_id"):
        return JSONResponse({"active_session_id": current}, status_code=409)
    active_sessions.pop(tid, None)
    return Response(status_code=204)


@app.get("/__/calls")
def calls() -> dict[str, list[dict[str, Any]]]:
    return recorded


@app.post("/__/reset")
def reset() -> dict[str, str]:
    recorded["starts"].clear()
    recorded["stops"].clear()
    active_sessions.clear()
    return {"reset": "ok"}


async def _publish(whip_url: str, whip_token: str) -> None:
    """Use aiortc to drive a test pattern stream into the streamer's WHIP."""
    from aiortc import RTCPeerConnection, RTCSessionDescription
    from aiortc.contrib.media import MediaPlayer

    pc = RTCPeerConnection()
    player = MediaPlayer("color=c=blue:s=320x240", format="lavfi", options={"framerate": "10"})
    pc.addTrack(player.video)

    await pc.setLocalDescription(await pc.createOffer())
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            whip_url,
            content=pc.localDescription.sdp,
            headers={
                "Authorization": f"Bearer {whip_token}",
                "Content-Type": "application/sdp",
            },
        )
    if resp.status_code != 201:
        return
    await pc.setRemoteDescription(RTCSessionDescription(sdp=resp.text, type="answer"))
    # Keep alive for the test session
    await asyncio.sleep(60.0)
    await pc.close()
```

- [ ] **Step 3: Write `services/streamer/tests/e2e/stub_serialhop.Dockerfile`**

```dockerfile
FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libavdevice59 libavfilter9 libavformat60 libavcodec60 libavutil58 \
    libswscale7 libswresample4 libsrtp2-1 libopus0 libvpx7 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir 'fastapi==0.115.*' 'uvicorn[standard]==0.30.*' \
    'aiortc==1.9.*' 'httpx==0.28.*'

COPY stub_serialhop.py /stub.py

ENV PYTHONPATH=/
EXPOSE 8001
CMD ["uvicorn", "stub:app", "--host", "0.0.0.0", "--port", "8001"]
```

- [ ] **Step 4: Write `services/streamer/tests/e2e/compose.yaml`**

```yaml
name: streamer-e2e

services:
  serialhop-stub:
    build:
      context: .
      dockerfile: stub_serialhop.Dockerfile
    environment:
      STUB_ARMED: '[{"id":"cam-0","label":"Test pattern"}]'
      STUB_BEHAVIOUR: normal
    networks:
      labnet:
        aliases:
          - chisel       # so streamer can reach it as chisel:8001
    ports:
      - "127.0.0.1:8081:8001"   # for direct test poking

  streamer:
    image: ${STREAMER_TEST_IMAGE:-lab-bridge-streamer:e2e}
    environment:
      STREAMER_CLIENTS_FILE: /etc/streamer/clients.json
      STREAMER_CHISEL_HOST: chisel
      STREAMER_PUBLIC_IP: 127.0.0.1
      STREAMER_PUBLISH_READY_TIMEOUT_S: "5"
      STREAMER_DRAIN_DEBOUNCE_S: "1"
      STREAMER_DISCOVERY_CACHE_TTL_S: "0.5"
    volumes:
      - ./fixtures/clients.json:/etc/streamer/clients.json:ro
    ports:
      - "127.0.0.1:8080:8000"
      - "127.0.0.1:50000-50100:50000-50100/udp"
    networks: [labnet]
    depends_on:
      - serialhop-stub

networks:
  labnet:
    driver: bridge
```

- [ ] **Step 5: Create the e2e fixture roster**

`services/streamer/tests/e2e/fixtures/clients.json`:

```json
{
  "alice": { "port": 8001 }
}
```

(Create with `mkdir -p services/streamer/tests/e2e/fixtures` then write.)

- [ ] **Step 6: Write `services/streamer/tests/e2e/conftest.py`**

```python
"""Session-scoped streamer + serialhop-stub fixture."""

from __future__ import annotations

import subprocess
from pathlib import Path

import httpx
import pytest

HERE = Path(__file__).parent
COMPOSE_FILE = HERE / "compose.yaml"


def _compose(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), *args],
        check=check,
        cwd=str(HERE),
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="session")
def streamer_stack() -> dict[str, str]:
    _compose("up", "-d", "--build", "--wait")
    try:
        yield {
            "streamer": "http://127.0.0.1:8080",
            "stub": "http://127.0.0.1:8081",
        }
    finally:
        _compose("down", "-v", check=False)


@pytest.fixture
def http_streamer(streamer_stack: dict[str, str]) -> httpx.Client:
    with httpx.Client(
        base_url=streamer_stack["streamer"],
        timeout=10.0,
        headers={"Remote-User": "alice", "Remote-Groups": "researchers"},
    ) as client:
        yield client


@pytest.fixture
def http_stub(streamer_stack: dict[str, str]) -> httpx.Client:
    with httpx.Client(base_url=streamer_stack["stub"], timeout=10.0) as client:
        client.post("/__/reset")
        yield client
```

- [ ] **Step 7: Commit**

```bash
git add services/streamer/tests/e2e
git commit -m "test(streamer): e2e harness with SerialHop stub"
```

---

## Task 15: e2e tests — picker, discovery, WHIP auth

The first batch of e2e behaviours that don't require driving real media.

**Files:**
- Create: `services/streamer/tests/e2e/test_picker.py`
- Create: `services/streamer/tests/e2e/test_whip_auth.py`

- [ ] **Step 1: Build the streamer e2e image locally**

```bash
cd services/streamer && docker build -t lab-bridge-streamer:e2e .
```

Expected: image builds.

- [ ] **Step 2: Write `services/streamer/tests/e2e/test_picker.py`**

```python
from __future__ import annotations

import httpx


def test_healthz_ok(http_streamer: httpx.Client) -> None:
    r = http_streamer.get("/healthz")
    assert r.status_code == 200


def test_picker_lists_alice(http_streamer: httpx.Client) -> None:
    r = http_streamer.get("/streamer/labs")
    assert r.status_code == 200
    assert "alice" in r.text


def test_api_labs_shows_active_with_armed_translation(
    http_streamer: httpx.Client, http_stub: httpx.Client
) -> None:
    r = http_streamer.get("/streamer/api/labs")
    assert r.status_code == 200
    rows = {row["name"]: row for row in r.json()}
    assert rows["alice"]["active"] is True
    assert rows["alice"]["translation_count"] == 1


def test_api_translations(http_streamer: httpx.Client) -> None:
    r = http_streamer.get("/streamer/api/labs/alice/translations")
    assert r.status_code == 200
    assert r.json() == [{"id": "cam-0", "label": "Test pattern"}]


def test_api_translations_unknown_lab_404(http_streamer: httpx.Client) -> None:
    r = http_streamer.get("/streamer/api/labs/ghost/translations")
    assert r.status_code == 404


def test_picker_blocks_unauthenticated() -> None:
    r = httpx.get("http://127.0.0.1:8080/streamer/labs", timeout=5.0)
    assert r.status_code == 401
```

- [ ] **Step 3: Write `services/streamer/tests/e2e/test_whip_auth.py`**

```python
from __future__ import annotations

import httpx


def test_whip_unknown_session_404() -> None:
    r = httpx.post(
        "http://127.0.0.1:8080/streamer/whip/01NOPE",
        headers={"Authorization": "Bearer tk_xyz", "Content-Type": "application/sdp"},
        content="v=0\r\n",
        timeout=5.0,
    )
    assert r.status_code == 404
```

- [ ] **Step 4: Run the first batch**

```bash
cd services/streamer && uv run pytest tests/e2e/test_picker.py tests/e2e/test_whip_auth.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add services/streamer/tests/e2e/test_picker.py services/streamer/tests/e2e/test_whip_auth.py
git commit -m "test(streamer): e2e picker + WHIP auth"
```

---

## Task 16: e2e tests — control flow + lifecycle

Exercise the start/stop/debounce path against the stub.

**Files:**
- Create: `services/streamer/tests/e2e/test_lifecycle.py`

- [ ] **Step 1: Write `services/streamer/tests/e2e/test_lifecycle.py`**

```python
from __future__ import annotations

import time

import httpx
import pytest

OFFER_SDP_TEMPLATE = (
    "v=0\r\n"
    "o=- 0 0 IN IP4 127.0.0.1\r\n"
    "s=-\r\n"
    "t=0 0\r\n"
    "m=video 9 UDP/TLS/RTP/SAVPF 96\r\n"
    "c=IN IP4 0.0.0.0\r\n"
    "a=rtpmap:96 VP8/90000\r\n"
    "a=recvonly\r\n"
)


def _whep(http_streamer: httpx.Client, lab: str, tid: str) -> httpx.Response:
    return http_streamer.post(
        f"/streamer/whep/{lab}/{tid}",
        headers={"Content-Type": "application/sdp"},
        content=OFFER_SDP_TEMPLATE,
    )


def test_first_whep_triggers_serialhop_start(
    http_streamer: httpx.Client, http_stub: httpx.Client
) -> None:
    _whep(http_streamer, "alice", "cam-0")
    time.sleep(0.3)
    calls = http_stub.get("/__/calls").json()
    assert len(calls["starts"]) == 1
    assert calls["starts"][0]["tid"] == "cam-0"


def test_drain_emits_stop_after_debounce(
    http_streamer: httpx.Client, http_stub: httpx.Client
) -> None:
    resp = _whep(http_streamer, "alice", "cam-0")
    if resp.status_code != 201:
        pytest.skip("publisher did not attach; covered in test_media_flows")

    location = resp.headers["Location"]
    http_streamer.delete(location)

    time.sleep(2.0)  # debounce is 1s in e2e settings
    calls = http_stub.get("/__/calls").json()
    assert len(calls["stops"]) >= 1


def test_two_viewers_share_publisher(
    http_streamer: httpx.Client, http_stub: httpx.Client
) -> None:
    http_stub.post("/__/reset")
    a = _whep(http_streamer, "alice", "cam-0")
    b = _whep(http_streamer, "alice", "cam-0")
    if a.status_code != 201 or b.status_code != 201:
        pytest.skip("publisher did not attach")
    time.sleep(0.3)
    calls = http_stub.get("/__/calls").json()
    assert len(calls["starts"]) == 1
```

- [ ] **Step 2: Run the lifecycle tests**

```bash
cd services/streamer && uv run pytest tests/e2e/test_lifecycle.py -v
```

Expected: all pass (some may skip if aiortc handshake is flaky in CI).

- [ ] **Step 3: Commit**

```bash
git add services/streamer/tests/e2e/test_lifecycle.py
git commit -m "test(streamer): e2e lifecycle + control plane"
```

---

## Task 17: Compose plumbing + Caddy + Authelia

Wire the streamer into the platform's compose template, Caddyfile, Authelia config, and render script.

**Files:**
- Modify: `compose/docker-compose.yml.tmpl`
- Modify: `compose/Caddyfile.tmpl`
- Modify: `compose/authelia/configuration.yml.tmpl`
- Modify: `compose/pins.yaml`
- Modify: `compose/config.ci.yaml.tmpl`
- Modify: `config.example.yaml`
- Modify: `scripts/lib/render.sh`

- [ ] **Step 1: Update `compose/docker-compose.yml.tmpl` — add streamer service**

Insert after the `flasher:` block (and before `networks:`):

```yaml
  streamer:
    image: __STREAMER_IMAGE__
    restart: unless-stopped
    environment:
      LAB_BRIDGE_VERSION: __LAB_BRIDGE_VERSION__
      STREAMER_CLIENTS_FILE: /etc/streamer/clients.json
      STREAMER_CHISEL_HOST: chisel
      STREAMER_PUBLIC_IP: __VPS_PUBLIC_IP__
      STREAMER_UDP_PORT_RANGE: 50000-50100
      STREAMER_PUBLISH_READY_TIMEOUT_S: "10"
      STREAMER_DRAIN_DEBOUNCE_S: "5"
      STREAMER_DISCOVERY_CACHE_TTL_S: "10"
      STREAMER_DISCOVERY_REQUEST_TIMEOUT_S: "1.0"
      STREAMER_WHIP_TOKEN_VALIDITY_S: "60"
      STREAMER_MAX_SUBSCRIBERS_PER_SESSION: "3"
    volumes:
      - ./siteapp/clients.json:/etc/streamer/clients.json:ro
      - ./streamer_data:/data
    ports:
      - "50000-50100:50000-50100/udp"
    networks: [labnet]
```

Also add `streamer` to the `caddy:` `depends_on:` list at the top of the file (alongside `siteapp, flasher, ...`).

- [ ] **Step 2: Update `compose/Caddyfile.tmpl` — add streamer routes**

Locate the existing `handle /flash/*` (or similar `/<service>/*`) block. Insert these blocks above the catch-all `reverse_proxy jupyter:8888`:

```caddy
    # WHIP — bearer-token auth, no Authelia
    handle /streamer/whip/* {
        reverse_proxy streamer:8000
    }

    # Everything else under /streamer/* — Authelia-gated
    handle /streamer/* {
        import authelia_required
        import inject_navbar
        reverse_proxy streamer:8000
    }
```

- [ ] **Step 3: Update `compose/authelia/configuration.yml.tmpl` — add /streamer ACL**

In the `access_control.rules:` block, add (mirroring `/grafana` / `/flash` entries):

```yaml
    - domain: "*"
      resources:
        - "^/streamer($|/.*)"
      policy: one_factor
      subject:
        - "group:researchers"
        - "group:admins"
```

But ensure `/streamer/whip` is **bypassed**. Add this rule **before** the previous one:

```yaml
    - domain: "*"
      resources:
        - "^/streamer/whip(/.*)?$"
      policy: bypass
```

Authelia rules are evaluated top-down; bypass comes first.

- [ ] **Step 4: Update `compose/pins.yaml` — add streamer**

Add to the file:

```yaml
streamer_image_repo: ghcr.io/khamitovdr/lab-bridge-streamer
streamer_image_sha: ""  # filled by first CI release
```

(Use the actual GHCR namespace used by siteapp and flasher.)

- [ ] **Step 5: Update `compose/config.ci.yaml.tmpl` — add vps_public_ip placeholder**

Add at the top level:

```yaml
vps_public_ip: 127.0.0.1
```

- [ ] **Step 6: Update `config.example.yaml`**

Add a top-level field with a comment:

```yaml
# Public IPv4 of the VPS hosting lab-bridge — used as the WebRTC ICE candidate
# address so SerialHop and browsers can dial UDP 50000-50100 directly.
vps_public_ip: 0.0.0.0
```

- [ ] **Step 7: Update `scripts/lib/render.sh` — substitute __VPS_PUBLIC_IP__ and __STREAMER_IMAGE__**

Find the `render_compose()` function. Add to its sed substitution list:

```bash
        -e "s|__STREAMER_IMAGE__|${STREAMER_IMAGE}|g" \
        -e "s|__VPS_PUBLIC_IP__|${VPS_PUBLIC_IP}|g" \
```

Find or create a `_streamer_image()` function (copy `_siteapp_image`):

```bash
_streamer_image() {
    local repo sha tag
    repo="$(yq e '.streamer_image_repo' "$REPO_ROOT/compose/pins.yaml")"
    sha="$(yq e '.streamer_image_sha' "$REPO_ROOT/compose/pins.yaml")"
    tag="$(awk 'NF { print $1; exit }' "$REPO_ROOT/VERSION")"
    if [[ -n "$sha" && "$sha" != "null" ]]; then
        echo "${repo}@${sha}"
    else
        echo "${repo}:${tag}"
    fi
}
```

And in `render_compose()` initialise the variables:

```bash
    STREAMER_IMAGE="$(_streamer_image)"
    VPS_PUBLIC_IP="$(yq e '.vps_public_ip' "$CONFIG_PATH")"
    if [[ -z "$VPS_PUBLIC_IP" || "$VPS_PUBLIC_IP" == "null" ]]; then
        echo "config.yaml is missing vps_public_ip" >&2
        return 1
    fi
```

- [ ] **Step 8: Sanity-check render**

```bash
cd /tmp && rm -rf render-smoke && mkdir render-smoke && cd render-smoke
cp -r $OLDPWD/compose ./compose
cp $OLDPWD/scripts/lib/render.sh ./render.sh
# (Plus a minimal config.yaml in this dir to confirm rendering doesn't error.)
```

Expected smoke: `bash -n scripts/lib/render.sh` passes.

```bash
cd /Users/khamitovdr/lab_devices_server && bash -n scripts/lib/render.sh
```

Expected: no output (syntactically valid).

- [ ] **Step 9: Commit**

```bash
git add compose/docker-compose.yml.tmpl compose/Caddyfile.tmpl \
        compose/authelia/configuration.yml.tmpl compose/pins.yaml \
        compose/config.ci.yaml.tmpl config.example.yaml scripts/lib/render.sh
git commit -m "feat(platform): wire streamer into compose + caddy + authelia"
```

---

## Task 18: Deploy script — restart list + healthcheck

Add streamer to the post-rsync restart list and the route-reachability probe.

**Files:**
- Modify: `scripts/deploy.sh`

- [ ] **Step 1: Read the current `scripts/deploy.sh`**

```bash
grep -n "restart_services\|reverse_proxy\|reachability" scripts/deploy.sh | head -30
```

- [ ] **Step 2: Add `streamer` to `restart_services`**

Find the line listing services to restart (e.g. `restart_services="caddy chisel siteapp"`). Add `streamer`:

```bash
restart_services="caddy chisel siteapp streamer"
```

- [ ] **Step 3: Add a probe in the route-reachability loop**

Find the loop around line ~117 (per `docs/adding-a-service.md`). Add:

```bash
    # streamer — Authelia-gated picker page
    code="$(curl -ksS -o /dev/null -w '%{http_code}' "https://$VPS_HOST/streamer/labs")"
    case "$code" in
        302|401|200) ;;
        *) echo "streamer route check: got $code"; exit 1 ;;
    esac
```

- [ ] **Step 4: Lint**

```bash
bash -n scripts/deploy.sh
shellcheck scripts/deploy.sh || true
```

Expected: no syntax errors.

- [ ] **Step 5: Commit**

```bash
git add scripts/deploy.sh
git commit -m "feat(deploy): restart streamer + add route reachability probe"
```

---

## Task 19: CI workflow — `pr-streamer.yml`

Per-service workflow mirroring `pr-siteapp.yml`.

**Files:**
- Create: `.github/workflows/pr-streamer.yml`

- [ ] **Step 1: Write the workflow file**

```yaml
name: pr-streamer

on:
  pull_request:
    types: [opened, synchronize, reopened]

concurrency:
  group: pr-streamer-${{ github.event.pull_request.number }}
  cancel-in-progress: true

permissions:
  contents: read
  pull-requests: read

jobs:
  streamer:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4

      - id: changed
        uses: dorny/paths-filter@v3
        with:
          filters: |
            src:
              - 'services/streamer/**'
              - '.github/workflows/pr-streamer.yml'

      - id: should-run
        name: determine if suite should run
        run: |
          set -e
          if [[ "${{ github.head_ref }}" == release-please--* ]]; then
            echo "run=true" >> "$GITHUB_OUTPUT"
            echo "::notice::release-please PR — running full streamer suite"
          else
            echo "run=${{ steps.changed.outputs.src }}" >> "$GITHUB_OUTPUT"
          fi

      - if: steps.should-run.outputs.run != 'true'
        run: echo "no streamer changes; skipping all steps"

      - if: steps.should-run.outputs.run == 'true'
        uses: actions/setup-python@v5
        with:
          python-version-file: services/streamer/.python-version
          cache: pip

      - name: install uv
        if: steps.should-run.outputs.run == 'true'
        run: pip install uv

      - name: deps
        if: steps.should-run.outputs.run == 'true'
        working-directory: services/streamer
        run: uv sync --frozen

      - name: ruff check
        if: steps.should-run.outputs.run == 'true'
        working-directory: services/streamer
        run: uv run ruff check app tests

      - name: ruff format check
        if: steps.should-run.outputs.run == 'true'
        working-directory: services/streamer
        run: uv run ruff format --check app tests

      - name: pytest (unit)
        if: steps.should-run.outputs.run == 'true'
        working-directory: services/streamer
        run: uv run pytest -v

      - name: docker buildx setup
        if: steps.should-run.outputs.run == 'true'
        uses: docker/setup-buildx-action@v3

      - name: image build (no push)
        if: steps.should-run.outputs.run == 'true'
        uses: docker/build-push-action@v6
        with:
          context: services/streamer
          platforms: linux/amd64
          push: false
          load: true
          tags: lab-bridge-streamer:pr-${{ github.event.pull_request.number }}

      - name: pytest (e2e)
        if: steps.should-run.outputs.run == 'true'
        working-directory: services/streamer
        env:
          STREAMER_TEST_IMAGE: lab-bridge-streamer:pr-${{ github.event.pull_request.number }}
        run: uv run pytest tests/e2e/ -v
```

- [ ] **Step 2: Validate**

```bash
# Just a syntax sniff — actions/checkout is run by GitHub.
yq e '.jobs.streamer.steps | length' .github/workflows/pr-streamer.yml
```

Expected: `12` (or similar integer).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/pr-streamer.yml
git commit -m "ci(streamer): per-service PR workflow"
```

---

## Task 20: release-please.yml — add streamer build + attest

Add the two steps mirroring siteapp/flasher in the existing release-build job.

**Files:**
- Modify: `.github/workflows/release-please.yml`

- [ ] **Step 1: Locate the existing siteapp build + attest pair**

```bash
grep -n "build & push siteapp\|attest siteapp" .github/workflows/release-please.yml
```

- [ ] **Step 2: Add the streamer build step**

After the siteapp attest step, insert:

```yaml
      - name: build & push streamer image
        if: steps.ref.outputs.mode == 'release'
        id: build-streamer
        uses: docker/build-push-action@v6
        with:
          context: services/streamer
          platforms: linux/amd64
          push: true
          provenance: false
          tags: |
            ghcr.io/${{ github.repository_owner }}/lab-bridge-streamer:${{ steps.ref.outputs.version }}
            ghcr.io/${{ github.repository_owner }}/lab-bridge-streamer:latest
          build-args: |
            LAB_BRIDGE_VERSION=${{ steps.ref.outputs.version }}
            LAB_BRIDGE_GIT_SHA=${{ github.sha }}

      - name: attest streamer build provenance
        if: steps.ref.outputs.mode == 'release'
        uses: actions/attest-build-provenance@v4
        with:
          subject-name: ghcr.io/${{ github.repository_owner }}/lab-bridge-streamer
          subject-digest: ${{ steps.build-streamer.outputs.digest }}
          push-to-registry: true
```

- [ ] **Step 3: Validate**

```bash
yq e '.jobs."release-build".steps | length' .github/workflows/release-please.yml
```

Expected: count increased by 2 vs pre-edit.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/release-please.yml
git commit -m "ci(streamer): release-build steps for streamer image"
```

---

## Task 21: Taskfile + helpers + bats route smoke

Add `task` integration and the platform integration smoke check.

**Files:**
- Modify: `Taskfile.yml`
- Modify: `tests/integration/helpers.bash`
- Modify: `tests/integration/test_routes_smoke.bats`

- [ ] **Step 1: Update `Taskfile.yml`**

Find `siteapp:build-and-push` and add nearby:

```yaml
  streamer:build-and-push:
    desc: Build and push the streamer image to GHCR
    cmds:
      - services/streamer/build.sh
```

Find `ops:logs:siteapp` and add nearby:

```yaml
  ops:logs:streamer:
    desc: Tail streamer container logs
    cmds:
      - ssh "$(yq e '.vps.host' config.yaml)" 'cd /srv/lab-bridge && docker compose logs -f streamer'
```

- [ ] **Step 2: Update `tests/integration/helpers.bash`**

Add a function next to `load_siteapp_test_image()`:

```bash
load_streamer_test_image() {
    local image="${STREAMER_TEST_IMAGE:-lab-bridge-streamer:e2e}"
    docker save "$image" | docker exec -i "$VPS_CONTAINER" docker load
}
```

- [ ] **Step 3: Update `tests/integration/test_routes_smoke.bats`**

Find `setup_file()` and add a `load_streamer_test_image` call alongside the existing image loads.

Add test cases at the end of the file:

```bash
@test "/streamer/labs requires authentication" {
    code="$(_through_caddy 'https://127.0.0.1/streamer/labs')"
    [[ "$code" == "302" || "$code" == "401" ]] || { echo "got: $code"; false; }
}

@test "/streamer/whip/dummy is exempt from authelia, returns 404 from streamer" {
    code="$(_through_caddy -X POST 'https://127.0.0.1/streamer/whip/01NOPE' \
        -H 'Content-Type: application/sdp' --data-binary 'v=0')"
    [[ "$code" == "404" || "$code" == "401" ]] || { echo "got: $code"; false; }
}
```

The `401` allowance covers the case where the WHIP token check runs before the URL-pattern dispatch — both prove Authelia was NOT in the path (a 302 would indicate forward_auth redirected to /login).

- [ ] **Step 4: Validate bats syntax**

```bash
bats --no-tempdir-cleanup --pretty --print-output-on-failure --tap \
     tests/integration/test_routes_smoke.bats --filter "non-existent" 2>&1 | head -5
```

Expected: bats parses the file (may say "0 tests selected" because of the filter).

- [ ] **Step 5: Commit**

```bash
git add Taskfile.yml tests/integration/helpers.bash tests/integration/test_routes_smoke.bats
git commit -m "feat(platform): streamer task targets + integration smoke"
```

---

## Task 22: Researcher-facing documentation

Public docs page accessible to researchers.

**Files:**
- Create: `public_docs/en/streaming.md`
- Create: `public_docs/ru/streaming.md`
- Modify: `public_docs/en/manifest.json` (or whatever drives the nav)
- Modify: `public_docs/ru/manifest.json`

- [ ] **Step 1: Inspect the docs nav format**

```bash
find public_docs -name 'manifest*.json' -o -name 'nav*.json' 2>/dev/null | head -5
ls public_docs/en/ | head -20
```

- [ ] **Step 2: Write `public_docs/en/streaming.md`**

```markdown
# Live streaming

When a lab operator allows streaming on their bench, you can watch the
experiment live from your browser.

## Watch a lab

1. Click "Live streams" in the navbar (or visit `/streamer/labs`).
2. Pick the lab you want to watch. Labs without armed streams are greyed
   out — ask the operator to enable a camera.
3. The lab page shows one tile per camera. Streams start automatically
   when you open the page and stop within ~5 seconds of you leaving.

## What you'll see

- One tile per camera ("translation"). Each tile shows the camera label
  and a connection state badge (`connecting…`, `live`, `retrying`, or
  `ended`).
- Use the video controls for fullscreen and picture-in-picture.
- If a stream ends mid-experiment, the page auto-retries 3 times with
  backoff. After that, click the tile to manually retry.

## Limits

- Up to 3 viewers per camera at the same time.
- Video only — no audio in v1.
- Streams are live-only — nothing is recorded.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Lab is greyed out | Operator hasn't armed any camera yet. |
| Tile stuck on "connecting…" | Your network may be blocking UDP ports 50000–50100. Try a different network. |
| Tile shows "ended" | Operator stopped allowing this camera, or the lab disconnected. |
```

- [ ] **Step 3: Write `public_docs/ru/streaming.md`**

```markdown
# Прямые трансляции

Когда оператор лаборатории включает трансляцию, исследователи могут
наблюдать за экспериментом в реальном времени из браузера.

## Подключиться к лаборатории

1. Нажмите «Прямые трансляции» в навигации (или перейдите по адресу
   `/streamer/labs`).
2. Выберите лабораторию. Лаборатории без активных трансляций показаны
   серым — попросите оператора включить камеру.
3. На странице лаборатории появится по одной плитке на каждую камеру.
   Трансляция запускается автоматически при открытии страницы и
   останавливается через ~5 секунд после её закрытия.

## Что вы видите

- По одной плитке на камеру («трансляция»). Каждая плитка содержит
  имя камеры и индикатор состояния (`подключение…`, `в эфире`,
  `повтор…`, `завершено`).
- Используйте элементы управления видео для полноэкранного режима и
  картинки-в-картинке.
- Если трансляция оборвалась, страница автоматически повторит попытку
  трижды с увеличивающимся интервалом. После этого нажмите на плитку
  для ручного повтора.

## Ограничения

- До 3 зрителей на одну камеру одновременно.
- Только видео — звук в v1 не передаётся.
- Только прямой эфир — запись не ведётся.

## Если что-то не работает

| Симптом | Вероятная причина |
|---|---|
| Лаборатория серая | Оператор ещё не включил ни одной камеры. |
| Плитка зависла на «подключение…» | Ваша сеть может блокировать UDP-порты 50000–50100. Попробуйте другую сеть. |
| Плитка показывает «завершено» | Оператор остановил трансляцию или лаборатория отключилась. |
```

- [ ] **Step 4: Add entries to the docs manifests**

Open `public_docs/en/manifest.json` and add a `streaming.md` entry in the appropriate nav section. Mirror the existing pattern (e.g. an entry like `{"title": "Live streaming", "path": "streaming.md"}`).

Do the same for `public_docs/ru/manifest.json` with the Russian title.

- [ ] **Step 5: Lint the docs**

```bash
cd services/siteapp && uv run python -m app.docs_lint ../../public_docs
```

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add public_docs
git commit -m "docs(streaming): researcher-facing user guide (en + ru)"
```

---

## Task 23: Update CLAUDE.md required-check list

Add `pr-streamer / streamer` to the required-checks enumeration so future PRs preserve the invariant.

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Edit CLAUDE.md**

Find the line listing required checks:

```
Required checks: `pr-title`, `pr-siteapp / siteapp`, `pr-flasher / flasher`, `pr-platform / platform`.
```

Replace with:

```
Required checks: `pr-title`, `pr-siteapp / siteapp`, `pr-flasher / flasher`, `pr-streamer / streamer`, `pr-platform / platform`.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude): add pr-streamer to required-checks list"
```

---

## Task 24: PR description prep — branch protection note

The implementation lands as a single PR (or stacked PRs squashed back together). The PR description must include a callout for the manual GitHub UI step that follows merge.

**Files:**
- None (this task produces the PR description content).

- [ ] **Step 1: Draft a PR-description "Required follow-up" block**

When opening the PR, include this section in the description:

```markdown
## ⚠️ Required follow-up after merge

This PR adds a new service (`streamer`) and a new required check.
Immediately after squash-merge, update branch protection on `main`:

1. Settings → Branches → `main` → Edit
2. Under "Require status checks to pass before merging", add:
   - `pr-streamer / streamer`

The check exists on every PR (it always triggers, gated internally on
`paths-filter`), so adding it does not block unrelated docs PRs.

In addition, set the `vps_public_ip` field in:
- `config.yaml` on the laptop (gitignored), and
- the matching GitHub secret used by the deploy workflow if your
  CI flow injects `vps_public_ip` via secrets rather than file rsync.
```

- [ ] **Step 2: No commit — this content goes into the GitHub PR form when you open it.**

---

## Final verification

Once all 24 tasks are committed:

- [ ] Full unit suite passes:

```bash
cd services/streamer && uv run pytest -v
```

- [ ] Full e2e suite passes:

```bash
cd services/streamer && docker build -t lab-bridge-streamer:e2e .
cd services/streamer && uv run pytest tests/e2e/ -v
```

- [ ] Ruff is clean:

```bash
cd services/streamer && uv run ruff check app tests && uv run ruff format --check app tests
```

- [ ] Routes-smoke bats passes against the fake-VPS:

```bash
bats tests/integration/test_routes_smoke.bats
```

- [ ] git log shows clean conventional-commit subjects:

```bash
git log --oneline main..HEAD
```

- [ ] PR opened with the "Required follow-up after merge" block from Task 24.
