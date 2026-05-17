"""Session-scoped fixture: bring caddy + stub up via docker compose, tear it down.

The image to run is selected via CADDY_TEST_IMAGE env var (default
``lab-bridge-caddy:e2e``). CI builds the image in the workflow's
image-build step and exports the tag; local runs should
``docker build -t lab-bridge-caddy:e2e services/caddy`` first.
"""
from __future__ import annotations

import subprocess
from collections.abc import Generator
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
def caddy_url() -> Generator[str, None, None]:
    _compose("up", "-d", "--wait")
    try:
        yield "http://127.0.0.1:18080"
    finally:
        _compose("down", "-v", check=False)


@pytest.fixture(scope="session")
def http(caddy_url: str) -> Generator[httpx.Client, None, None]:
    with httpx.Client(base_url=caddy_url, timeout=5.0) as client:
        yield client
