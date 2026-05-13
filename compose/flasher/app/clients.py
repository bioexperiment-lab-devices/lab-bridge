from __future__ import annotations

import json
import socket
from pathlib import Path

TCP_PROBE_TIMEOUT_S = 0.5


def load_roster(path: Path) -> dict[str, dict[str, int]]:
    """Parse the runtime clients.json file produced by render_siteapp_clients.

    On-disk shape: {name: {"port": int, "password_sha256": str}, ...}
    Returned shape: {name: {"port": int}, ...} — the hash is irrelevant here.

    Raises OSError if the file is missing, ValueError on malformed JSON or
    invalid per-entry shape.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("clients.json must be a JSON object")
    out: dict[str, dict[str, int]] = {}
    for name, entry in raw.items():
        if not isinstance(entry, dict):
            raise ValueError(f"roster value must be object, got: {name}={entry!r}")
        port = entry.get("port")
        # bool is a subclass of int; reject explicitly so a JSON `true`
        # doesn't silently coerce to port 1.
        if isinstance(port, bool) or not isinstance(port, int):
            raise ValueError(f"roster port must be int, got: {name}.port={port!r}")
        out[name] = {"port": port}
    return out


def probe_tcp(host: str, port: int, timeout_s: float = TCP_PROBE_TIMEOUT_S) -> bool:
    """Return True iff TCP dial to host:port completes within timeout.

    chisel-server tears down the reverse listener when its client
    disconnects, so a successful connect implies an active tunnel.
    """
    try:
        with socket.create_connection((host, port), timeout_s):
            return True
    except OSError:
        return False
