from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Home\n\nWelcome\n", encoding="utf-8")
    (docs / "intro.md").write_text("# Intro\n\nhello world\n", encoding="utf-8")
    (docs / "intro.ru.md").write_text("# Введение\n\nпривет\n", encoding="utf-8")
    (docs / "diagram.md").write_text(
        "# Diagram\n\n```mermaid\nflowchart LR\n  A --> B\n```\n",
        encoding="utf-8",
    )
    section = docs / "section"
    section.mkdir()
    (section / "index.md").write_text("# Section\n", encoding="utf-8")
    (section / "page.md").write_text("# Page\n", encoding="utf-8")
    icons = docs / "icons"
    icons.mkdir()
    (icons / "jupyter.svg").write_bytes(
        b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" '
        b'width="28" height="28"><circle r="14" cx="14" cy="14" fill="orange"/></svg>'
    )
    (icons / "secret.exe").write_bytes(b"MZ\x90\x00")
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "x")
    from importlib import reload

    import app.main

    reload(app.main)
    return TestClient(app.main.app)


def test_docs_index_renders(client: TestClient) -> None:
    r = client.get("/docs/")
    assert r.status_code == 200
    assert "Welcome" in r.text


def test_page_renders(client: TestClient) -> None:
    r = client.get("/docs/intro")
    assert r.status_code == 200
    assert "hello world" in r.text


def test_directory_without_slash_redirects(client: TestClient) -> None:
    r = client.get("/docs/section", follow_redirects=False)
    assert r.status_code == 308
    assert r.headers["location"].endswith("/docs/section/")


def test_lang_query_switches_to_russian(client: TestClient) -> None:
    r = client.get("/docs/intro?lang=ru")
    assert r.status_code == 200
    assert "привет" in r.text


def test_lang_falls_back_to_english(client: TestClient) -> None:
    r = client.get("/docs/section/page?lang=ru")
    assert r.status_code == 200
    assert "Page" in r.text


def test_lang_cookie_persists(client: TestClient) -> None:
    r = client.get("/docs/intro?lang=ru", follow_redirects=False)
    assert r.cookies.get("lang") == "ru"
    client.cookies.set("lang", "ru")
    r2 = client.get("/docs/intro")
    assert "привет" in r2.text


def test_missing_returns_404(client: TestClient) -> None:
    assert client.get("/docs/nope").status_code == 404


def test_orphan_ru_only_returns_404(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "docs" / "only.ru.md").write_text("# Только\n", encoding="utf-8")
    assert client.get("/docs/only").status_code == 404


def test_url_encoded_traversal_returns_404_not_redirect(client: TestClient) -> None:
    """A URL-encoded `..` segment must not leak directory existence via 308.
    Without safe_join, `/docs/..%2Fagent` would 308 to `/docs/../agent/`.
    With safe_join, traversal is treated like a missing doc -> 404."""
    r = client.get("/docs/..%2Fagent", follow_redirects=False)
    assert r.status_code == 404


def test_diagram_page_loads_mermaid_script(client: TestClient) -> None:
    r = client.get("/docs/diagram")
    assert r.status_code == 200
    assert "/_static/mermaid-init.js" in r.text


def test_plain_page_does_not_load_mermaid_script(client: TestClient) -> None:
    r = client.get("/docs/intro")
    assert r.status_code == 200
    assert "/_static/mermaid-init.js" not in r.text


def test_doc_static_svg_is_served(client: TestClient) -> None:
    r = client.get("/docs/icons/jupyter.svg")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert b"<svg" in r.content


def test_doc_static_disallowed_extension_is_404(client: TestClient) -> None:
    r = client.get("/docs/icons/secret.exe")
    assert r.status_code == 404


def test_doc_static_missing_file_is_404(client: TestClient) -> None:
    r = client.get("/docs/icons/nope.svg")
    assert r.status_code == 404
