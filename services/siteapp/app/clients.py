from __future__ import annotations

import json
from pathlib import Path

CHISEL_HOST = "chisel"  # docker compose service name on labnet


def load_roster(path: Path) -> dict[str, dict[str, object]]:
    """Read and reshape the rendered roster file.

    Returns the response-ready map: {name: {"host": ..., "port": int}}.
    Raises OSError on missing/unreadable file, ValueError on malformed
    JSON or wrong shape. The route layer lets these propagate so
    FastAPI returns a 500 and uvicorn logs the traceback.

    Entry shape on disk is {"port": int, "password_sha256": str};
    the hash is used by the public-clients endpoint and ignored here.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("clients.json must be a JSON object")
    out: dict[str, dict[str, object]] = {}
    for name, entry in raw.items():
        if not isinstance(name, str):
            raise ValueError(f"roster key must be string, got: {name!r}")
        if not isinstance(entry, dict):
            raise ValueError(f"roster value must be object, got: {name}={entry!r}")
        port = entry.get("port")
        if isinstance(port, bool) or not isinstance(port, int):
            raise ValueError(f"roster port must be int, got: {name}.port={port!r}")
        out[name] = {"host": CHISEL_HOST, "port": port}
    return out
