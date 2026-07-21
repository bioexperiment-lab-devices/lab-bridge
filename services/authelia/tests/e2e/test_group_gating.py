"""researcher cannot pass admins-only verify; admin can pass both."""

from __future__ import annotations

import httpx

from .test_forward_auth import _login


def test_researcher_denied_on_flash(http: httpx.Client) -> None:
    cookie = _login(http, "bob", "bob-password")
    r = http.get(
        "/api/verify",
        headers={
            "Cookie": cookie,
            "X-Forwarded-Host": "test.local",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Uri": "/flash",
            "X-Forwarded-Method": "GET",
        },
    )
    assert r.status_code == 403


def test_researcher_denied_on_api_admin(http: httpx.Client) -> None:
    cookie = _login(http, "bob", "bob-password")
    r = http.get(
        "/api/verify",
        headers={
            "Cookie": cookie,
            "X-Forwarded-Host": "test.local",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Uri": "/api/admin/labs/pc-1/update",
            "X-Forwarded-Method": "GET",
        },
    )
    assert r.status_code == 403


def test_researcher_allowed_on_jupyter(http: httpx.Client) -> None:
    cookie = _login(http, "bob", "bob-password")
    r = http.get(
        "/api/verify",
        headers={
            "Cookie": cookie,
            "X-Forwarded-Host": "test.local",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Uri": "/jupyter/lab",
            "X-Forwarded-Method": "GET",
        },
    )
    assert r.status_code == 200
