from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "test-token")
    from importlib import reload

    import app.main

    reload(app.main)
    return TestClient(app.main.app)


def _publish_binary(tmp_path: Path, content: bytes = b"PE-binary-bytes") -> None:
    agent = tmp_path / "agent"
    (agent / "windows" / "agent.exe").write_bytes(content)
    meta = {
        "version": "1.2.3",
        "sha256": "abc",
        "uploaded_at": "2026-05-01T00:00:00Z",
        "size": len(content),
    }
    (agent / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def test_page_when_no_binary(client: TestClient) -> None:
    r = client.get("/download/agent")
    assert r.status_code == 200
    assert "Not yet available" in r.text


def test_page_renders_when_binary_present(tmp_path: Path, client: TestClient) -> None:
    _publish_binary(tmp_path)
    r = client.get("/download/agent")
    assert r.status_code == 200
    assert "1.2.3" in r.text
    assert "Download for Windows" in r.text


def test_binary_streams(tmp_path: Path, client: TestClient) -> None:
    _publish_binary(tmp_path, b"hello-binary")
    r = client.get("/download/agent/windows/agent.exe")
    assert r.status_code == 200
    assert r.content == b"hello-binary"
    assert r.headers["content-type"] == "application/octet-stream"
    assert "SerialHop-v1.2.3.exe" in r.headers["content-disposition"]
    assert r.headers["cache-control"] == "no-store"


def test_binary_404_when_missing(client: TestClient) -> None:
    assert client.get("/download/agent/windows/agent.exe").status_code == 404


def test_page_renders_body_markdown(tmp_path: Path, client: TestClient) -> None:
    _publish_binary(tmp_path)
    (tmp_path / "agent" / "page.md").write_text(
        "## What is this?\n\nA Windows lab agent.\n", encoding="utf-8"
    )
    r = client.get("/download/agent")
    assert "What is this?" in r.text
    assert "A Windows lab agent" in r.text


from datetime import UTC, datetime, timedelta

from app.agent import _relative_time


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def test_relative_time_just_now_en():
    now = datetime.now(UTC)
    assert _relative_time(_iso(now - timedelta(seconds=10)), "en") == "just now"


def test_relative_time_minutes_en():
    now = datetime.now(UTC)
    assert _relative_time(_iso(now - timedelta(minutes=5)), "en") == "5 minutes ago"


def test_relative_time_hours_en():
    now = datetime.now(UTC)
    assert _relative_time(_iso(now - timedelta(hours=3)), "en") == "3 hours ago"


def test_relative_time_days_en():
    now = datetime.now(UTC)
    assert _relative_time(_iso(now - timedelta(days=6)), "en") == "6 days ago"


def test_relative_time_weeks_en():
    now = datetime.now(UTC)
    assert _relative_time(_iso(now - timedelta(days=21)), "en") == "3 weeks ago"


def test_relative_time_days_ru():
    now = datetime.now(UTC)
    assert _relative_time(_iso(now - timedelta(days=6)), "ru") == "6 дн назад"


def test_relative_time_garbage_returns_empty():
    assert _relative_time("not-a-date", "en") == ""
