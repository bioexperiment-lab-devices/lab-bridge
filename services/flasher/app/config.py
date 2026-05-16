from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    clients_file: Path
    chisel_host: str
    data_dir: Path
    upload_token: str
    version: str = "dev"
    git_sha: str = "unknown"


def _load_upload_token() -> str:
    tok_file = os.environ.get("FLASHER_UPLOAD_TOKEN__FILE")
    if tok_file:
        return Path(tok_file).read_text(encoding="utf-8").strip()
    inline = os.environ.get("FLASHER_UPLOAD_TOKEN", "").strip()
    if inline:
        return inline
    # Dev/test convenience: synthesize a per-process random token so the app boots
    # without configuration. Production deploys always set FLASHER_UPLOAD_TOKEN__FILE.
    return secrets.token_urlsafe(32)


def load_settings() -> Settings:
    clients_env = os.environ.get("FLASHER_CLIENTS_FILE")
    if not clients_env:
        raise RuntimeError("FLASHER_CLIENTS_FILE env var is required")
    clients_file = Path(clients_env)

    chisel_host = os.environ.get("FLASHER_CHISEL_HOST", "chisel").strip() or "chisel"

    data_env = os.environ.get("FLASHER_DATA_DIR")
    if not data_env:
        raise RuntimeError("FLASHER_DATA_DIR env var is required")
    data_dir = Path(data_env).resolve()
    (data_dir / "blobs" / "firmware").mkdir(parents=True, exist_ok=True)
    (data_dir / "blobs" / "backups").mkdir(parents=True, exist_ok=True)

    upload_token = _load_upload_token()

    version = os.environ.get("LAB_BRIDGE_VERSION", "dev").strip() or "dev"
    git_sha = os.environ.get("LAB_BRIDGE_GIT_SHA", "unknown").strip() or "unknown"

    return Settings(
        clients_file=clients_file,
        chisel_host=chisel_host,
        data_dir=data_dir,
        upload_token=upload_token,
        version=version,
        git_sha=git_sha,
    )
