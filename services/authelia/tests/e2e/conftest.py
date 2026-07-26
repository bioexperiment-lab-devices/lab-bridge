"""Session-scoped fixture: bring Authelia up via docker compose, tear it down."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import httpx
import pytest

HERE = Path(__file__).parent
COMPOSE_FILE = HERE / "compose.yaml"


def _compose(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), *args],
        check=check,
        cwd=str(HERE),
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="session")
def authelia_url() -> str:
    _compose("up", "-d", "--wait")
    try:
        yield "http://127.0.0.1:9091"
    finally:
        _compose("down", "-v", check=False)


@pytest.fixture(scope="session")
def http(authelia_url: str) -> httpx.Client:
    with httpx.Client(base_url=authelia_url, timeout=10.0) as client:
        yield client


@pytest.fixture
def restart_authelia(authelia_url: str):
    """Bounce the Authelia container the way `scripts/deploy.sh` does.

    Only the authelia service is restarted — redis keeps running, which is
    exactly the production deploy shape (deploy.sh restarts caddy, siteapp,
    chisel and authelia, never the session store).
    """

    def _restart() -> None:
        _compose("restart", "authelia")
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                if httpx.get(f"{authelia_url}/api/health", timeout=2.0).status_code == 200:
                    return
            except httpx.RequestError:
                pass
            time.sleep(0.5)
        raise RuntimeError("authelia did not become healthy again after restart")

    return _restart
