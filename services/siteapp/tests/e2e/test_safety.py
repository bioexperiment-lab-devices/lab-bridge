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
    # The raw <script> must be absent — bleach strips it entirely (strip=True).
    assert "<script>" not in body, "raw <script> tag leaked into rendered HTML"
