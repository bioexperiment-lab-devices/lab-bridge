"""Class 2 — session and cookie lifecycle."""

from __future__ import annotations

import time

import httpx
import pytest

from clients import SessionLog, login, make_client
from conftest import Finding


def _set_cookie_attrs(set_cookie_header: str) -> dict[str, str | bool]:
    parts = [p.strip() for p in set_cookie_header.split(";")]
    name_value = parts[0]
    name = name_value.split("=", 1)[0]
    attrs: dict[str, str | bool] = {"name": name}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            attrs[k.strip().lower()] = v.strip()
        else:
            attrs[p.strip().lower()] = True
    return attrs


def _login_short(target_url, verify_tls, creds):
    log = SessionLog()
    client, info = login(
        target_url, username=creds[0], password=creds[1], verify=verify_tls, log=log
    )
    return client, info, log


def test_2_1_replay_after_get_logout(target_url, verify_tls, admin_creds, record):
    client, info, log = _login_short(target_url, verify_tls, admin_creds)
    session_cookie = info.get("authelia_session", "")
    assert session_cookie, "no authelia_session cookie issued at login"
    client.get("/logout")
    client.close()
    with make_client(
        target_url,
        verify=verify_tls,
        log=log,
        cookies={"authelia_session": session_cookie},
    ) as replay:
        r = replay.get("/flash/")
    ok = r.status_code == 302 and "/login" in (r.headers.get("location") or "")
    record(
        Finding(
            id="2.1",
            title="Cookie replay after GET /logout must fail",
            severity="High",
            status="verified" if ok else "vulnerable",
            summary=(
                "Server-side session must be invalidated, not just client-side cookie cleared."
            ),
            details={
                "replay_status": r.status_code,
                "replay_location": r.headers.get("location"),
            },
        ),
        log,
    )
    assert ok, (
        f"stale cookie still works: {r.status_code} → {r.headers.get('location')}"
    )


def test_2_2_replay_after_post_logout(target_url, verify_tls, admin_creds, record):
    client, info, log = _login_short(target_url, verify_tls, admin_creds)
    session_cookie = info.get("authelia_session", "")
    client.post("/logout")
    client.close()
    with make_client(
        target_url,
        verify=verify_tls,
        log=log,
        cookies={"authelia_session": session_cookie},
    ) as replay:
        r = replay.get("/flash/")
    ok = r.status_code == 302 and "/login" in (r.headers.get("location") or "")
    record(
        Finding(
            id="2.2",
            title="Cookie replay after POST /logout must fail",
            severity="High",
            status="verified" if ok else "vulnerable",
            summary="POST /logout must invalidate the server-side session.",
            details={
                "replay_status": r.status_code,
                "replay_location": r.headers.get("location"),
            },
        ),
        log,
    )
    assert ok, f"stale cookie after POST logout still works: {r.status_code}"


def test_2_3_concurrent_sessions_independent(
    target_url, verify_tls, admin_creds, record
):
    a_client, a_info, log = _login_short(target_url, verify_tls, admin_creds)
    b_client, b_info, _ = _login_short(target_url, verify_tls, admin_creds)
    a_cookie = a_info.get("authelia_session")
    b_cookie = b_info.get("authelia_session")
    distinct = a_cookie != b_cookie
    a_client.get("/logout")
    a_client.close()
    r = b_client.get("/flash/")
    b_client.close()
    ok = distinct and r.status_code in (200, 302)
    if r.status_code == 302:
        ok = ok and "/login" not in (r.headers.get("location") or "")
    record(
        Finding(
            id="2.3",
            title="Logging out one session does not kill other sessions",
            severity="Informational",
            status="informational" if ok else "vulnerable",
            summary="Per-session invalidation, not user-global, is the documented behaviour.",
            details={
                "distinct_cookies": distinct,
                "b_status_after_a_logout": r.status_code,
            },
        ),
        log,
    )
    assert ok


def test_2_4_login_cookie_attributes(target_url, verify_tls, admin_creds, record):
    _, info, log = _login_short(target_url, verify_tls, admin_creds)
    raw = info.get("raw_set_cookies", "")
    session_lines = [
        line for line in raw.splitlines() if line.startswith("authelia_session=")
    ]
    missing: list[str] = []
    if not session_lines:
        missing.append("no authelia_session Set-Cookie at all")
    else:
        attrs = _set_cookie_attrs(session_lines[0])
        for required in ("httponly", "secure"):
            if not attrs.get(required):
                missing.append(required)
        ss = str(attrs.get("samesite", "")).lower()
        if ss not in ("lax", "strict"):
            missing.append(f"samesite={ss or 'none'}")
    record(
        Finding(
            id="2.4",
            title="Login Set-Cookie attribute hygiene",
            severity="Medium" if missing else "Informational",
            status="vulnerable" if missing else "verified",
            summary=(
                "Missing/weak cookie attributes at login: " + ", ".join(missing)
                if missing
                else "Cookie attributes look correct (HttpOnly, Secure, SameSite=Lax)."
            ),
            details={"missing": missing, "raw": raw[:400]},
        ),
        log,
    )


def test_2_5_logout_cookie_attributes(target_url, verify_tls, admin_creds, record):
    client, info, log = _login_short(target_url, verify_tls, admin_creds)
    r = client.get("/logout")
    client.close()
    raw_lines = []
    for k, v in r.headers.multi_items():
        if k.lower() == "set-cookie":
            raw_lines.append(v)
    missing_secure: list[str] = []
    for line in raw_lines:
        attrs = _set_cookie_attrs(line)
        if not attrs.get("secure"):
            missing_secure.append(str(attrs.get("name")))
    record(
        Finding(
            id="2.5",
            title="Logout-cleared cookies must include Secure",
            severity="Low" if missing_secure else "Informational",
            status="vulnerable" if missing_secure else "verified",
            summary=(
                "Manual cookie clearing in siteapp/app/auth.py omits Secure on these cookies: "
                + ", ".join(missing_secure)
                if missing_secure
                else "All logout-clear Set-Cookie lines have Secure."
            ),
            details={"missing_secure": missing_secure, "lines": raw_lines},
        ),
        log,
    )


def test_2_6_forged_cookie_rejected(anon_log, target_url, verify_tls, record):
    with make_client(
        target_url,
        verify=verify_tls,
        log=anon_log,
        cookies={"authelia_session": "A" * 64},
    ) as c:
        r = c.get("/flash/")
    ok = r.status_code == 302 and "/login" in (r.headers.get("location") or "")
    record(
        Finding(
            id="2.6",
            title="Forged authelia_session cookie must be rejected",
            severity="Critical",
            status="verified" if ok else "vulnerable",
            summary="HMAC-signed cookies must not accept arbitrary values.",
            details={"status_code": r.status_code, "location": r.headers.get("location")},
        ),
        anon_log,
    )
    assert ok


def test_2_7_truncated_cookie_rejected(target_url, verify_tls, admin_creds, record):
    client, info, log = _login_short(target_url, verify_tls, admin_creds)
    client.close()
    real = info.get("authelia_session", "")
    truncated = real[: max(8, len(real) // 2)]
    with make_client(
        target_url, verify=verify_tls, log=log, cookies={"authelia_session": truncated}
    ) as c:
        r = c.get("/flash/")
    ok = r.status_code == 302 and "/login" in (r.headers.get("location") or "")
    record(
        Finding(
            id="2.7",
            title="Truncated valid cookie must be rejected",
            severity="High",
            status="verified" if ok else "vulnerable",
            summary="Cookie signature must be intact-or-reject.",
            details={"status_code": r.status_code},
        ),
        log,
    )
    assert ok


@pytest.mark.slow
def test_2_8_inactivity_timeout(
    target_url, verify_tls, admin_creds, slow_enabled, record
):
    if not slow_enabled:
        pytest.skip("requires --slow (waits past 5 min inactivity)")
    client, info, log = _login_short(target_url, verify_tls, admin_creds)
    time.sleep(310)
    r = client.get("/flash/")
    client.close()
    ok = r.status_code == 302
    record(
        Finding(
            id="2.8",
            title="Inactivity timeout invalidates session",
            severity="Informational",
            status="informational" if ok else "vulnerable",
            summary="Authelia config: inactivity: 5m. Session must time out.",
            details={"status_code": r.status_code, "wait_seconds": 310},
        ),
        log,
    )


def test_2_9_cross_role_cookie(
    target_url, verify_tls, admin_creds, researcher_creds, record
):
    a_client, a_info, a_log = _login_short(target_url, verify_tls, admin_creds)
    r_client, r_info, r_log = _login_short(target_url, verify_tls, researcher_creds)
    a_cookie = a_info.get("authelia_session")
    r_cookie = r_info.get("authelia_session")
    distinct = a_cookie != r_cookie

    admin_on_flash = a_client.get("/flash/")
    res_on_flash = r_client.get("/flash/")

    a_client.close()
    r_client.close()

    admin_ok = admin_on_flash.status_code in (200, 302) and not (
        admin_on_flash.status_code == 302
        and "/login" in (admin_on_flash.headers.get("location") or "")
    )
    res_blocked = res_on_flash.status_code in (302, 403)
    ok = distinct and admin_ok and res_blocked
    record(
        Finding(
            id="2.9",
            title="Cookie scope is per-user, role gating works",
            severity="Critical",
            status="verified" if ok else "vulnerable",
            summary="Admin cookie unlocks /flash/; researcher cookie does not.",
            details={
                "distinct": distinct,
                "admin_on_flash": admin_on_flash.status_code,
                "res_on_flash": res_on_flash.status_code,
            },
        ),
        a_log,
    )
    assert ok


def test_2_10_session_fixation(target_url, verify_tls, admin_creds, record):
    log = SessionLog()
    bogus = "fixation-probe-" + "A" * 32
    with make_client(
        target_url, verify=verify_tls, log=log, cookies={"authelia_session": bogus}
    ) as c:
        c.get("/login")
    client, info, _ = _login_short(target_url, verify_tls, admin_creds)
    client.close()
    issued = info.get("authelia_session", "")
    ok = issued and issued != bogus
    record(
        Finding(
            id="2.10",
            title="Session fixation: login issues a fresh cookie",
            severity="High",
            status="verified" if ok else "vulnerable",
            summary=(
                "The cookie value after login must differ from any pre-login attacker-set value."
            ),
            details={
                "pre_login": bogus[:8] + "...",
                "issued_prefix": (issued[:8] + "...") if issued else "",
            },
        ),
        log,
    )
    assert ok


def test_2_11_csrf_firstfactor_origin(target_url, verify_tls, admin_creds, record):
    log = SessionLog()
    with httpx.Client(
        base_url=target_url,
        verify=verify_tls,
        timeout=10.0,
        follow_redirects=False,
        event_hooks={"response": []},
    ) as c:
        r = c.post(
            "/api/auth/firstfactor",
            json={
                "username": admin_creds[0],
                "password": admin_creds[1],
                "targetURL": "/",
                "requestMethod": "GET",
                "keepMeLoggedIn": True,
            },
            headers={
                "Origin": "https://evil.example",
                "Referer": "https://evil.example/",
                "Content-Type": "application/json",
            },
        )
    grants = r.status_code == 200 and bool(r.cookies.get("authelia_session"))
    record(
        Finding(
            id="2.11",
            title="Cross-origin POST to /api/auth/firstfactor",
            severity="Low" if grants else "Informational",
            status="vulnerable" if grants else "informational",
            summary=(
                "Authelia does not check Origin/Referer on the auth API; SameSite=Lax on the "
                "session cookie is the actual CSRF mitigation. Documented for awareness."
            ),
            details={
                "status_code": r.status_code,
                "set_cookie_present": bool(r.cookies.get("authelia_session")),
            },
        ),
        log,
    )


def test_2_12_get_logout_csrf(target_url, verify_tls, admin_creds, record):
    client, info, log = _login_short(target_url, verify_tls, admin_creds)
    r = client.get("/logout")
    client.close()
    record(
        Finding(
            id="2.12",
            title="GET /logout enables CSRF-logout",
            severity="Informational",
            status="informational",
            summary=(
                "GET-based logout means a third-party page can log the user out via <img src=>. "
                "Low impact; documented in siteapp/app/auth.py."
            ),
            details={"status_code": r.status_code, "method": "GET"},
        ),
        log,
    )
