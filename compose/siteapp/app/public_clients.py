from __future__ import annotations

import hashlib
import json
import secrets as secrets_mod
import socket
from pathlib import Path

DUMMY_HASH = b"\x00" * 32  # used for constant-time miss-branch compare
CHISEL_HOST = "chisel"
TCP_PROBE_TIMEOUT = 0.3  # seconds; per-request, sub-millisecond on a healthy labnet


def _parse_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        return ""
    return authorization.split(None, 1)[1].strip()


def _load_roster(path: Path) -> dict[str, dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("clients.json must be a JSON object")
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


from fastapi import APIRouter, Header, HTTPException, Path as PathParam

from app.config import Settings


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

    return router
