"""Class 5 — information disclosure and headers."""

from __future__ import annotations

import socket
import ssl

import pytest

from conftest import Finding


def test_5_1_security_headers(anon, anon_log, record):
    r = anon.get("/")
    headers = {k.lower(): v for k, v in r.headers.items()}
    expected = {
        "strict-transport-security": "max-age=",
        "x-content-type-options": "nosniff",
        "referrer-policy": None,
        "content-security-policy": None,
    }
    missing = []
    for h, contains in expected.items():
        v = headers.get(h)
        if v is None:
            missing.append(h)
        elif contains and contains not in v.lower():
            missing.append(f"{h} (does not contain {contains!r})")
    severity = "Low" if missing else "Informational"
    record(
        Finding(
            id="5.1",
            title="Security headers on the platform root",
            severity=severity,
            status="vulnerable" if missing else "verified",
            summary=(
                "Hardening miss: missing security headers " + ", ".join(missing)
                if missing
                else "All checked headers present."
            ),
            details={"missing": missing, "present": {h: headers.get(h) for h in expected}},
        ),
        anon_log,
    )


def test_5_2_healthz_not_exposed(anon, anon_log, record):
    r = anon.get("/healthz")
    ok = r.status_code == 404
    record(
        Finding(
            id="5.2",
            title="/healthz must not be reachable through Caddy",
            severity="Low",
            status="verified" if ok else "vulnerable",
            summary="Per-service /healthz endpoints are docker-network-only.",
            details={"status_code": r.status_code},
        ),
        anon_log,
    )
    assert ok, f"/healthz exposed: {r.status_code}"


def test_5_3_no_traceback(anon, anon_log, record):
    r = anon.get("/api/public/server-info")
    body = r.text
    looks_like_traceback = "Traceback" in body or "raise " in body
    ok = not looks_like_traceback
    record(
        Finding(
            id="5.3",
            title="No Python tracebacks in API responses",
            severity="Low",
            status="verified" if ok else "vulnerable",
            summary="Production responses must not leak stack traces.",
            details={"status_code": r.status_code, "body_excerpt": body[:200]},
        ),
        anon_log,
    )
    assert ok


def test_5_4_server_info_fields(anon, anon_log, record):
    r = anon.get("/api/public/server-info")
    body = {}
    try:
        body = r.json()
    except Exception:
        pass
    keys = sorted(body.keys()) if isinstance(body, dict) else []
    record(
        Finding(
            id="5.4",
            title="/api/public/server-info field inventory",
            severity="Informational",
            status="informational",
            summary="Fields returned to anonymous callers — review for unexpected additions.",
            details={"status_code": r.status_code, "keys": keys},
        ),
        anon_log,
    )


def test_5_5_attempted_path_xss(anon, anon_log, record):
    payload = "/<script>alert(1)</script>"
    r = anon.get(payload)
    body = r.text
    raw_present = "<script>alert(1)</script>" in body
    escaped_present = (
        "&lt;script&gt;alert(1)&lt;/script&gt;" in body or "&#x3C;script" in body
    )
    ok = (not raw_present) or escaped_present
    record(
        Finding(
            id="5.5",
            title="attempted_path reflected XSS in 404/403",
            severity="High",
            status="verified" if ok else "vulnerable",
            summary="The 403/404 template must HTML-escape the attempted path.",
            details={
                "status_code": r.status_code,
                "raw_present": raw_present,
                "escaped_present": escaped_present,
            },
        ),
        anon_log,
    )
    assert ok, "attempted_path renders raw script"


def test_5_6_open_redirect(anon, anon_log, record):
    r = anon.get("/login", params={"rd": "https://evil.example/"})
    record(
        Finding(
            id="5.6",
            title="Open-redirect via /login?rd=",
            severity="Low",
            status="informational",
            summary=(
                "The login form sets `rd` as a query param. Real exploit requires "
                "a successful login that 302s to the value — only a finding if the final "
                "redirect leaves the VPS host. We capture the page render here; full flow "
                "tested via session class."
            ),
            details={
                "status_code": r.status_code,
                "body_has_rd": "evil.example" in r.text,
            },
        ),
        anon_log,
    )


def test_5_7_tls_protocols(target_host, record):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with socket.create_connection((target_host, 443), timeout=5) as sock:
        with ctx.wrap_socket(sock, server_hostname=target_host) as ssock:
            proto = ssock.version()
            cipher = ssock.cipher()
            peer_cert = ssock.getpeercert(binary_form=True)
    record(
        Finding(
            id="5.7",
            title="TLS protocol and cipher",
            severity="Informational",
            status="informational",
            summary=f"Negotiated {proto} / {cipher[0] if cipher else 'unknown'}",
            details={"protocol": proto, "cipher": str(cipher), "cert_len": len(peer_cert)},
        ),
    )


@pytest.mark.parametrize(
    "path", ["/loki/api/v1/labels", "/prometheus/", "/api/datasources/proxy/1/"]
)
def test_5_8_internal_observability_not_exposed(anon, anon_log, record, path):
    r = anon.get(path)
    ok = r.status_code == 404 or (
        r.status_code == 302 and "/login" in (r.headers.get("location") or "")
    )
    record(
        Finding(
            id=f"5.8({path})",
            title=f"Internal observability path {path} must not be reachable",
            severity="High",
            status="verified" if ok else "vulnerable",
            summary="Loki/Prometheus must not be proxied directly by Caddy.",
            details={
                "path": path,
                "status_code": r.status_code,
                "location": r.headers.get("location"),
            },
        ),
        anon_log,
    )
    assert ok, f"{path} → {r.status_code}"
