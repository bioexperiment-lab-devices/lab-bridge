"""Class 6 — auth state edge cases (brute-force regulation, OIDC handshake)."""

from __future__ import annotations

import secrets

import httpx

from clients import SessionLog, login
from conftest import Finding


def _attempt_login(target_url, verify_tls, username, password):
    log = SessionLog()
    with httpx.Client(
        base_url=target_url, verify=verify_tls, timeout=10.0, follow_redirects=False
    ) as c:
        r = c.post(
            "/api/auth/firstfactor",
            json={
                "username": username,
                "password": password,
                "targetURL": "/",
                "requestMethod": "GET",
                "keepMeLoggedIn": True,
            },
            headers={"Content-Type": "application/json", "Origin": target_url},
        )
    return r, log


def test_6_1_brute_force_regulation(target_url, verify_tls, anon_log, record):
    probe_user = f"bf-probe-{secrets.token_hex(4)}"
    statuses: list[int] = []
    for _ in range(5):
        r, _ = _attempt_login(target_url, verify_tls, probe_user, "wrong-password")
        statuses.append(r.status_code)
    distinct = len(set(statuses)) > 1
    record(
        Finding(
            id="6.1",
            title="Brute-force regulation triggers within max_retries+2",
            severity="Informational",
            status="informational" if distinct else "vulnerable",
            summary=(
                "Authelia is configured with max_retries=3, ban_time=5m. After 3 wrongs, "
                "response should change."
            ),
            details={
                "probe_user": probe_user,
                "statuses": statuses,
                "distinct_responses": distinct,
            },
        ),
        anon_log,
    )


def _follow_oidc(client: httpx.Client, target_url: str) -> list[int]:
    next_url: str = "/grafana/"
    statuses: list[int] = []
    for _ in range(7):
        r = client.get(next_url)
        statuses.append(r.status_code)
        if r.status_code not in (301, 302, 303, 307, 308):
            break
        loc = r.headers.get("location") or ""
        if not loc:
            break
        if loc.startswith("http"):
            u = httpx.URL(loc)
            if u.host != httpx.URL(target_url).host:
                break
            qs = u.query.decode() if isinstance(u.query, bytes) else u.query
            next_url = u.path + (("?" + qs) if qs else "")
        else:
            next_url = loc
    return statuses


def test_6_3_oidc_admin_handshake(target_url, verify_tls, admin_creds, record):
    log = SessionLog()
    client, _ = login(
        target_url,
        username=admin_creds[0],
        password=admin_creds[1],
        verify=verify_tls,
        log=log,
    )
    try:
        statuses = _follow_oidc(client, target_url)
        landed = bool(statuses) and statuses[-1] in (200, 302)
    finally:
        client.close()
    record(
        Finding(
            id="6.3",
            title="Admin completes OIDC handshake into Grafana",
            severity="Informational",
            status="informational" if landed else "vulnerable",
            summary=(
                "Authelia OIDC → Grafana should complete in ≤5 hops with a 200 or final auth cookie."
            ),
            details={"statuses": statuses},
        ),
        log,
    )


def test_6_4_oidc_researcher_handshake(
    target_url, verify_tls, researcher_creds, record
):
    log = SessionLog()
    client, _ = login(
        target_url,
        username=researcher_creds[0],
        password=researcher_creds[1],
        verify=verify_tls,
        log=log,
    )
    try:
        statuses = _follow_oidc(client, target_url)
        landed = bool(statuses) and statuses[-1] in (200, 302)
    finally:
        client.close()
    record(
        Finding(
            id="6.4",
            title="Researcher completes OIDC handshake into Grafana",
            severity="Informational",
            status="informational" if landed else "vulnerable",
            summary="Researcher group must also complete OIDC and land in Grafana.",
            details={"statuses": statuses},
        ),
        log,
    )
