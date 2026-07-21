"""Admin-only proxy to a lab agent's remote-update endpoints.

Resolves a lab name to its chisel port (reusing the siteapp roster) and
forwards POST /agent/update and GET /agent/update/status to
http://chisel:<port>. The agent's status code and body are returned
verbatim, with two deliberate deviations documented in
docs/superpowers/specs/2026-07-21-remote-admin-update-server-design.md §6:

  * an agent 404 (feature disabled) is re-worded to a clear message, and
  * an unreachable agent (tunnel down, incl. the expected post-install
    restart) becomes a retryable 503 rather than an error.

The gate itself is at the edge (Authelia rule + Caddy forward_auth), matching
every other admin surface in this repo; there is no app-layer group check.
"""

from __future__ import annotations

import json

import httpx
from fastapi import APIRouter, Path as PathParam, Request, Response

from app.clients import load_roster
from app.config import Settings

CHISEL_HOST = "chisel"
UPDATE_POST_TIMEOUT_S = 30.0  # agent may do a synchronous GitHub lookup before 202/502
STATUS_TIMEOUT_S = 5.0  # local read on the agent

AGENT_UPDATE_PATH = "/agent/update"
AGENT_UPDATE_STATUS_PATH = "/agent/update/status"


def _json(payload: dict, status_code: int) -> Response:
    return Response(
        content=json.dumps(payload).encode("utf-8"),
        status_code=status_code,
        media_type="application/json",
    )


def _resolve_port(settings: Settings, name: str) -> int | None:
    """Return the lab's chisel port, or None if the name is unknown.

    Lets load_roster's OSError/ValueError propagate (→ 500) — a broken roster
    is a server fault, distinct from an unknown lab name.
    """
    roster = load_roster(settings.clients_file)
    entry = roster.get(name)
    return int(entry["port"]) if entry is not None else None


async def _forward(
    method: str,
    port: int,
    agent_path: str,
    *,
    body: bytes | None,
    timeout_s: float,
    host: str,
) -> Response:
    url = f"http://{host}:{port}{agent_path}"
    headers = {"content-type": "application/json"} if body is not None else None
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method, url, content=body, headers=headers, timeout=timeout_s
            )
    except (httpx.HTTPError, OSError) as exc:
        # Tunnel down / agent restarting mid-install — expected, retryable.
        return _json(
            {"error": "agent unreachable", "detail": str(exc) or type(exc).__name__},
            status_code=503,
        )

    if resp.status_code == 404:
        # We reached the agent and it returned 404 → remote update is disabled
        # on that PC. The raw {"error":"not found"} is ambiguous; clarify it.
        try:
            upstream = resp.json()
        except ValueError:
            upstream = {"body": resp.text[:200]}
        return _json(
            {
                "error": "remote update disabled",
                "detail": "Remote update is turned off on this agent.",
                "upstream": upstream,
            },
            status_code=404,
        )

    # Verbatim passthrough of everything else (202/200/400/409/502/...).
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type", "application/json"),
    )


def make_router(settings: Settings, *, host: str = CHISEL_HOST) -> APIRouter:
    router = APIRouter()

    @router.post("/api/admin/labs/{name}/update")
    async def trigger_update(
        request: Request,
        name: str = PathParam(..., min_length=1, max_length=128),
    ) -> Response:
        port = _resolve_port(settings, name)
        if port is None:
            return _json({"error": "unknown lab", "detail": name}, status_code=404)
        # Empty body → {} → "latest release" per the agent contract.
        body = await request.body() or b"{}"
        return await _forward(
            "POST",
            port,
            AGENT_UPDATE_PATH,
            body=body,
            timeout_s=UPDATE_POST_TIMEOUT_S,
            host=host,
        )

    @router.get("/api/admin/labs/{name}/update/status")
    async def update_status(
        name: str = PathParam(..., min_length=1, max_length=128),
    ) -> Response:
        port = _resolve_port(settings, name)
        if port is None:
            return _json({"error": "unknown lab", "detail": name}, status_code=404)
        return await _forward(
            "GET",
            port,
            AGENT_UPDATE_STATUS_PATH,
            body=None,
            timeout_s=STATUS_TIMEOUT_S,
            host=host,
        )

    return router
