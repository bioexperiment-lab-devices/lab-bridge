from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


def _isolate_main(monkeypatch, docs_root: Path, tmp_path: Path) -> None:
    """Drop cached app.main + app.config so re-import picks up the new docs_root."""
    site_data = tmp_path / "site_data"
    (site_data / "agent" / "windows").mkdir(parents=True, exist_ok=True)
    (site_data / "agent" / ".tmp").mkdir(parents=True, exist_ok=True)
    clients_file = tmp_path / "clients.json"
    clients_file.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("SITE_DATA", str(site_data))
    monkeypatch.setenv("SITEAPP_DOCS_DIR", str(docs_root))
    monkeypatch.setenv("SITEAPP_CLIENTS_FILE", str(clients_file))
    monkeypatch.setenv("SITEAPP_CHISEL_LISTEN_PORT", "8080")
    sys.modules.pop("app.main", None)
    sys.modules.pop("app.config", None)


def test_startup_succeeds_with_valid_docs(tmp_path: Path, monkeypatch) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Home\n", encoding="utf-8")
    _isolate_main(monkeypatch, docs, tmp_path)
    # Importing app.main must not raise. It will call build_nav at import time.
    importlib.import_module("app.main")


def test_startup_fails_on_malformed_manifest(tmp_path: Path, monkeypatch) -> None:
    from app.docs_manifest import DocsNavError

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "intro.md").write_text("# Intro\n", encoding="utf-8")
    (docs / "extra.md").write_text("# Extra\n", encoding="utf-8")
    (docs / "_nav.yaml").write_text("- name: intro\n", encoding="utf-8")
    _isolate_main(monkeypatch, docs, tmp_path)
    with pytest.raises(DocsNavError):
        importlib.import_module("app.main")
