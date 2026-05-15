from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    clients_file: Path
    chisel_host: str
    version: str = "dev"
    git_sha: str = "unknown"


def load_settings() -> Settings:
    clients_env = os.environ.get("FLASHER_CLIENTS_FILE")
    if not clients_env:
        raise RuntimeError("FLASHER_CLIENTS_FILE env var is required")
    # Not .resolve()'d — this is a reference to an externally-mounted file,
    # not a data root we own. Routes re-read it on each request.
    clients_file = Path(clients_env)

    chisel_host = os.environ.get("FLASHER_CHISEL_HOST", "chisel").strip() or "chisel"

    version = os.environ.get("LAB_BRIDGE_VERSION", "dev").strip() or "dev"
    git_sha = os.environ.get("LAB_BRIDGE_GIT_SHA", "unknown").strip() or "unknown"

    return Settings(
        clients_file=clients_file,
        chisel_host=chisel_host,
        version=version,
        git_sha=git_sha,
    )
