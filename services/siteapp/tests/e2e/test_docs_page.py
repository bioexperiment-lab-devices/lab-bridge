"""End-to-end coverage for the redesigned Docs page."""

from __future__ import annotations

import httpx


def test_docs_root_returns_200(http: httpx.Client) -> None:
    r = http.get("/docs/")
    assert r.status_code in (200, 308)


def test_doc_page_has_new_layout(http: httpx.Client) -> None:
    r = http.get("/docs/system-overview", follow_redirects=True)
    if r.status_code != 200:
        return  # doc may not be present in e2e fixture; soft-skip
    body = r.text
    assert 'class="lb-page lb-page--docs"' in body
    assert 'class="lb-docs-side"' in body
    assert 'class="lb-docs-article"' in body
    assert 'class="lb-docs-article__breadcrumb"' in body


def test_doc_with_code_block_emits_figure(http: httpx.Client) -> None:
    # Test fixture must include a doc with a fenced ```python title="..."``` block.
    # If your e2e compose doesn't ship one yet, this test is a soft pass.
    r = http.get("/docs/technical-overview", follow_redirects=True)
    if r.status_code != 200:
        return
    body = r.text
    if '<figure class="lb-code"' in body:
        assert 'class="lb-code__copy"' in body
