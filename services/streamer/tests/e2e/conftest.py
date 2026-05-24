"""Session-scoped streamer + serialhop-stub fixture."""

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
def streamer_stack() -> dict[str, str]:
    _compose("up", "-d", "--build", "--wait")
    try:
        yield {
            "streamer": "http://127.0.0.1:8080",
            "stub": "http://127.0.0.1:8081",
        }
    finally:
        _compose("down", "-v", check=False)


@pytest.fixture
def http_streamer(streamer_stack: dict[str, str]) -> httpx.Client:
    with httpx.Client(
        base_url=streamer_stack["streamer"],
        timeout=10.0,
        headers={"Remote-User": "alice", "Remote-Groups": "researchers"},
    ) as client:
        yield client


@pytest.fixture
def http_stub(streamer_stack: dict[str, str]) -> httpx.Client:
    with httpx.Client(base_url=streamer_stack["stub"], timeout=10.0) as client:
        client.post("/__/reset")
        yield client
