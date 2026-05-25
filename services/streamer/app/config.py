from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration; populated from environment variables."""

    model_config = SettingsConfigDict(env_prefix="STREAMER_", env_file=None)

    clients_file: Path = Path("/etc/streamer/clients.json")
    chisel_host: str = "chisel"

    public_ip: str = "127.0.0.1"
    udp_port_range: str = "50000-50100"

    publish_ready_timeout_s: float = 10.0
    drain_debounce_s: float = 5.0
    discovery_cache_ttl_s: float = 10.0
    discovery_request_timeout_s: float = 1.0
    whip_token_validity_s: float = 60.0
    max_subscribers_per_session: int = 3

    lab_bridge_version: str = Field(default="dev", alias="LAB_BRIDGE_VERSION")
    lab_bridge_git_sha: str = Field(default="unknown", alias="LAB_BRIDGE_GIT_SHA")


def load_settings() -> Settings:
    return Settings()
