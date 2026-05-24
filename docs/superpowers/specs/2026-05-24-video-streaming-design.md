# Video streaming from SerialHop — design

**Status:** draft (brainstormed 2026-05-24)
**Date:** 2026-05-24
**Owner:** khamitovdr
**Related:**
- `docs/superpowers/specs/2026-05-15-per-service-isolation-design.md` (per-service split this builds on)
- `docs/superpowers/specs/2026-05-04-client-discovery-by-username-design.md` (chisel-tunnel discovery pattern)
- `docs/adding-a-service.md` (checklist for adding a new service)

## Motivation

Researchers driving lab-bridge labs from Jupyter today have no way to see what
physically happens during an experiment. A run that produces nothing but a CSV
of sensor readings could be silently failing (a sample is missing, a tube
came loose, the lid is open) and the researcher would only learn at the end.
A live view of the lab bench during the experiment closes that loop.

The constraint set from brainstorming:

- **Sub-second latency.** Researchers want to react to what they see, not
  watch a stale feed. This rules out HLS/DASH and points at WebRTC.
- **No 24/7 streaming.** Cameras stay idle until a viewer actually opens the
  page. The server decides when to start/stop.
- **Operator gates streaming.** Stream is only available if the lab operator
  explicitly "armed" the translation on the SerialHop side (selecting one or
  more cameras, previewing, hitting Allow). Camera enumeration and preview
  are SerialHop-local — the server never sees raw camera feeds it didn't ask
  for.
- **Both researchers and admins are viewers.** Same Authelia groups that gate
  the rest of the platform.
- **One translation = one camera = one stream.** Multi-camera "bundling" is
  not a server concern; the viewer page composes a grid from N independent
  translations.
- **v1 is live-only.** No recording. No audio. 1–3 concurrent viewers per
  stream.

This spec covers the **server-side service and the wire protocol** between
the server and SerialHop. The SerialHop client-side implementation (camera
enumeration, preview UI, "Allow streaming" toggle, WHIP publisher) is a
follow-up that targets this protocol; it is **out of scope here**.

## Goals

- Add a new `streamer` service that:
  - Discovers armed translations on each lab over the existing chisel
    reverse tunnel.
  - Issues start/stop control commands to SerialHop over that same tunnel.
  - Ingests WebRTC video via WHIP from SerialHop on a publicly-addressable
    HTTPS endpoint.
  - Forwards media to ≤3 concurrent WebRTC subscribers per translation via
    WHEP.
  - Serves the viewer-facing HTML and JSON APIs under `/streamer/*`.
- Define the SerialHop-facing HTTP protocol (`GET /api/translations`,
  `POST /api/translations/{id}/start`, `POST /api/translations/{id}/stop`)
  so SerialHop can be implemented against a stable contract.
- Integrate the new service with the existing platform invariants:
  per-service CI workflow, Authelia auth, Caddy routing, chisel tunnel for
  control, single-component release-please.

## Non-goals

- SerialHop client implementation (separate package, separate plan).
- Recording / playback / retention. v1 is live-only.
- Audio. v1 is video-only.
- Adaptive bitrate, simulcast, or quality picker.
- Per-lab access control (every authenticated researcher/admin sees every
  lab — matches today's `/api/public/labs`).
- Browser fan-out beyond 3 viewers / stream. The SFU is `aiortc`; swapping
  for MediaMTX or LiveKit later is a localized internal change.
- TURN/STUN. The streamer container is publicly addressable; SerialHop and
  browsers dial outbound to it directly. Empty `ice_servers` array shipped
  in the start command; protocol leaves the door open.
- Snapshot / frame-grab UI.

## Approach decision

Three alternatives were considered:

- **A — New `streamer` service, fully self-contained.** Owns discovery,
  control plane, signaling, SFU, and the viewer pages. siteapp is untouched.
- **B — Fold streaming into siteapp.** Add `aiortc` + signaling routes to
  siteapp. Zero new services.
- **C — MediaMTX as a stack-only component.** Drop in a Go-based SFU; siteapp
  becomes the only Python piece, doing control-plane glue.

**Decision: Approach A.** Per the per-service-isolation invariant in
`CLAUDE.md`, each service lives at `services/<name>/` with its own image,
CI workflow, and dependencies. `aiortc` pulls native deps (PyAV, libsrtp,
libavcodec) that have no business in the siteapp image; long-lived WebRTC
peer connections do not belong in the same event loop that renders docs.
MediaMTX is overkill for 1–3 viewers, no audio, no recording, and its auth
model doesn't natively integrate with Authelia.

A pre-revision of Approach A had siteapp acting as a discovery/control
intermediary. That coupling is unnecessary: `clients.json` is a *file* the
streamer can mount the same way flasher does, SerialHop is the source of
truth for which translations exist (operator picks cameras on the lab
machine where they physically exist), and Caddy's `forward_auth` applies
Authelia uniformly to every upstream. siteapp's only touchpoint is an
optional hyperlink from its home page to `/streamer/labs`.

## Architecture overview

```
            ┌─ browser viewer ─────────────────────────────────┐
            │  GET  /streamer/labs            (Authelia-gated) │
            │  GET  /streamer/labs/<lab>      (Authelia-gated) │
            │  POST /streamer/whep/<lab>/<id> (Authelia-gated) │
            └──────────────┬────────────────────────────────────┘
                           │ HTTPS (signaling) + UDP 50000-50100 (RTP)
                           ▼
            ┌─ Caddy ─────────────────────────────────────────┐
            │  forward_auth /streamer/* → authelia            │
            │  /streamer/whip/* EXCLUDED from forward_auth    │
            └──────────────┬────────────────────────────────────┘
                           │ reverse_proxy streamer:8000
                           ▼
            ┌─ services/streamer/ (this spec) ────────────────┐
            │  main.py  config.py  auth.py                    │
            │  pages.py  whip.py  whep.py  sfu.py (aiortc)    │
            │  session_manager.py  discovery.py  control.py   │
            │  roster.py                                      │
            │  Session state in-memory only                   │
            └──────────────┬────────────────────────────────────┘
                           │ on labnet:
                           │   reads clients.json (roster, RO)
                           │   GET  chisel:<port>/api/translations
                           │   POST chisel:<port>/api/translations/{id}/start
                           │   POST chisel:<port>/api/translations/{id}/stop
                           ▼
            ┌─ chisel (reverse tunnels per lab) ──────────────┐
            └──────────────┬───────────────────────────────────┘
                           │ chisel client (over the internet)
                           ▼
            ┌─ SerialHop (per lab machine) — out of scope ────┐
            │  /api/translations*                              │
            │  WHIP publisher → https://<host>/streamer/whip/* │
            │  Outbound UDP to <VPS_PUBLIC_IP>:50000-50100     │
            └──────────────────────────────────────────────────┘
```

Control plane (start/stop) rides the existing chisel reverse tunnel; media
plane (RTP/SRTP) goes outbound from SerialHop directly to the streamer's
host UDP ports. No new chisel tunnel.

## Section 1 — Data model

A **translation** is the SerialHop side of a single live camera publish.
SerialHop owns it; streamer never persists translation metadata.

### 1.1 On SerialHop (shape defined by this spec, implementation deferred)

```json
{
  "id": "cam-0",
  "label": "Microscope side view",
  "armed": true,
  "camera_hint": "/dev/video0"
}
```

`id` is stable across SerialHop restarts. `armed` reflects the operator's
"Allow streaming" toggle. `camera_hint` is internal to SerialHop's operator
UI; it is not sent to the server.

### 1.2 On the streamer (runtime in-memory only)

```
labs_index:   {lab_name → [TranslationDescriptor]}        # discovery cache
sessions:     {(lab_name, translation_id) → Session}      # exists iff a session is active

TranslationDescriptor:
  id: str
  label: str

Session:
  session_id:        ULID                          # one-shot, regenerated on every CREATED
  publish_token:     bytes | None                  # burned on first WHIP redemption
  state:             CREATED | PUBLISHING | DRAINING
  publisher_pc:      aiortc.RTCPeerConnection | None
  publisher_track:   aiortc.MediaStreamTrack | None
  publish_ready:     asyncio.Event
  subscribers:       {subscriber_id → RTCPeerConnection}
  last_activity:     monotonic timestamp
  debounce_task:     asyncio.Task | None
```

No on-disk state. Streamer restart clears everything; SerialHop publishers
detect the dead connection (RTP timeouts, DTLS failure) and tear down their
own captures.

## Section 2 — SerialHop-facing protocol (the wire contract)

Three endpoints, hosted by SerialHop's local API, reachable from the streamer
container via `http://chisel:<port>` (the existing reverse tunnel). All three
have an unauthenticated body — trust is the labnet ↔ chisel scope, identical
to today's `/agent/info`.

### 2.1 Discovery — `GET /api/translations`

Streamer polls each lab when it needs a fresh view of what's armed.

- Cache TTL inside streamer: `STREAMER_DISCOVERY_CACHE_TTL_S` (default 10 s).
- Force-refreshed when a viewer loads the picker page.
- Request timeout: `STREAMER_DISCOVERY_REQUEST_TIMEOUT_S` (default 1.0 s).

**Response 200:**
```json
{
  "translations": [
    { "id": "cam-0", "label": "Microscope side view" },
    { "id": "cam-1", "label": "Plate reader top" }
  ]
}
```

- `translations` may be empty.
- Only **armed** translations appear.
- Unknown extra fields tolerated — protocol is additive.

**Failure modes:** any non-200 / timeout / connection error means "this lab
currently exposes no translations". Streamer logs at INFO and surfaces the
lab as inactive on the picker.

### 2.2 Start — `POST /api/translations/{id}/start`

Streamer issues this when the first viewer arrives for a translation that
has no active publisher.

**Request body:**
```json
{
  "session_id": "01HXYZ…",
  "whip_url":  "https://lab.example.com/streamer/whip/01HXYZ…",
  "whip_token": "tk_<32-bytes-base64url>",
  "ice_servers": []
}
```

- `session_id` is a ULID generated by streamer; opaque to SerialHop.
- `whip_url` is the absolute URL SerialHop must POST its WHIP SDP offer to.
- `whip_token` is a one-shot bearer with validity
  `STREAMER_WHIP_TOKEN_VALIDITY_S` (default 60 s). SerialHop must send it as
  `Authorization: Bearer <whip_token>` on the WHIP POST.
- `ice_servers` is empty in v1; included so STUN/TURN can be added later
  without protocol changes.

**Responses:**

| Code | Meaning | SerialHop action |
|---|---|---|
| 202 Accepted | Will publish | Open WHIP to `whip_url`, push the camera track |
| 404 Not Found | Unknown `id` (race: was armed at discovery, disarmed since) | None |
| 409 Conflict | Already publishing this `id` | Return current session: `{"session_id":"…"}`. No new capture. |
| 503 Service Unavailable | Camera busy / hardware failure | None; streamer surfaces "camera unavailable" to viewer |

**Idempotency:** a duplicate `start` with the same `session_id` is a no-op
(409 with the existing `session_id`).

### 2.3 Stop — `POST /api/translations/{id}/stop`

Streamer issues this when the last viewer leaves and the debounce window
expires.

**Request body:**
```json
{ "session_id": "01HXYZ…" }
```

**Responses:**

| Code | Meaning |
|---|---|
| 204 No Content | Stopped (or was already stopped) |
| 409 Conflict | A different `session_id` is currently active — SerialHop **ignores** the stop |

The `session_id` guard prevents this race:

```
streamer:                                      SerialHop:
  sends stop (session_id=A) ───────────╮       still publishing A
                                       │
  first viewer leaves                  │
  debounce expires                     │
  new viewer arrives                   │
  generates session_id=B               │
  sends start(B) ──────────────────────┼──►    starts publishing B
                                       │       (A torn down by SerialHop on start B)
  (stale stop A arrives) ──────────────╯       checks session_id != B → ignores
```

Without the guard, a stale stop would kill the just-started B session.

### 2.4 Trust boundary

The three endpoints above are **unauthenticated in the request**. The trust
boundary is the chisel reverse tunnel: only containers on `labnet` can reach
`chisel:<port>`, and SerialHop registered its tunnel with the password from
`compose/chisel/users.json`. Same posture as today's `/agent/info`,
`flasher` calls, and siteapp's `labs.py` aggregator.

The `whip_token` (sent on the WHIP POST, *not* on start/stop) gates the
public, internet-facing WHIP endpoint — see Section 3.

### 2.5 Explicitly NOT in this protocol

- No "preview" endpoint — preview is SerialHop-local.
- No "list cameras" endpoint — cameras are SerialHop-local; the server only
  ever sees translations.
- No reverse channel from SerialHop to streamer other than WHIP itself.
- No SerialHop-side authentication of start/stop bodies — chisel scope is
  the gate.
- No multi-tenant `id` namespacing within a single SerialHop — `id` only
  needs to be unique within one lab. The streamer-wide key is
  `(lab_name, translation_id)`.

## Section 3 — WHIP / WHEP signaling

WHIP (IETF RFC 9725) and WHEP carry the SDP offer/answer over plain HTTPS
POST with `application/sdp` bodies. Media flows outside Caddy on UDP.

### 3.1 Endpoint table

| URL | Method | Auth | Purpose |
|---|---|---|---|
| `/streamer/whip/{session_id}` | POST | `Authorization: Bearer <whip_token>` | SerialHop pushes media; body = SDP offer (sendonly video). Response 201, body = SDP answer. |
| `/streamer/whip/{session_id}` | DELETE | same bearer | SerialHop tears down its publish |
| `/streamer/whep/{lab}/{translation_id}` | POST | Authelia session (researchers OR admins) | Viewer subscribes; body = SDP offer (recvonly video). Response 201, body = SDP answer, `Location` header. |
| `/streamer/whep/{lab}/{translation_id}/{sub_id}` | DELETE | same session | Viewer unsubscribes (also fires from `pagehide`) |

Caddy excludes `/streamer/whip/*` from `(authelia_required)` — its sole auth
is the one-shot bearer. Every other `/streamer/*` path imports the snippet.

### 3.2 WHIP handler logic

```
on POST /streamer/whip/{session_id}:
  session = sessions.get(session_id)
  if session is None:                  # streamer didn't issue this
    return 404
  if session.publish_token is None:    # already redeemed
    return 410
  if Authorization bearer != session.publish_token:
    return 401
  session.publish_token = None         # one-shot, burn now

  pc = RTCPeerConnection()
  pc.on("track", lambda t:
    session.publisher_track = t;
    session.publish_ready.set();
    session.state = PUBLISHING)
  pc.on("connectionstatechange",
    lambda: _on_publisher_state(session, pc))
  await pc.setRemoteDescription(offer_sdp)
  await pc.setLocalDescription(await pc.createAnswer())
  session.publisher_pc = pc
  return 201,
    body = pc.localDescription.sdp,
    Location: /streamer/whip/{session_id}
```

### 3.3 WHEP handler logic

The non-trivial case: viewer arrives before publisher.

```
on POST /streamer/whep/{lab}/{translation_id}:
  key = (lab, translation_id)
  async with sessions_lock[key]:
    session = sessions.get(key)
    if session is None:
      if not _is_armed(lab, translation_id):    # consult discovery cache
        return 404
      session = _create_session(key)            # new session_id + whip_token
      try:
        await control.start(lab, translation_id, session)
      except CameraBusy:
        return 503
      except ControlError:
        sessions.pop(key, None)
        return 502

  session.last_activity = now()
  _cancel_drain(session)

  try:
    await wait_for(session.publish_ready,
                   timeout=STREAMER_PUBLISH_READY_TIMEOUT_S)
  except TimeoutError:
    return 504

  if len(session.subscribers) >= STREAMER_MAX_SUBSCRIBERS_PER_SESSION:
    return 429

  sub_pc = RTCPeerConnection()
  sub_pc.addTrack(session.publisher_track)
  sub_pc.on("connectionstatechange",
    lambda: _on_subscriber_state(session, sub_id, sub_pc))
  await sub_pc.setRemoteDescription(offer_sdp)
  await sub_pc.setLocalDescription(await sub_pc.createAnswer())
  sub_id = ulid()
  session.subscribers[sub_id] = sub_pc
  return 201,
    body = sub_pc.localDescription.sdp,
    Location: /streamer/whep/{lab}/{translation_id}/{sub_id}
```

`sessions_lock` is a per-key `asyncio.Lock` to serialize "first viewer"
session creation when two WHEPs race.

### 3.4 ICE / NAT in v1

- Streamer binds **host candidates only**. Candidates rendered as
  `<STREAMER_PUBLIC_IP>:<udp_port>/udp`.
- No STUN, no TURN. SerialHop and browsers dial outbound to the publicly
  addressable VPS; outbound UDP through typical NATs needs no help.
- `ice_servers` passed to peers is `[]`. The Section 2.2 `ice_servers` field
  in the start command is reserved for future protocol-stable additions.

### 3.5 Compose plumbing

`compose/docker-compose.yml.tmpl` gains:

```yaml
streamer:
  image: __STREAMER_IMAGE__
  restart: unless-stopped
  environment:
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
  ports:
    - "50000-50100:50000-50100/udp"
  volumes:
    - ./siteapp/clients.json:/etc/streamer/clients.json:ro
    - ./streamer_data:/data
  networks: [labnet]
```

`./siteapp/clients.json` is the rendered roster file — the path is already
shared by flasher under the same compose template. The path string carries
the historical "siteapp" prefix; we keep it consistent across services
rather than rename.

`compose/Caddyfile.tmpl` adds:

```caddy
handle /streamer/whip/* {
    reverse_proxy streamer:8000
}

handle /streamer/* {
    import authelia_required
    reverse_proxy streamer:8000
}
```

Caddy auto-sorts `handle` blocks by path specificity, so `/streamer/whip/*`
matches before `/streamer/*` regardless of source order — but we keep the
WHIP block first in the template for human readability.

`compose/pins.yaml` gets:

```yaml
streamer:
  image: ghcr.io/<owner>/lab-bridge-streamer
  sha:   sha256:<filled-on-first-build>
```

`config.yaml` and `compose/config.ci.yaml.tmpl` get a new top-level field:

```yaml
vps_public_ip: 111.88.145.138    # CI template: 127.0.0.1
```

`scripts/lib/render.sh` reads it and substitutes into the compose template.

## Section 4 — Viewer flow & UI

### 4.1 Page routes (HTML, server-rendered)

| URL | Purpose |
|---|---|
| `/streamer/labs` | Lab picker. One card per roster entry. Active iff discovery returns ≥1 translation AND chisel tunnel is up. Inactive cards are greyed, non-clickable, subtitled "no streams allowed by operator". |
| `/streamer/labs/{name}` | Viewing page. Server-renders a grid skeleton; JS hydrates one tile per translation. |

Both extend `base.html` style — Caddy injects the shared navbar; streamer's
own static dir holds `streamer.css` + `streamer.js` that reuse the platform
design tokens.

### 4.2 JSON API (consumed by streamer's own pages)

| URL | Returns |
|---|---|
| `GET /streamer/api/labs` | `[{ "name": "khamit_desktop", "active": true, "translation_count": 2 }, ...]` |
| `GET /streamer/api/labs/{name}/translations` | `[{ "id": "cam-0", "label": "Microscope side view" }, ...]` |

Both are Authelia-gated. The picker is server-rendered with the same data
for first-paint; the JSON endpoints power 15 s background polling for
"newly-armed translation" discovery without a page reload.

### 4.3 Per-tile JS (sketch)

```js
async function attach(tileEl, lab, translationId) {
  const pc = new RTCPeerConnection();
  pc.addTransceiver("video", { direction: "recvonly" });
  pc.ontrack = (e) => {
    tileEl.querySelector("video").srcObject = e.streams[0];
  };
  pc.onconnectionstatechange = () =>
    updateStateBadge(tileEl, pc.connectionState);

  await pc.setLocalDescription(await pc.createOffer());

  const resp = await fetch(`/streamer/whep/${lab}/${translationId}`, {
    method: "POST",
    headers: { "Content-Type": "application/sdp" },
    body: pc.localDescription.sdp,
  });
  if (resp.status === 504) {
    scheduleRetry(tileEl, lab, translationId);
    return;
  }
  if (!resp.ok) {
    renderError(tileEl, resp.status);
    return;
  }

  tileEl.dataset.subscriberLocation = resp.headers.get("Location");
  await pc.setRemoteDescription({
    type: "answer",
    sdp: await resp.text(),
  });
}

window.addEventListener("pagehide", () => {
  document.querySelectorAll("[data-subscriber-location]").forEach(t => {
    fetch(t.dataset.subscriberLocation, {
      method: "DELETE", keepalive: true,
    });
  });
});
```

### 4.4 Visuals & UX

- Grid: `grid-template-columns: repeat(auto-fit, minmax(360px, 1fr))`.
- `<video autoplay muted playsinline controls>` — browser-native fullscreen
  and PiP for free.
- Tile footer: translation label + connection state badge
  (`connecting…` / `live` / `retrying` / `ended`).
- 504 / disconnect: 3 automatic retries with 2 s / 5 s / 15 s backoff, then
  "ended — click to retry" CTA.
- A lab currently offline from chisel: picker greys the card; direct visit
  to `/streamer/labs/<name>` renders empty-state with a Retry button.

### 4.5 Deferred to follow-ups

- Live "translation added" server-push (WebSocket / SSE) — v1 uses 15 s / 30 s
  polling on picker / viewing pages.
- Per-lab access control.
- Mobile polish (the grid degrades to single-column acceptably).
- Snapshot / single-frame capture.
- Adaptive bitrate / quality picker.

## Section 5 — Auth model

| Surface | Caller | Mechanism |
|---|---|---|
| `/streamer/labs`, `/streamer/labs/{name}`, `/streamer/api/labs*`, `/streamer/whep/*` | Browser viewer | Authelia `forward_auth` at Caddy; streamer reads `Remote-User` / `Remote-Groups`; required group is `researchers` OR `admins`. |
| `/streamer/whip/{session_id}` | SerialHop | Caddy excludes from `(authelia_required)`. Streamer validates `Authorization: Bearer <whip_token>`, then burns the token. |
| `chisel:<port>/api/translations/*` | Streamer → SerialHop | No auth header; chisel-tunnel-scoped trust. |

`authelia/configuration.yml` gains one access-control rule (mirroring
`/grafana` and `/flash`):

```yaml
- domain: "*"
  resources: ["^/streamer($|/.*)"]
  policy: one_factor
  subject: ["group:researchers", "group:admins"]
```

The `(authelia_required)` snippet's existing `handle_response @forbidden`
hook routes 403s through `/_errors/403`, so a logged-in viewer without a
matching group sees the standard error page.

No per-lab ACL in v1. Future extension: a `viewers: ["alice", "bob"]` field
per chisel client in `config.yaml`, rendered into `clients.json`, checked in
streamer against `Remote-User`.

## Section 6 — Session lifecycle & error handling

### 6.1 Session state machine

```
                first WHEP                publisher WHIP
   (no state) ──────────► CREATED ────────────────────► PUBLISHING
                  │             │                            │
                  │             │ 10 s publish timeout       │ last subscriber leaves
                  │             ▼                            ▼
                  │          STOPPED ◄── debounce expires ── DRAINING
                  │             ▲                            │ new subscriber
                  │             │                            ▼
                  └─────────────┴───────────────────────  PUBLISHING (back to)
```

| Transition | Trigger | Action |
|---|---|---|
| → CREATED | First WHEP for `(lab, tid)` | Create Session, generate `session_id` + `whip_token`, POST start to SerialHop |
| CREATED → PUBLISHING | WHIP arrives, publisher track event | Set `publisher_track`; signal `publish_ready`; pending WHEP futures resolve |
| CREATED → STOPPED | 10 s elapsed, no WHIP | Pending WHEPs resolve with 504; POST stop; drop Session |
| PUBLISHING → DRAINING | Last subscriber's PC `closed` or DELETE on Location | Start `STREAMER_DRAIN_DEBOUNCE_S` (5 s) timer |
| DRAINING → PUBLISHING | New WHEP arrives | Cancel debounce, attach new subscriber |
| DRAINING → STOPPED | Debounce expires | POST stop with current `session_id`; close all PCs; drop Session |
| PUBLISHING → STOPPED | Publisher PC state ∈ {`failed`, `closed`} | Close all subscriber PCs; best-effort POST stop; drop Session |

### 6.2 Failure modes

| Failure | Detection | User-visible result |
|---|---|---|
| Lab's chisel tunnel down at picker load | Discovery TCP-dial fail | Picker greys the lab card |
| Lab's chisel tunnel drops between discovery and first WHEP | `control.start` raises `ControlError` | WHEP 502 → tile "lab unavailable", auto-retry |
| SerialHop 503 on start (camera busy) | Synchronous on first WHEP | WHEP 503 → tile "camera unavailable" |
| Publisher never arrives within 10 s | `publish_ready` timeout | WHEP 504 → tile retries with backoff |
| Publisher disconnects mid-stream | aiortc `connectionstatechange` → failed | Subscribers' tracks end; tile "ended" + auto-retry |
| Operator hits "disarm" on SerialHop | SerialHop tears down its WHIP PC | Same as publisher disconnect; on next load, discovery omits the translation |
| Streamer restart | All in-memory state lost | Publisher PCs fail; SerialHop tears down captures on its own; viewer reload triggers a fresh start |
| Two viewers race to be "first" | Both WHEP handlers see no session | `sessions_lock[key]` serializes; loser awaits `publish_ready` |

### 6.3 Operational knobs (env-tunable)

| Variable | Default | Meaning |
|---|---|---|
| `STREAMER_PUBLISH_READY_TIMEOUT_S` | 10 | WHEP wait budget for publisher |
| `STREAMER_DRAIN_DEBOUNCE_S` | 5 | Grace period before stopping after last viewer leaves |
| `STREAMER_DISCOVERY_CACHE_TTL_S` | 10 | TTL on per-lab `/api/translations` cache |
| `STREAMER_DISCOVERY_REQUEST_TIMEOUT_S` | 1.0 | HTTP timeout on a discovery probe |
| `STREAMER_WHIP_TOKEN_VALIDITY_S` | 60 | Max age of an unredeemed `whip_token` |
| `STREAMER_MAX_SUBSCRIBERS_PER_SESSION` | 3 | Soft cap; 4th+ subscriber returns 429 |

### 6.4 Explicitly NOT in v1

- No persistence — Session state is in-memory; restart resets everything.
- No exponential backoff on `control.start` failures — surface fast (504/502)
  rather than hold the WHEP open.
- No `/metrics` endpoint. If observability becomes a need, expose Prometheus
  metrics in a follow-up (platform already runs Prometheus + cadvisor).
- No graceful drain on streamer shutdown — restarts kick all viewers.

## Section 7 — Testing

Three layers, per `CLAUDE.md`.

### 7.1 Unit — `services/streamer/tests/test_*.py`

Pure-logic, no containers. Run by `pr-streamer.yml`'s unit step.

| File | Covers |
|---|---|
| `test_roster.py` | `clients.json` parsing, mirroring `services/siteapp/app/clients.py:load_roster` |
| `test_session_manager.py` | State machine (all branches of 6.1), debounce timing with mocked clock, `asyncio.Lock` on race |
| `test_discovery.py` | Cache TTL, failure-as-empty, request timeout |
| `test_tokens.py` | `whip_token` entropy, one-shot burn, expiry |
| `test_control.py` | start/stop request shape against a mocked httpx client; `session_id` guard on stop |

### 7.2 Service e2e — `services/streamer/tests/e2e/`

Runs in `pr-streamer.yml`'s e2e step against the just-built image. Mirrors
`services/siteapp/tests/e2e/` and `services/flasher/tests/e2e/`.

`compose.yml` brings up:
- `streamer` (just-built image).
- `serialhop-stub` — a small FastAPI app pretending to be `chisel:<port>`,
  aliased as `chisel` on the test network. Responds to
  `/api/translations`, `/api/translations/{id}/start`,
  `/api/translations/{id}/stop`. Records calls for assertions.
- Test driver uses `aiortc` as both publisher (a synthetic test-pattern
  `VideoStreamTrack`) and subscriber (`MediaBlackhole` sink + a
  frame-counting recorder fixture).

| Test | Asserts |
|---|---|
| `test_picker.py` | `/streamer/api/labs` reflects roster ∩ discovery; lab with no armed translations is `active=false` |
| `test_whip_auth.py` | Missing/wrong bearer → 401; replay → 410 |
| `test_publish_only_on_first_viewer.py` | Zero `/start` calls while no WHEP arrives; first WHEP → exactly one `/start` |
| `test_whep_waits_for_publisher.py` | WHEP before publisher resolves once stub's `/start` is answered by a test publisher |
| `test_whep_timeout.py` | No publisher within 10 s → WHEP 504 |
| `test_media_flows.py` | Subscriber receives ≥30 frames in 2 s |
| `test_drain_debounce.py` | Last subscriber leaves → `/stop` only after `STREAMER_DRAIN_DEBOUNCE_S` |
| `test_session_id_guard.py` | Stale stop with old `session_id` ignored |
| `test_publisher_drop.py` | Stub aborts publisher mid-stream → subscriber's track ends; new WHEP triggers fresh `/start` with new `session_id` |
| `test_two_viewers_share_publisher.py` | Two WHEPs for `(lab, tid)` → exactly one `/start` recorded |

### 7.3 Platform integration — `tests/integration/`

The thin "everything wires together" tier. No streamer behaviour tests
here — those live in e2e.

Extend `tests/integration/test_routes_smoke.bats`:
- `GET /streamer/labs` unauthenticated → 302 to `/login` (Authelia chain).
- `POST /streamer/whip/dummy` unauthenticated → 401 from streamer (proves
  Caddy did **not** apply `authelia_required` to the WHIP path).
- `GET /healthz` on streamer (via internal port) → 200.

No new bats matrix cell; the existing `routes-smoke` cell already brings up
the full fake-VPS stack.

### 7.4 CI plumbing

Per `docs/adding-a-service.md`:
- `.github/workflows/pr-streamer.yml` — `dorny/paths-filter` gating, unit +
  e2e steps. Required check name: `pr-streamer / streamer`.
- Branch protection updated to add the new required check (manual step,
  called out in the implementation plan).
- `release-please` unchanged (single-component model — root `VERSION`
  already covers `services/streamer/VERSION` via `extra-files`).
- `pins.yaml` gets `streamer:` image SHA on first build; CI publishes to
  GHCR exactly like siteapp/flasher.
- `renovate.json` regexes auto-cover the new service path.

## Implementation order (rough)

1. Scaffold `services/streamer/` per `docs/adding-a-service.md`.
2. Roster + discovery (`roster.py`, `discovery.py`) with unit tests; no SFU
   yet.
3. Session state machine + control plane stubs (`session_manager.py`,
   `control.py`); unit-tested in isolation.
4. WHIP / WHEP handlers + aiortc wiring (`whip.py`, `whep.py`, `sfu.py`).
5. HTML pages + JS (`pages.py`, `templates/`, `static/streamer.js`).
6. Compose plumbing + Caddyfile + Authelia rule.
7. e2e harness + tests.
8. `.github/workflows/pr-streamer.yml`.
9. Bats smoke additions.
10. Documentation: `public_docs/` page for researchers; admin note in
    `docs/adding-a-service.md` if any pattern was bent.

## Open questions

None at spec time. Issues to revisit during implementation will be tracked
in the plan, not here.
