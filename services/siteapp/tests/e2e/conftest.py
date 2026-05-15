"""Session-scoped fixture: bring siteapp up via docker compose, tear it down.

The image to run is selected via SITEAPP_TEST_IMAGE env var (default
``lab-bridge-siteapp:e2e``). CI builds the image in the workflow's
image-build step and exports the tag; local runs should
``docker build -t lab-bridge-siteapp:e2e services/siteapp`` first.
"""

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
def siteapp_url() -> str:
    _compose("up", "-d", "--wait")
    try:
        yield "http://127.0.0.1:8001"
    finally:
        _compose("down", "-v", check=False)


@pytest.fixture(scope="session")
def http(siteapp_url: str) -> httpx.Client:
    with httpx.Client(base_url=siteapp_url, timeout=5.0) as client:
        yield client
