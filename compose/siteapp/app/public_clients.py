from __future__ import annotations

import hashlib
import json
import secrets as secrets_mod
from pathlib import Path

DUMMY_HASH = b"\x00" * 32  # used for constant-time miss-branch compare


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
        secrets_mod.compare_digest(DUMMY_HASH, bearer_hash)
        return None
    try:
        expected = bytes.fromhex(entry["password_sha256"])
    except (KeyError, TypeError, ValueError):
        secrets_mod.compare_digest(DUMMY_HASH, bearer_hash)
        return None
    if not secrets_mod.compare_digest(expected, bearer_hash):
        return None
    return entry
