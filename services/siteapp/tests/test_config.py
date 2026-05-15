from __future__ import annotations

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
    assert (s.site_data / "agent" / "windows").is_dir()
    assert isinstance(s, Settings)


def test_clients_file_required(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "tok")
    monkeypatch.delenv("SITEAPP_CLIENTS_FILE", raising=False)
    with pytest.raises(RuntimeError, match="SITEAPP_CLIENTS_FILE"):
        load_settings()


def test_clients_file_path_stored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "tok")
    monkeypatch.setenv("SITEAPP_CLIENTS_FILE", "/etc/siteapp/clients.json")
    settings = load_settings()
    assert settings.clients_file == Path("/etc/siteapp/clients.json")


def test_chisel_listen_port_required(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "tok")
    monkeypatch.delenv("SITEAPP_CHISEL_LISTEN_PORT", raising=False)
    with pytest.raises(RuntimeError, match="SITEAPP_CHISEL_LISTEN_PORT"):
        load_settings()


def test_chisel_listen_port_stored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "tok")
    monkeypatch.setenv("SITEAPP_CHISEL_LISTEN_PORT", "9090")
    settings = load_settings()
    assert settings.chisel_listen_port == 9090


def test_chisel_listen_port_non_integer_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "tok")
    monkeypatch.setenv("SITEAPP_CHISEL_LISTEN_PORT", "not-a-number")
    with pytest.raises(ValueError):
        load_settings()


def test_docs_dir_required(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "tok")
    monkeypatch.delenv("SITEAPP_DOCS_DIR", raising=False)
    with pytest.raises(RuntimeError, match="SITEAPP_DOCS_DIR"):
        load_settings()


def test_docs_dir_stored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    docs = tmp_path / "srv-docs"
    docs.mkdir()
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "tok")
    monkeypatch.setenv("SITEAPP_DOCS_DIR", str(docs))
    settings = load_settings()
    assert settings.docs_root == docs


def test_docs_dir_must_exist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "tok")
    monkeypatch.setenv("SITEAPP_DOCS_DIR", str(tmp_path / "does-not-exist"))
    with pytest.raises(RuntimeError, match="SITEAPP_DOCS_DIR"):
        load_settings()
