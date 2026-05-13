from __future__ import annotations

from pathlib import Path

import pytest

from app.config import load_settings


def test_loads_defaults(_clients_file_default: Path) -> None:
    settings = load_settings()
    assert settings.clients_file == _clients_file_default
    assert settings.chisel_host == "chisel"


def test_clients_file_env_required(monkeypatch) -> None:
    monkeypatch.delenv("FLASHER_CLIENTS_FILE", raising=False)
    with pytest.raises(RuntimeError, match="FLASHER_CLIENTS_FILE"):
        load_settings()


def test_chisel_host_falls_back_to_default(monkeypatch, _clients_file_default: Path) -> None:
    monkeypatch.delenv("FLASHER_CHISEL_HOST", raising=False)
    settings = load_settings()
    assert settings.chisel_host == "chisel"
