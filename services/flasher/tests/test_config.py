from __future__ import annotations

from pathlib import Path

import pytest

from app.config import load_settings


def test_load_settings_requires_data_dir(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("FLASHER_DATA_DIR", raising=False)
    with pytest.raises(RuntimeError, match="FLASHER_DATA_DIR"):
        load_settings()


def test_load_settings_creates_data_dir_and_blob_subdirs(monkeypatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "flasher_data"
    monkeypatch.setenv("FLASHER_DATA_DIR", str(data_dir))
    monkeypatch.delenv("FLASHER_UPLOAD_TOKEN", raising=False)
    monkeypatch.delenv("FLASHER_UPLOAD_TOKEN__FILE", raising=False)

    s = load_settings()

    assert s.data_dir == data_dir.resolve()
    assert (data_dir / "blobs" / "firmware").is_dir()
    assert (data_dir / "blobs" / "backups").is_dir()


def test_load_settings_synthesises_token_when_neither_env_set(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FLASHER_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("FLASHER_UPLOAD_TOKEN", raising=False)
    monkeypatch.delenv("FLASHER_UPLOAD_TOKEN__FILE", raising=False)

    s = load_settings()

    assert isinstance(s.upload_token, str)
    assert len(s.upload_token) >= 32


def test_load_settings_reads_token_from_file_when_present(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FLASHER_DATA_DIR", str(tmp_path))
    tok_file = tmp_path / "token"
    tok_file.write_text("from-file-token\n", encoding="utf-8")
    monkeypatch.setenv("FLASHER_UPLOAD_TOKEN__FILE", str(tok_file))
    monkeypatch.setenv("FLASHER_UPLOAD_TOKEN", "inline-token")  # __FILE wins

    s = load_settings()

    assert s.upload_token == "from-file-token"


def test_load_settings_reads_token_from_env_when_no_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FLASHER_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("FLASHER_UPLOAD_TOKEN__FILE", raising=False)
    monkeypatch.setenv("FLASHER_UPLOAD_TOKEN", "inline-token")

    s = load_settings()

    assert s.upload_token == "inline-token"
