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
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("clients.json must be a JSON object")
    out: dict[str, dict[str, object]] = {}
    for name, port in raw.items():
        if not isinstance(name, str):
            raise ValueError(f"roster key must be string, got: {name!r}")
        # bool is a subclass of int in Python; exclude it explicitly.
        if isinstance(port, bool) or not isinstance(port, int):
            raise ValueError(f"roster value must be int, got: {name}={port!r}")
        out[name] = {"host": CHISEL_HOST, "port": port}
    return out
