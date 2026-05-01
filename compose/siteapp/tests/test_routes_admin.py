from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "x")
    monkeypatch.setenv("SITEAPP_CSRF_SECRET", "test-csrf-secret")
    from importlib import reload

    import app.main

    reload(app.main)
    return TestClient(app.main.app)


def _csrf(client: TestClient) -> str:
    r = client.get("/admin/docs")
    import re

    m = re.search(r'name="csrf"\s+value="([^"]+)"', r.text)
    assert m, "csrf token not found in admin/docs"
    return m.group(1)


def test_dashboard_renders(client: TestClient) -> None:
    r = client.get("/admin/")
    assert r.status_code == 200
    assert "Documentation" in r.text and "Agent" in r.text


def test_docs_listing_empty(client: TestClient) -> None:
    r = client.get("/admin/docs")
    assert r.status_code == 200
    assert "Drop files here" in r.text


def test_upload_md(client: TestClient, tmp_path: Path) -> None:
    csrf = _csrf(client)
    r = client.post(
        "/admin/docs/upload",
        data={"csrf": csrf, "target": ""},
        files={"files": ("Hello.MD", b"# Hi\n", "text/markdown")},
    )
    assert r.status_code in (200, 303)
    assert (tmp_path / "docs" / "hello.md").is_file()


def test_upload_rejects_bad_extension(client: TestClient, tmp_path: Path) -> None:
    csrf = _csrf(client)
    r = client.post(
        "/admin/docs/upload",
        data={"csrf": csrf, "target": ""},
        files={"files": ("evil.exe", b"\x4d\x5a", "application/octet-stream")},
    )
    assert r.status_code == 400
    assert not any((tmp_path / "docs").iterdir())


def test_upload_rejects_traversal(client: TestClient, tmp_path: Path) -> None:
    csrf = _csrf(client)
    r = client.post(
        "/admin/docs/upload",
        data={"csrf": csrf, "target": "../escape"},
        files={"files": ("ok.md", b"# Ok\n", "text/markdown")},
    )
    assert r.status_code == 400


def test_upload_without_csrf(client: TestClient) -> None:
    r = client.post(
        "/admin/docs/upload",
        data={"target": ""},
        files={"files": ("ok.md", b"# Ok\n", "text/markdown")},
    )
    assert r.status_code == 403


def test_delete(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "docs" / "doomed.md").write_text("# Doomed\n", encoding="utf-8")
    csrf = _csrf(client)
    r = client.post(
        "/admin/docs/delete",
        data={"csrf": csrf, "target": "", "name": "doomed.md"},
    )
    assert r.status_code in (200, 303)
    assert not (tmp_path / "docs" / "doomed.md").exists()


def test_rename(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "docs" / "old.md").write_text("# Old\n", encoding="utf-8")
    csrf = _csrf(client)
    r = client.post(
        "/admin/docs/rename",
        data={"csrf": csrf, "target": "", "old": "old.md", "new": "shiny.md"},
    )
    assert r.status_code in (200, 303)
    assert (tmp_path / "docs" / "shiny.md").is_file()
    assert not (tmp_path / "docs" / "old.md").exists()


def test_new_folder(client: TestClient, tmp_path: Path) -> None:
    csrf = _csrf(client)
    r = client.post(
        "/admin/docs/new-folder",
        data={"csrf": csrf, "target": "", "name": "Section-One"},
    )
    assert r.status_code in (200, 303)
    assert (tmp_path / "docs" / "section-one").is_dir()
