"""Path-traversal in admin upload + HTML-escape on rendered markdown.

These are siteapp-behaviour assertions formerly in test_siteapp_safety.bats.
The /admin/* docs upload endpoints are operator-authenticated at the Caddy
edge in production — in the harness there's no Caddy, so we hit the routes
on the siteapp port directly. (Siteapp itself enforces request-shape
validation independent of who's authenticated at the edge.)

Note: /admin/docs/upload requires a valid CSRF token. We fetch one from
GET /admin/docs and parse it from the HTML response before posting.
"""
from __future__ import annotations

import io
import re


def _get_csrf_token(http) -> str:
    """Fetch a CSRF token from the admin docs page."""
    r = http.get("/admin/docs")
    assert r.status_code == 200, f"admin docs page failed: {r.status_code}"
    # The CSRF token is in a hidden input: <input ... name="csrf" value="...">
    m = re.search(r'name="csrf"\s+value="([^"]+)"', r.text)
    if not m:
        m = re.search(r'value="([^"]+)"\s+name="csrf"', r.text)
    assert m is not None, f"CSRF token not found in admin docs HTML. Body excerpt: {r.text[:500]}"
    return m.group(1)


def test_admin_docs_upload_rejects_traversal_target(http) -> None:
    csrf = _get_csrf_token(http)
    files = {"files": ("test.md", io.BytesIO(b"# hi"), "text/markdown")}
    data = {"target": "../escape.md", "csrf": csrf}
    # /admin/ endpoints normally sit behind Caddy basic_auth in prod.
    # We hit siteapp directly; the route should still validate `target`.
    r = http.post("/admin/docs/upload", files=files, data=data)
    # Expect 400 (traversal rejected) — NOT 200/302 (would mean traversal accepted).
    assert r.status_code == 400, (
        f"path traversal not rejected: got {r.status_code} body={r.text!r}"
    )


def test_uploaded_markdown_with_raw_html_is_escaped(http) -> None:
    """An admin-uploaded .md containing raw <script> renders escaped, so a
    viewer's browser doesn't execute it (defence against an admin
    uploading user-supplied markdown)."""
    csrf = _get_csrf_token(http)
    payload = b"# Title\n\n<script>alert('xss')</script>\n"
    files = {"files": ("xss-test.md", io.BytesIO(payload), "text/markdown")}
    data = {"target": "", "csrf": csrf}
    up = http.post("/admin/docs/upload", files=files, data=data)
    # Successful upload redirects to /admin/docs; follow redirect
    assert up.status_code in (200, 302, 303), f"upload failed: {up.status_code} {up.text}"

    rendered = http.get("/docs/xss-test")
    assert rendered.status_code == 200
    body = rendered.text
    # The raw <script> must be absent — bleach strips it entirely (strip=True).
    assert "<script>" not in body, "raw <script> tag leaked into rendered HTML"
