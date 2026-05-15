"""Bring flasher + stub-serialhop up via docker compose for the test session."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import httpx
import pytest

HERE = Path(__file__).parent
COMPOSE_FILE = HERE / "compose.yaml"


def wait_for_terminal(
    http: httpx.Client, job_id: str, *, max_iterations: int = 30, sleep_s: float = 0.5
) -> dict:
    """Poll /flash/api/flash/<job_id> until status is terminal ('done' or 'error').

    Returns the final job-record body. Raises AssertionError with the latest
    body if the loop exhausts without reaching terminal state.
    """
    body: dict = {}
    for _ in range(max_iterations):
        time.sleep(sleep_s)
        r = http.get(f"/flash/api/flash/{job_id}")
        assert r.status_code == 200, f"polling /flash/api/flash/{job_id} returned {r.status_code}"
        body = r.json()
        if body.get("status") in {"done", "error"}:
            return body
    raise AssertionError(
        f"flash job {job_id} did not reach terminal status within "
        f"{max_iterations * sleep_s:.1f}s; last body: {body!r}"
    )


def _compose(
    *args: str, env: dict | None = None, check: bool = True
) -> subprocess.CompletedProcess:
    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)
    return subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), *args],
        check=check,
        cwd=str(HERE),
        env=proc_env,
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="session")
def flasher_url() -> str:
    _compose("up", "-d", "--build", "--wait")
    try:
        yield "http://127.0.0.1:8002"
    finally:
        _compose("down", "-v", check=False)


@pytest.fixture(scope="session")
def http(flasher_url: str) -> httpx.Client:
    with httpx.Client(base_url=flasher_url, timeout=10.0) as client:
        yield client


@pytest.fixture
def set_stub_outcome():
    """Restart stub-serialhop with a different STUB_FLASH_OUTCOME.

    Restores stub to the default 'success' outcome after the test so subsequent
    tests in the session see the expected default behavior.

    Usage:
        def test_x(http, set_stub_outcome):
            set_stub_outcome("rolled_back_test_failed")
            ...
    """

    def _set(outcome: str) -> None:
        _compose("stop", "stub-serialhop", check=False)
        _compose("rm", "-f", "stub-serialhop", check=False)
        _compose("up", "-d", "--wait", "stub-serialhop", env={"STUB_FLASH_OUTCOME": outcome})

    yield _set

    # Teardown: restore stub to 'success' outcome for subsequent tests.
    _compose("stop", "stub-serialhop", check=False)
    _compose("rm", "-f", "stub-serialhop", check=False)
    _compose("up", "-d", "--wait", "stub-serialhop", env={"STUB_FLASH_OUTCOME": "success"})
