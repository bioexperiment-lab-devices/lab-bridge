from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    site_data: Path
    agent_upload_token: str
    clients_file: Path
    chisel_listen_port: int
    docs_root: Path
    version: str = "dev"
    git_sha: str = "unknown"

    @property
    def agent_root(self) -> Path:
        return self.site_data / "agent"


def load_settings() -> Settings:
    data = os.environ.get("SITE_DATA")
    if not data:
        raise RuntimeError("SITE_DATA env var is required")
    site_data = Path(data).resolve()
    (site_data / "agent" / "windows").mkdir(parents=True, exist_ok=True)
    (site_data / "agent" / ".tmp").mkdir(parents=True, exist_ok=True)

    docs_env = os.environ.get("SITEAPP_DOCS_DIR")
    if not docs_env:
        raise RuntimeError("SITEAPP_DOCS_DIR env var is required")
    # Not .resolve()'d — this is a reference to an externally-mounted
    # directory, not a data root we own. Symlinks inside are still
    # rejected at request time by safe_join in docs.py.
    docs_root = Path(docs_env)
    if not docs_root.is_dir():
        raise RuntimeError(
            f"SITEAPP_DOCS_DIR must point to an existing directory; got: {docs_root}"
        )

    clients_env = os.environ.get("SITEAPP_CLIENTS_FILE")
    if not clients_env:
        raise RuntimeError("SITEAPP_CLIENTS_FILE env var is required")
    # Not .resolve()'d — this is a reference to an externally-mounted file,
    # not a data root we own. The route reads it on each request.
    clients_file = Path(clients_env)

    port_env = os.environ.get("SITEAPP_CHISEL_LISTEN_PORT")
    if not port_env:
        raise RuntimeError("SITEAPP_CHISEL_LISTEN_PORT env var is required")
    # int() raises ValueError on garbage like "abc"; surface as a boot crash —
    # a misrendered template should never produce a "port 0" runtime fallback.
    chisel_listen_port = int(port_env)

    token_file = os.environ.get("SITEAPP_AGENT_UPLOAD_TOKEN__FILE")
    if token_file:
        token = Path(token_file).read_text(encoding="utf-8").strip()
    else:
        token = os.environ.get("SITEAPP_AGENT_UPLOAD_TOKEN", "").strip()
    if not token:
        # Local-dev convenience: synthesize a per-process token so the app boots.
        token = secrets.token_urlsafe(32)

    version = os.environ.get("LAB_BRIDGE_VERSION", "dev").strip() or "dev"
    git_sha = os.environ.get("LAB_BRIDGE_GIT_SHA", "unknown").strip() or "unknown"

    return Settings(
        site_data=site_data,
        agent_upload_token=token,
        clients_file=clients_file,
        chisel_listen_port=chisel_listen_port,
        docs_root=docs_root,
        version=version,
        git_sha=git_sha,
    )
