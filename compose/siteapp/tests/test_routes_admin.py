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
    # Only the seeded default index.md should be present; no evil.exe written.
    names = {p.name for p in (tmp_path / "docs").iterdir()}
    assert "evil.exe" not in names
    assert names <= {"index.md"}


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


def test_target_with_unsafe_segment_rejected(client: TestClient) -> None:
    """target=<script> must 400, not silently create a polluted directory."""
    csrf = _csrf(client)
    r = client.post(
        "/admin/docs/upload",
        data={"csrf": csrf, "target": "<script>"},
        files={"files": ("ok.md", b"# Ok\n", "text/markdown")},
    )
    assert r.status_code == 400


def test_new_folder_existing_returns_409(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "docs" / "already").mkdir()
    csrf = _csrf(client)
    r = client.post(
        "/admin/docs/new-folder",
        data={"csrf": csrf, "target": "", "name": "already"},
    )
    assert r.status_code == 409


def test_new_folder_missing_parent_returns_404(client: TestClient) -> None:
    csrf = _csrf(client)
    # `target=ghost` — parent dir doesn't exist on disk yet.
    # Note: GET /admin/docs?target=ghost would 400 because we sanitize but the
    # path doesn't exist. We hit /admin/docs/new-folder directly with that target.
    r = client.post(
        "/admin/docs/new-folder",
        data={"csrf": csrf, "target": "ghost", "name": "newly"},
    )
    assert r.status_code in (404, 400)


def test_delete_non_empty_directory_returns_400(client: TestClient, tmp_path: Path) -> None:
    sec = tmp_path / "docs" / "filled"
    sec.mkdir()
    (sec / "child.md").write_text("# c\n", encoding="utf-8")
    csrf = _csrf(client)
    r = client.post(
        "/admin/docs/delete",
        data={"csrf": csrf, "target": "", "name": "filled"},
    )
    assert r.status_code == 400


def test_breadcrumb_accumulates_path(client: TestClient, tmp_path: Path) -> None:
    """Nested target should produce links that include the cumulative path,
    not just each segment in isolation."""
    nested = tmp_path / "docs" / "a" / "b"
    nested.mkdir(parents=True)
    r = client.get("/admin/docs?target=a/b")
    assert r.status_code == 200
    # The 'a' link must point at /admin/docs?target=a (not just a value of a).
    # The 'b' link must point at /admin/docs?target=a/b (cumulative).
    assert 'href="/admin/docs?target=a"' in r.text
    assert 'href="/admin/docs?target=a/b"' in r.text


def test_agent_page_renders(client: TestClient) -> None:
    r = client.get("/admin/agent")
    assert r.status_code == 200
    assert "Agent" in r.text


def test_agent_manual_upload(client: TestClient, tmp_path: Path) -> None:
    r = client.get("/admin/agent")
    import re

    csrf = re.search(r'name="csrf"\s+value="([^"]+)"', r.text).group(1)  # type: ignore[union-attr]
    r = client.post(
        "/admin/agent/upload",
        data={"csrf": csrf, "version": "9.9.9"},
        files={"binary": ("agent.exe", b"manual-bytes", "application/octet-stream")},
    )
    assert r.status_code in (200, 303)
    assert (tmp_path / "agent" / "windows" / "agent.exe").read_bytes() == b"manual-bytes"


def test_rotate_token_returns_value(client: TestClient) -> None:
    r = client.get("/admin/agent")
    import re

    csrf = re.search(r'name="csrf"\s+value="([^"]+)"', r.text).group(1)  # type: ignore[union-attr]
    r = client.post("/admin/agent/rotate-token", data={"csrf": csrf})
    assert r.status_code == 200
    assert "new_token" in r.text
    import re as _re
    assert _re.search(r"[A-Za-z0-9_-]{40,}", r.text)


def test_rename_rejects_extensionless_new_name(client: TestClient, tmp_path: Path) -> None:
    """Renaming a .md file to a name with no extension must 400, otherwise the
    file becomes unreachable via /docs/<name>. Original must be preserved."""
    (tmp_path / "docs" / "intro.md").write_text("# Intro\n", encoding="utf-8")
    csrf = _csrf(client)
    r = client.post(
        "/admin/docs/rename",
        data={"csrf": csrf, "target": "", "old": "intro.md", "new": "intro"},
    )
    assert r.status_code == 400
    assert (tmp_path / "docs" / "intro.md").is_file()
    assert not (tmp_path / "docs" / "intro").exists()


def test_rename_rejects_disallowed_extension(client: TestClient, tmp_path: Path) -> None:
    """Renaming to a name with an extension outside ALLOWED_DOC_EXT must 400."""
    (tmp_path / "docs" / "intro.md").write_text("# Intro\n", encoding="utf-8")
    csrf = _csrf(client)
    r = client.post(
        "/admin/docs/rename",
        data={"csrf": csrf, "target": "", "old": "intro.md", "new": "intro.exe"},
    )
    assert r.status_code == 400
    assert (tmp_path / "docs" / "intro.md").is_file()


def test_rename_directory_no_extension_check(client: TestClient, tmp_path: Path) -> None:
    """Directories rename freely — no extension constraint."""
    (tmp_path / "docs" / "old-section").mkdir()
    csrf = _csrf(client)
    r = client.post(
        "/admin/docs/rename",
        data={"csrf": csrf, "target": "", "old": "old-section", "new": "new-section"},
    )
    assert r.status_code in (200, 303)
    assert (tmp_path / "docs" / "new-section").is_dir()
