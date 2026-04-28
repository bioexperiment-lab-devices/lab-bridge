# Chisel client — log forwarding implementation spec

**Date:** 2026-04-28
**Status:** Approved (server-side merged; client-side not yet implemented)
**Audience:** Developers of `lab_devices_client` (separate repository).
**Companion doc:** [2026-04-28-chisel-client-logs-design.md](./2026-04-28-chisel-client-logs-design.md) — server-side design and rationale. This file is the contract the client must honor.

## Purpose

Today, when something misbehaves in a remote lab, the operator has to ask lab
staff to ZIP and email two log files (`lab_devices_client.log`,
`lab_devices_client_stderr.log`). The server side now hosts an internal Loki +
Grafana stack, reachable from the client only through the existing chisel
session. This spec describes the changes needed in `lab_devices_client` so it
streams its stdout/stderr to that Loki, where the operator can browser-tail and
search them at `https://<vps-host>/grafana/`.

## Goals

- Ship every line written to `lab_devices_client.log` and
  `lab_devices_client_stderr.log` over the existing chisel tunnel to Loki, in
  near real-time.
- Survive transient network drops — buffer in memory, drop oldest on overflow,
  never block the device-control hot path.
- Self-identify each stream with stable labels (client name, stream,
  binary version) so the operator can filter in Grafana.
- No new public network surface, no new server credentials. Reuse the chisel
  auth that's already provisioned per device.

## Non-goals

- Persistent on-disk buffering of unsent log lines (rotated log files on the
  client remain the durable record; Loki is a queryable mirror).
- Structured-log inference, metric extraction, or PII scrubbing — the line
  body is forwarded verbatim.
- Client-side searching, archival, or compaction.
- Authenticating the push to Loki at the application layer (chisel auth is
  the gate; mislabeling is treated as an integrity issue, not a
  confidentiality breach — see "Identity" below).

## What changes on the client

### 1. Extend the chisel session with one forward tunnel

The existing chisel client invocation already provides one **reverse** tunnel
(`R:0.0.0.0:<reverse_port>:127.0.0.1:<local_device_port>`) for the device
port. Add one **forward** tunnel in the same invocation so that connecting to
`127.0.0.1:3100` on the lab machine reaches `loki:3100` on the in-VPS
`labnet` Docker network.

Final invocation:

```sh
chisel client \
    --auth <name>:<password> \
    <vps-host>:<chisel_port> \
    R:0.0.0.0:<reverse_port>:127.0.0.1:<local_device_port> \
    127.0.0.1:3100:loki:3100
```

The server side has been updated (commit history on `lab-bridge` `main`) so
that every chisel user's allow-list now grants this exact forward target. An
unauthenticated client cannot open this tunnel.

### 2. Push logs to Loki via HTTP

Every batch of log lines POSTs to `http://127.0.0.1:3100/loki/api/v1/push`
(plain HTTP — chisel handles confidentiality on the wire). The endpoint is
Loki's standard JSON push API.

Request:

```
POST http://127.0.0.1:3100/loki/api/v1/push
Content-Type: application/json
Content-Encoding: gzip                # optional but recommended
```

Body shape (one or more streams, one or more values per stream):

```json
{
  "streams": [
    {
      "stream": {
        "client":  "microscope-1",
        "stream":  "stdout",
        "service": "lab_devices_client",
        "version": "1.4.2"
      },
      "values": [
        ["1714329600000000000", "<verbatim log line>"]
      ]
    }
  ]
}
```

The first element of each `values` entry is the timestamp **in nanoseconds
since the Unix epoch, as a string**. The second is the verbatim log line as a
single string — preserve any structured framing (timestamps, levels, request
ids) the client already writes. Loki does not parse the line body.

A successful push returns HTTP 204 (no body). Non-2xx responses must be
retried per "Failure handling" below.

### 3. Required labels (and only these labels)

| Label | Value | Source |
|---|---|---|
| `client` | The chisel auth username (e.g. `microscope-1`). | Chisel client config. Must match. |
| `stream` | `stdout` or `stderr`. | Which file/handle the line came from. |
| `service` | Constant string `lab_devices_client`. | Hardcoded. |
| `version` | The client binary's semver string (e.g. `1.4.2`). | Build-time embedded; same value for the lifetime of the process. |

**Do not add any other labels.** Free-form fields (request ids, timestamps,
levels, error codes) belong in the line body, not in labels — adding them to
the label map will explode Loki's index. The server enforces a hard ceiling
of 15 labels per stream and 1024 chars per value, so cardinality bugs will be
rejected loudly rather than silently degrading the deployment.

### 4. Batching and buffering

- **Flush trigger:** whichever comes first — every **2 seconds** or every
  **500 lines**.
- **Group by stream:** stdout and stderr lines may share one POST, but each
  must be in its own `streams[]` entry with its own `stream` label map.
  (Different label maps in the same POST are fine; mixing them in one stream
  block is not.)
- **In-memory buffer:** up to **~10,000 lines total** across both streams.
  On overflow, drop the **oldest** lines to make room for new. Increment a
  local counter (`logs_dropped_total` or similar) and emit it as part of the
  next successful push so the operator can detect overruns.
- **Failure handling:** on push failure (chisel down, Loki 5xx, network
  drop), do **not** block the writer. Hold the batch in memory and retry
  with exponential backoff (suggested: 1s → 2s → 5s → 10s, capped at
  10s). Once the buffer hits its ceiling, drop oldest. Never write
  unsent lines to a sidecar file — that's what the existing on-disk
  `lab_devices_client.log` rotation is for.
- **Ordering and dedup:** server makes no guarantees. The client should
  push in arrival order but the server may interleave or accept duplicates
  if a retry succeeds after the original push partially landed.

### 5. Identity

The client is trusted to set the `client` label correctly to its own chisel
auth username. Mislabeling produces wrong attribution in Grafana panels (an
integrity issue), not data leakage to other tenants (there are no tenants).
A future per-client auth proxy could harden this without changing the client
contract; the present design intentionally takes the cheaper path.

### 6. Backward compatibility

- The on-disk rotated log files (`lab_devices_client.log`,
  `lab_devices_client_stderr.log`) remain the durable record. **Continue to
  write them as before.** Loki ingest is in addition to, not in replacement
  of, the existing files.
- The forward tunnel is purely additive. A client running an older binary
  that doesn't open it will still pass chisel auth and continue to function
  for device-port forwarding; the server will just see no logs.

## Suggested implementation shape

(Adapt to whatever language and concurrency model the client uses — these
are illustrative.)

- A **log shipper** owned by the same supervisor that owns the chisel
  subprocess. Reads from two queues (one per stream), batches by time and
  count, POSTs.
- A **buffer** (deque or ring buffer) with a strict line cap. Drop oldest
  on overflow.
- An **HTTP client** that uses `Connection: keep-alive` to avoid re-handshaking
  per batch. Set a short timeout (≤5 s) — failed pushes go back into the
  retry loop, never block.
- A **gzip wrapper** around the JSON body (set `Content-Encoding: gzip`).
  Loki accepts both compressed and uncompressed; gzip cuts traffic by ~70%
  for line-oriented logs.
- Surface the **`logs_dropped_total`** counter in whatever metric/log
  surface the client already exposes, so the operator can see when the
  buffer is overflowing.

## Verification

In order, on a development VPS:

1. **Tunnel comes up.** Start the client. The chisel session log should
   show two routes (the existing reverse + the new `127.0.0.1:3100`
   forward). On the lab machine, `curl -i http://127.0.0.1:3100/ready`
   should return `HTTP/1.1 200 OK`.

2. **Push lands in Loki.** Tail one of the local log files and confirm the
   same lines appear within a few seconds at
   `https://<vps-host>/grafana/` → "Lab client logs" → Live tail panel
   (filtered to your `client` label).

3. **Disconnect tolerance.** Block outbound TCP to the chisel port for 30 s
   (e.g. `iptables`/firewall rule on the lab machine). Lines written
   during that window should buffer and flush within seconds of restoring
   the connection. The on-disk log files must show every line whether or
   not the network was up.

4. **Buffer overflow surfaces.** Force a longer outage that exceeds the
   10k-line buffer. Confirm that:
   - the client does not OOM,
   - device control is unaffected,
   - the dropped-lines counter increments and reaches Loki on the next
     successful push.

5. **Cardinality guard.** Try (in a debug build) emitting a stream with a
   spurious extra label. The Loki side returns HTTP 400 — confirm the
   client logs the rejection at WARN, drops the offending batch (rather
   than hot-looping), and continues.

## Failure modes (client side)

| Failure | Effect | Required behavior |
|---|---|---|
| Chisel session down | Forward tunnel dead, pushes fail | Buffer; backoff; do not block writer; never lose on-disk record |
| Loki 5xx (overload) | Push rejected with retry-able error | Backoff and retry the same batch |
| Loki 4xx (bad request, e.g. cardinality) | Push rejected permanently | Log at WARN, drop the batch, do not retry |
| Lab-machine clock skew >7 days | Loki rejects with `reject_old_samples` | Log at WARN once per session; let later batches recover when the clock corrects |
| Buffer overflow | New lines drop oldest | Increment counter; surface in next successful push |
| `client` label mismatched to chisel auth | Wrong panel attribution | Out of scope; documented as an integrity issue |

## Open questions for the client team

These don't affect the contract but matter for the implementation:

- Where in the existing client supervisor does the log shipper live? Same
  process, sidecar thread, or separate child? (Recommendation: same
  process, separate worker thread, so it inherits the existing crash and
  restart semantics.)
- Should the dropped-lines counter also be written to the on-disk log?
  (Recommendation: yes, at WARN, every time the counter increments — that
  way the operator can see overflows even if Loki is also down.)
- Does the client already have a usable HTTP client / gzip / async-queue
  primitive, or do those need to be added as dependencies?
