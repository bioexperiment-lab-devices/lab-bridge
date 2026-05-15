from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def site_data(tmp_path: Path) -> Path:
    """Fresh, empty site_data/ tree for a single test."""
    (tmp_path / "agent" / "windows").mkdir(parents=True)
    return tmp_path


@pytest.fixture(autouse=True)
def _docs_dir_default(tmp_path: Path, monkeypatch) -> Path:
    """Set SITEAPP_DOCS_DIR to a fresh empty docs root for every test.

    Tests that need actual doc content can write into the returned path
    or override the env var explicitly. Tests asserting the env var is
    *absent* (e.g. test_docs_dir_required) must call
    ``monkeypatch.delenv("SITEAPP_DOCS_DIR", raising=False)`` themselves.
    """
    p = tmp_path / "docs-root"
    p.mkdir()
    monkeypatch.setenv("SITEAPP_DOCS_DIR", str(p))
    return p


@pytest.fixture(autouse=True)
def _clients_file_default(tmp_path: Path, monkeypatch) -> Path:
    """Set SITEAPP_CLIENTS_FILE to a fresh empty roster for every test."""
    p = tmp_path / "clients.json"
    p.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("SITEAPP_CLIENTS_FILE", str(p))
    return p


@pytest.fixture(autouse=True)
def _chisel_listen_port_default(monkeypatch) -> int:
    """Set SITEAPP_CHISEL_LISTEN_PORT to a fixed test value."""
    monkeypatch.setenv("SITEAPP_CHISEL_LISTEN_PORT", "8080")
    return 8080
