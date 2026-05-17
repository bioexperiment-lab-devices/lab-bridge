"""Stub upstream for caddy e2e tests.

Routes:
  GET /html          → text/html with </head>, no CSP
  GET /html-csp      → text/html with </head>, CSP "default-src 'self'; script-src 'self' 'unsafe-inline'"
  GET /html-strict   → text/html with CSP "default-src 'none'; script-src 'self'"
  GET /html-no-script → text/html with CSP "default-src 'self'" (no explicit script-src)
  GET /json          → application/json {"ok": true}
  GET /css           → text/css "body{}"
  GET /tricky-html   → text/html containing literal "</head>" inside <script> CDATA
"""

from __future__ import annotations
import gzip
import io
from http.server import BaseHTTPRequestHandler, HTTPServer

PAGES = {
    "/html": (
        b"<!doctype html><html><head><title>x</title></head><body>hi</body></html>",
        "text/html",
        None,
    ),
    "/html-csp": (
        b"<!doctype html><html><head><title>x</title></head><body>hi</body></html>",
        "text/html",
        "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self'",
    ),
    "/html-strict": (
        b"<!doctype html><html><head><title>x</title></head><body>hi</body></html>",
        "text/html",
        "default-src 'none'; script-src 'self'; style-src 'self'",
    ),
    "/html-no-script": (
        b"<!doctype html><html><head><title>x</title></head><body>hi</body></html>",
        "text/html",
        "default-src 'self'",
    ),
    "/json": (b'{"ok": true}', "application/json", None),
    "/css": (b"body{}", "text/css", None),
    "/tricky-html": (
        b"<!doctype html><html><head><script>/*</head>*/</script></head><body>x</body></html>",
        "text/html",
        None,
    ),
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        path = self.path.split("?", 1)[0]
        if path not in PAGES:
            self.send_response(404)
            self.end_headers()
            return
        body, ctype, csp = PAGES[path]
        gzip_requested = "gzip" in self.headers.get("accept-encoding", "")
        payload = body
        encoding_header = None
        if gzip_requested and ctype.startswith("text/"):
            buf = io.BytesIO()
            with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
                gz.write(body)
            payload = buf.getvalue()
            encoding_header = "gzip"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        if csp:
            self.send_header("Content-Security-Policy", csp)
        if encoding_header:
            self.send_header("Content-Encoding", encoding_header)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args, **_kwargs) -> None:  # silence
        pass


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 9000), Handler).serve_forever()
