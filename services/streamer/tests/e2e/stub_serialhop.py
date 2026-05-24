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

    # Replace-on-conflict: always accept the new session_id (idempotent for
    # same session_id, silently replaces on different session_id — no 409).
    sid = body["session_id"]
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
