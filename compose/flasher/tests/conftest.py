from __future__ import annotations

import os
from pathlib import Path

import pytest


def pytest_configure(config) -> None:  # noqa: ARG001
    """Set sentinel env vars so app.main can be imported during collection.

    The autouse fixtures below override these with tmp_path values per-test.
    """
    os.environ.setdefault("FLASHER_CLIENTS_FILE", "/tmp/clients_test_sentinel.json")
    os.environ.setdefault("FLASHER_CHISEL_HOST", "chisel")


@pytest.fixture(autouse=True)
def _clients_file_default(tmp_path: Path, monkeypatch) -> Path:
    """Set FLASHER_CLIENTS_FILE to a fresh empty roster for every test.

    Tests that *intentionally* assert the env var is absent must call
    monkeypatch.delenv("FLASHER_CLIENTS_FILE", raising=False) themselves.
    """
    p = tmp_path / "clients.json"
    p.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("FLASHER_CLIENTS_FILE", str(p))
    return p


@pytest.fixture(autouse=True)
def _chisel_host_default(monkeypatch) -> str:
    monkeypatch.setenv("FLASHER_CHISEL_HOST", "chisel")
    return "chisel"


@pytest.fixture
def clients_file(_clients_file_default: Path) -> Path:
    """Re-export of the autouse fixture for tests that want to write to it."""
    return _clients_file_default
