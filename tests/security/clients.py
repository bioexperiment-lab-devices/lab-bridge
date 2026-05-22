"""HTTP session helpers for the security audit harness.

Three session flavours: anonymous, researcher, admin. Each is a thin wrapper
around httpx.Client with an event hook that records request/response metadata
into a per-session log. Tests pull the latest exchanges from the log when
attaching evidence to findings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterator

import httpx


REDACT_HEADERS = {"authorization", "cookie", "set-cookie"}
TOKEN_RE = re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]+", re.IGNORECASE)
MAX_BODY = 2048


@dataclass
class Exchange:
    method: str
    url: str
    request_headers: dict[str, str]
    request_body: str
    status: int
    response_headers: dict[str, str]
    response_body: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "url": self.url,
            "request_headers": self.request_headers,
            "request_body": self.request_body,
            "status": self.status,
            "response_headers": self.response_headers,
            "response_body": self.response_body,
        }


@dataclass
class SessionLog:
    exchanges: list[Exchange] = field(default_factory=list)

    def latest(self, n: int = 5) -> list[Exchange]:
        return self.exchanges[-n:]


def _redact_header_value(name: str, value: str) -> str:
    n = name.lower()
    if n == "authorization":
        return TOKEN_RE.sub(r"\1<redacted>", value) if "bearer" in value.lower() else "<redacted>"
    if n == "cookie":
        return _mask_cookie_header(value)
    if n == "set-cookie":
        return _mask_set_cookie(value)
    return value


def _mask_cookie_header(value: str) -> str:
    parts = []
    for chunk in value.split(";"):
        chunk = chunk.strip()
        if "=" in chunk:
            name, val = chunk.split("=", 1)
            parts.append(f"{name}={_mask(val)}")
        else:
            parts.append(chunk)
    return "; ".join(parts)


def _mask_set_cookie(value: str) -> str:
    first, sep, rest = value.partition(";")
    if "=" in first:
        name, val = first.split("=", 1)
        first = f"{name}={_mask(val)}"
    return first + sep + rest


def _mask(val: str) -> str:
    val = val.strip()
    if not val:
        return ""
    prefix = val[:6]
    return f"{prefix}...({len(val)} chars)"


def _truncate(s: str | bytes) -> str:
    if isinstance(s, bytes):
        try:
            s = s.decode("utf-8", errors="replace")
        except Exception:
            s = str(s)
    if len(s) > MAX_BODY:
        return s[:MAX_BODY] + f"...<truncated {len(s) - MAX_BODY} bytes>"
    return s


def make_hooks(log: SessionLog) -> dict[str, list]:
    def on_response(response: httpx.Response) -> None:
        request = response.request
        try:
            request_body = _truncate(request.content) if request.content else ""
        except Exception:
            request_body = "<unreadable>"
        try:
            response.read()
            response_body = _truncate(response.content) if response.content else ""
        except Exception:
            response_body = "<unreadable>"
        exchange = Exchange(
            method=request.method,
            url=str(request.url),
            request_headers={
                k: _redact_header_value(k, v) for k, v in request.headers.items()
            },
            request_body=request_body,
            status=response.status_code,
            response_headers={
                k: _redact_header_value(k, v) for k, v in response.headers.items()
            },
            response_body=response_body,
        )
        log.exchanges.append(exchange)

    return {"response": [on_response]}


def make_client(
    target_url: str,
    *,
    verify: bool,
    log: SessionLog,
    cookies: dict[str, str] | None = None,
    follow_redirects: bool = False,
) -> httpx.Client:
    return httpx.Client(
        base_url=target_url,
        verify=verify,
        timeout=15.0,
        follow_redirects=follow_redirects,
        cookies=cookies or {},
        event_hooks=make_hooks(log),
    )


def login(
    target_url: str,
    *,
    username: str,
    password: str,
    verify: bool,
    log: SessionLog,
) -> tuple[httpx.Client, dict[str, str]]:
    """POST /api/auth/firstfactor and return a client with the session cookie.

    Returns (client, captured_set_cookies) so tests can assert on cookie
    attributes from the original response.
    """
    with httpx.Client(
        base_url=target_url,
        verify=verify,
        timeout=15.0,
        follow_redirects=False,
        event_hooks=make_hooks(log),
    ) as bootstrap:
        r = bootstrap.post(
            "/api/auth/firstfactor",
            json={
                "username": username,
                "password": password,
                "targetURL": "/",
                "requestMethod": "GET",
                "keepMeLoggedIn": True,
            },
            headers={
                "Content-Type": "application/json",
                "Origin": target_url,
                "Referer": f"{target_url}/login",
            },
        )
    if r.status_code != 200:
        raise RuntimeError(f"login failed: {r.status_code} {r.text[:200]}")
    cookies = {}
    set_cookies: list[str] = []
    for header_name, header_value in r.headers.multi_items():
        if header_name.lower() == "set-cookie":
            set_cookies.append(header_value)
            name, _, rest = header_value.partition("=")
            value = rest.split(";", 1)[0]
            cookies[name.strip()] = value
    client = make_client(target_url, verify=verify, log=log, cookies=cookies)
    return client, {"raw_set_cookies": "\n".join(set_cookies), **cookies}


def iter_redirects(client: httpx.Client, method: str, path: str, **kwargs) -> Iterator[httpx.Response]:
    """Follow redirects manually up to 5 hops, yielding each response."""
    current_method = method
    current_path = path
    for _ in range(5):
        r = client.request(current_method, current_path, **kwargs)
        yield r
        if r.status_code not in (301, 302, 303, 307, 308):
            return
        loc = r.headers.get("location")
        if not loc:
            return
        current_path = loc
        current_method = "GET" if r.status_code == 303 else current_method
        kwargs.pop("json", None)
        kwargs.pop("data", None)
