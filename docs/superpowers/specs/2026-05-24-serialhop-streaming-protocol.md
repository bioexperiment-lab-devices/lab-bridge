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
| `whip_token` | string | One-shot bearer for the WHIP POST. Send as `Authorization: Bearer <whip_token>`. Validity ≤60 s — your WHIP POST must complete within that window. After redemption the token is burned (replay → 410). |
| `ice_servers` | array of `RTCIceServer` objects | STUN/TURN configuration for your WebRTC peer connection. May be empty (v1 ships `[]`). Pass through to `RTCPeerConnection` as-is. |

**Response codes:**

| Code | When |
|---|---|
| 202 Accepted | SerialHop will publish. Response body: empty or `{}`. SerialHop now opens WHIP (see Section 2). |
| 404 Not Found | `{id}` is unknown to SerialHop. Body: `{ "error": "unknown translation" }`. |
| 503 Service Unavailable | Camera busy / hardware failure. Body: `{ "error": "<human description>" }`. |

**Replace-on-conflict:** if `{id}` is already publishing under a *different*
`session_id` when `start` arrives, SerialHop must **tear down the old
publish and start the new one** (close the old WHIP peer connection,
release the old `session_id`, then publish the new one). Return 202.
Rationale: the server's request is the source of truth; refusing would
leave the new viewer stuck.

**Idempotency:** if `start` arrives with a `session_id` SerialHop already
recognises as the *current* active session for `{id}`, return 202 with
empty body (no-op). This handles retries from the server's HTTP client.

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

**Why the 409 guard matters:** events run top-to-bottom in time —

```
time   streamer side                        SerialHop side
 │                                          publishing session A
 │     last viewer leaves                   │
 │     debounce expires                     │
 │     POST stop (sid=A) ──────────╮        │  (in flight)
 │     drop session A locally       │       │
 │                                  │       │
 │     new viewer arrives           │       │
 │     create session B             │       │
 │     POST start (sid=B) ──────────┼──►   stops A (replace-on-conflict),
 │                                  │       starts publishing B → 202
 │                                  │       publishing session B
 │     (stale stop A arrives) ──────╯       sid=A != active=B → 409,
 │                                          ignores stop
 ▼                                          publishing session B (preserved)
```

Without the 409 guard on stop, the stale `stop(A)` would kill the freshly
started `B`. With it, SerialHop preserves the new session.

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
```

No `Authorization` header is required — the bearer was burned on the
successful POST in 2.3. The server identifies the session purely from the
URL path (`session_id`). Sending the `Authorization` header is harmless and
ignored.

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
      translations, 404 for unknown id, 503 for hardware unavailable.
- [ ] A `start` with a `session_id` matching the current active session
      returns 202 with empty body (idempotent retry).
- [ ] A `start` with a *different* `session_id` while one is publishing
      replaces the old session and returns 202.
- [ ] On 202, WHIP publish begins within 10 seconds of receipt and the
      WHIP POST is sent within 60 seconds (token validity window).
- [ ] WHIP uses `Authorization: Bearer {whip_token}` exactly once per
      session.
- [ ] SDP offer is sendonly video, H.264 or VP8.
- [ ] First video frame arrives within 5 seconds of WHIP 201.
- [ ] `POST /api/translations/{id}/stop` returns 204 for matching
      `session_id`, 409 (with `active_session_id`) for mismatched.
- [ ] On 204, DELETE `{whip_url}` (no Authorization header needed) and
      close the camera.
- [ ] Operator disarm proactively tears down publish + DELETEs `{whip_url}`.
- [ ] On SerialHop restart, all in-flight `session_id` state is dropped;
      subsequent stops for unknown sessions return 204 (idempotent).
