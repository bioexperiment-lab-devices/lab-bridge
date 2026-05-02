from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.config import Settings, load_settings


def test_load_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "abc123")
    monkeypatch.delenv("SITEAPP_AGENT_UPLOAD_TOKEN__FILE", raising=False)
    settings = load_settings()
    assert settings.site_data == tmp_path.resolve()
    assert settings.agent_upload_token == "abc123"


def test_token_from_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    token_file = tmp_path / "tok"
    token_file.write_text("file-token\n", encoding="utf-8")
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.delenv("SITEAPP_AGENT_UPLOAD_TOKEN", raising=False)
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN__FILE", str(token_file))
    settings = load_settings()
    assert settings.agent_upload_token == "file-token"


def test_missing_site_data_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SITE_DATA", raising=False)
    with pytest.raises(RuntimeError):
        load_settings()


def test_creates_subdirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "x")
    s = load_settings()
    assert (s.site_data / "docs").is_dir()
    assert (s.site_data / "agent" / "windows").is_dir()
    assert isinstance(s, Settings)


def test_seeds_default_index_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "x")
    s = load_settings()
    index = s.docs_root / "index.md"
    assert index.is_file()
    assert "Welcome to lab-bridge" in index.read_text(encoding="utf-8")


def test_does_not_overwrite_existing_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "index.md").write_text("# Custom\n", encoding="utf-8")
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "x")
    load_settings()
    assert (tmp_path / "docs" / "index.md").read_text(encoding="utf-8") == "# Custom\n"
