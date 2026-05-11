from __future__ import annotations

import hashlib
import httpx
import json
import secrets as secrets_mod
import socket
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Path as PathParam

from app.config import Settings

DUMMY_HASH = b"\x00" * 32  # used for constant-time miss-branch compare
CHISEL_HOST = "chisel"
CHISEL_HEALTH_URL = "http://chisel:7000/health"
HEALTH_PROBE_TIMEOUT = 1.0  # seconds
TCP_PROBE_TIMEOUT = 0.3  # seconds; per-request, sub-millisecond on a healthy labnet


def _parse_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        return ""
    return authorization.split(None, 1)[1].strip()


def _load_roster(path: Path) -> dict[str, dict]:
    """Read clients.json and validate the per-entry shape.

    Returns the raw dict (entries include port + password_sha256).
    Raises OSError on missing file; ValueError on malformed JSON or
    bad entry shape. Hash-string validation is intentionally deferred
    to _verify, which fails closed on a malformed or missing hash.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("clients.json must be a JSON object")
    for name, entry in raw.items():
        if not isinstance(entry, dict):
            raise ValueError(f"roster value must be object, got: {name}={entry!r}")
        port = entry.get("port")
        # bool is a subclass of int; reject it explicitly so a YAML
        # `true` doesn't silently coerce to port 1 downstream.
        if isinstance(port, bool) or not isinstance(port, int):
            raise ValueError(f"roster port must be int, got: {name}.port={port!r}")
    return raw


def _verify(username: str, bearer: str, roster: dict) -> dict | None:
    """Return the roster entry on success, None on any failure.

    Constant-time across hit/miss branches: both paths compute a single
    SHA-256 over the bearer and a single secrets.compare_digest, so the
    response time does not leak whether the username exists.
    """
    entry = roster.get(username)
    bearer_hash = hashlib.sha256(bearer.encode("utf-8")).digest()
    if entry is None:
        secrets_mod.compare_digest(DUMMY_HASH, bearer_hash)  # constant-time dummy; do not remove
        return None
    try:
        expected = bytes.fromhex(entry["password_sha256"])
    except (KeyError, TypeError, ValueError):
        secrets_mod.compare_digest(DUMMY_HASH, bearer_hash)  # constant-time dummy; do not remove
        return None
    if not secrets_mod.compare_digest(expected, bearer_hash):
        return None
    return entry


def _probe_tunnel(port: int) -> bool:
    """Return True iff TCP dial to chisel:<port> succeeded within timeout.

    chisel-server tears down the reverse listener when a client
    disconnects, so a successful connect implies an active session.
    """
    try:
        with socket.create_connection((CHISEL_HOST, port), TCP_PROBE_TIMEOUT):
            return True
    except OSError:
        return False


def make_router(settings: Settings) -> APIRouter:
    router = APIRouter()

    @router.get("/api/public/clients/{username}")
    def get_client(
        username: str = PathParam(..., min_length=1, max_length=128),
        authorization: str | None = Header(default=None),
    ) -> dict:
        bearer = _parse_bearer(authorization)
        roster = _load_roster(settings.clients_file)
        entry = _verify(username, bearer, roster)
        if entry is None:
            raise HTTPException(status_code=401, detail="unauthorized")
        port = int(entry["port"])
        return {"port": port, "connected": _probe_tunnel(port)}

    @router.get("/api/public/health")
    def get_health() -> dict:
        try:
            r = httpx.get(CHISEL_HEALTH_URL, timeout=HEALTH_PROBE_TIMEOUT)
            r.raise_for_status()
            return {"chisel": "ok"}
        except httpx.HTTPStatusError as e:
            return {"chisel": "down", "error": f"http {e.response.status_code}"}
        except httpx.TimeoutException:
            return {"chisel": "down", "error": "timeout"}
        except httpx.HTTPError as e:
            return {"chisel": "down", "error": type(e).__name__.lower()}

    return router
