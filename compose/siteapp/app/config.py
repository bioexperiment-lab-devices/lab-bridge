from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    site_data: Path
    agent_upload_token: str
    max_upload_mb_doc: int = 10
    max_upload_mb_agent: int = 100
    csrf_secret: str = ""

    @property
    def docs_root(self) -> Path:
        return self.site_data / "docs"

    @property
    def agent_root(self) -> Path:
        return self.site_data / "agent"


def load_settings() -> Settings:
    data = os.environ.get("SITE_DATA")
    if not data:
        raise RuntimeError("SITE_DATA env var is required")
    site_data = Path(data).resolve()
    (site_data / "docs").mkdir(parents=True, exist_ok=True)
    (site_data / "agent" / "windows").mkdir(parents=True, exist_ok=True)
    (site_data / "agent" / ".tmp").mkdir(parents=True, exist_ok=True)

    token_file = os.environ.get("SITEAPP_AGENT_UPLOAD_TOKEN__FILE")
    if token_file:
        token = Path(token_file).read_text(encoding="utf-8").strip()
    else:
        token = os.environ.get("SITEAPP_AGENT_UPLOAD_TOKEN", "").strip()
    if not token:
        # Local-dev convenience: synthesize a per-process token so the app boots.
        token = secrets.token_urlsafe(32)

    csrf = os.environ.get("SITEAPP_CSRF_SECRET", secrets.token_urlsafe(32))

    return Settings(
        site_data=site_data,
        agent_upload_token=token,
        csrf_secret=csrf,
    )
