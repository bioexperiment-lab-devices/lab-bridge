"""Class 4 — header / X-Forwarded smuggling."""

from __future__ import annotations

import httpx

from conftest import Finding


def test_4_1_xforwarded_user_injection(target_url, verify_tls, anon_log, record):
    with httpx.Client(
        base_url=target_url, verify=verify_tls, timeout=10.0, follow_redirects=False
    ) as c:
        r = c.get(
            "/flash/",
            headers={
                "X-Forwarded-User": "admin",
                "Remote-User": "admin",
                "Remote-Groups": "admins",
                "Remote-Name": "Admin",
                "Remote-Email": "admin@example.com",
            },
        )
    ok = r.status_code == 302 and "/login" in (r.headers.get("location") or "")
    record(
        Finding(
            id="4.1",
            title="X-Forwarded-User / Remote-Groups must not grant access",
            severity="Critical",
            status="verified" if ok else "vulnerable",
            summary="Caddy must strip identity headers from client requests before reverse_proxy.",
            details={"status_code": r.status_code, "location": r.headers.get("location")},
        ),
        anon_log,
    )
    assert ok, (
        f"identity-header smuggling worked: {r.status_code} → {r.headers.get('location')}"
    )


def test_4_2_xforwarded_host_login(target_url, verify_tls, anon_log, record):
    with httpx.Client(
        base_url=target_url, verify=verify_tls, timeout=10.0, follow_redirects=False
    ) as c:
        r = c.get("/login", headers={"X-Forwarded-Host": "evil.example"})
    body = r.text
    has_evil = "evil.example" in body
    record(
        Finding(
            id="4.2",
            title="X-Forwarded-Host on /login must not influence rendered form action",
            severity="Medium",
            status="vulnerable" if has_evil else "verified",
            summary="The login page must always post back to the real host.",
            details={"status_code": r.status_code, "evil_present": has_evil},
        ),
        anon_log,
    )
    assert not has_evil, "evil host reflected in login page"


def test_4_3_xforwarded_uri_firstfactor(target_url, verify_tls, anon_log, record):
    with httpx.Client(
        base_url=target_url, verify=verify_tls, timeout=10.0, follow_redirects=False
    ) as c:
        r = c.post(
            "/api/auth/firstfactor",
            json={
                "username": "nonexistent-bogus",
                "password": "wrong",
                "targetURL": "/flash/",
                "requestMethod": "GET",
                "keepMeLoggedIn": True,
            },
            headers={
                "X-Forwarded-Uri": "/flash/",
                "Origin": target_url,
                "Referer": f"{target_url}/login",
            },
        )
    ok = r.status_code in (200, 401, 403, 400)
    grants_access = r.status_code == 200 and bool(r.cookies.get("authelia_session"))
    record(
        Finding(
            id="4.3",
            title="Manipulated X-Forwarded-Uri must not grant access on bad creds",
            severity="Critical",
            status="vulnerable" if grants_access else "verified",
            summary="Forwarded headers must never bypass credential verification.",
            details={
                "status_code": r.status_code,
                "set_cookie_present": bool(r.cookies.get("authelia_session")),
            },
        ),
        anon_log,
    )
    assert ok and not grants_access


def test_4_4_host_header_injection(target_url, verify_tls, anon_log, record):
    with httpx.Client(
        base_url=target_url, verify=verify_tls, timeout=10.0, follow_redirects=False
    ) as c:
        r = c.get("/", headers={"Host": "evil.example"})
    body_excerpt = r.text[:200]
    suspicious_200 = r.status_code == 200 and "evil.example" in body_excerpt
    record(
        Finding(
            id="4.4",
            title="Host header injection must not serve the platform under another name",
            severity="Low",
            status="vulnerable" if suspicious_200 else "verified",
            summary="Caddy should refuse or default-route requests with a foreign Host header.",
            details={"status_code": r.status_code, "body_excerpt": body_excerpt},
        ),
        anon_log,
    )
    assert not suspicious_200
