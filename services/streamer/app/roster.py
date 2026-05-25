"""Parse the rendered clients.json roster into a name → port map."""

from __future__ import annotations

import json
from pathlib import Path


def load_roster(path: Path) -> dict[str, int]:
    """Read clients.json and return {name: port}.

    Raises OSError on missing/unreadable file. Raises ValueError on
    malformed JSON or per-entry shape problems. Mirrors
    ``services/siteapp/app/clients.py:load_roster`` validation rules.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("clients.json must be a JSON object")
    out: dict[str, int] = {}
    for name, entry in raw.items():
        if not isinstance(entry, dict):
            raise ValueError(f"roster value must be object, got: {name}={entry!r}")
        port = entry.get("port")
        # bool is a subclass of int — reject explicitly.
        if isinstance(port, bool) or not isinstance(port, int):
            raise ValueError(f"roster port must be int, got: {name}.port={port!r}")
        out[name] = port
    return out
