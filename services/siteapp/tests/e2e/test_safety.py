"""HTML-escape on rendered markdown.

The siteapp markdown renderer must strip raw <script> tags from rendered
documents (defence-in-depth even though public_docs/ is now repo-tracked).
This test renders the xss-test.md fixture and asserts the script tag
does not appear in the rendered HTML.
"""

from __future__ import annotations


def test_rendered_markdown_strips_script_tag(http) -> None:
    rendered = http.get("/docs/xss-test")
    assert rendered.status_code == 200
    body = rendered.text
    # The page legitimately includes inline <script> tags (theme boot in
    # base.html, sidebar interactivity), so we match against the XSS
    # payload's specific signature rather than any <script> occurrence.
    # xss-test.md contains <script>alert('xss')</script>; bleach must
    # strip the wrapper so the alert text renders as plain content with
    # no surrounding script tag.
    assert "<script>alert" not in body, "user-supplied <script>alert leaked into rendered HTML"
    assert "alert('xss')" in body, "expected sanitized payload text to survive as plain text"
