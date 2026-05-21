"""Session-scoped fixture: bring Authelia up via docker compose, tear it down."""

from __future__ import annotations

import subprocess
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
