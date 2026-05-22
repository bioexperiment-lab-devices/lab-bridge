"""Class 1 — direct-path auth bypass.

See docs/superpowers/specs/2026-05-22-security-audit-design.md §"Class 1".
"""

from __future__ import annotations

import httpx
import pytest

from conftest import Finding


def _expect_redirect_or_forbidden(resp: httpx.Response) -> bool:
    if resp.status_code == 302:
        return "/login" in (resp.headers.get("location") or "")
    return resp.status_code in (401, 403)


def test_1_1_anon_flash_index(anon, anon_log, record):
    r = anon.get("/flash/")
    ok = _expect_redirect_or_forbidden(r)
    record(
        Finding(
            id="1.1",
            title="Anonymous GET /flash/ must require auth",
            severity="Critical",
            status="verified" if ok else "vulnerable",
            summary="/flash/ must redirect anonymous users to /login or return 403.",
            details={"status_code": r.status_code, "location": r.headers.get("location")},
        ),
        anon_log,
    )
    assert ok, f"expected redirect to /login or 403, got {r.status_code}"


def test_1_2_anon_flash_api_firmware(anon, anon_log, record):
    r = anon.get("/flash/api/firmware")
    ok = _expect_redirect_or_forbidden(r)
    record(
        Finding(
            id="1.2",
            title="/flash/api/firmware must require admin auth",
            severity="Critical",
            status="verified" if ok else "vulnerable",
            summary=(
                "Operator firmware listing must be behind Authelia admin gate; "
                "the Caddyfile's /flash/api/v1/* block must NOT shadow this route."
            ),
            details={"status_code": r.status_code, "location": r.headers.get("location")},
        ),
        anon_log,
    )
    assert ok, f"unprotected /flash/api/firmware → {r.status_code}"


def test_1_3_anon_flash_api_v1(anon, anon_log, record):
    r = anon.get("/flash/api/v1/firmware", params={"sha256": "deadbeef" * 8})
    ok = r.status_code == 401
    record(
        Finding(
            id="1.3",
            title="/flash/api/v1/* is bearer-only, not Authelia-gated",
            severity="Medium",
            status="verified" if ok else "vulnerable",
            summary=(
                "The CI bearer surface must return 401 (no redirect), so the agent can detect "
                "missing creds without HTML."
            ),
            details={"status_code": r.status_code, "location": r.headers.get("location")},
        ),
        anon_log,
    )
    assert ok, f"expected 401, got {r.status_code}"


def test_1_4_anon_flash_api_firmware_post(anon, anon_log, record):
    r = anon.post("/flash/api/firmware", json={})
    ok = _expect_redirect_or_forbidden(r)
    record(
        Finding(
            id="1.4",
            title="POST /flash/api/firmware (operator) must require admin",
            severity="Critical",
            status="verified" if ok else "vulnerable",
            summary=(
                "Write must not reach FastAPI (a 422 response would mean the request "
                "bypassed Authelia)."
            ),
            details={"status_code": r.status_code},
        ),
        anon_log,
    )
    assert ok, f"unprotected POST → {r.status_code}"


def test_1_5_researcher_flash(researcher, researcher_log, record):
    r = researcher.get("/flash/")
    ok = r.status_code in (302, 403)
    record(
        Finding(
            id="1.5",
            title="Researcher must not access /flash/",
            severity="Critical",
            status="verified" if ok else "vulnerable",
            summary="Researchers are not admins; Authelia must refuse /flash/.",
            details={"status_code": r.status_code, "location": r.headers.get("location")},
        ),
        researcher_log,
    )
    assert ok, f"researcher reached /flash/ with {r.status_code}"


def test_1_6_researcher_flash_post(researcher, researcher_log, record, admin):
    body = {
        "name": "audit-probe",
        "description": "",
        "firmware": ":020000040000FA\n:00000001FF\n",
        "tags": [],
    }
    created_id = None
    try:
        r = researcher.post("/flash/api/firmware", json=body)
        ok = r.status_code in (302, 403)
        if r.status_code == 200:
            try:
                created_id = (r.json() or {}).get("id")
            except Exception:
                created_id = None
        record(
            Finding(
                id="1.6",
                title="Researcher must not POST firmware",
                severity="Critical",
                status="verified" if ok else "vulnerable",
                summary="Researchers cannot create firmware entries.",
                details={"status_code": r.status_code, "created_id": created_id},
            ),
            researcher_log,
        )
        assert ok, f"researcher created firmware with {r.status_code}"
    finally:
        if created_id:
            try:
                admin.delete(f"/flash/api/firmware/{created_id}")
            except Exception:
                pass


def test_1_7_researcher_grafana_jupyter(researcher, researcher_log, record):
    r1 = researcher.get("/grafana/")
    r2 = researcher.get("/jupyter/")
    ok = r1.status_code in (200, 301, 302) and r2.status_code in (200, 301, 302)
    record(
        Finding(
            id="1.7",
            title="Researcher reaches /grafana/ and /jupyter/",
            severity="Informational",
            status="informational" if ok else "vulnerable",
            summary="Positive test: researcher group is allowed through Authelia to both services.",
            details={"grafana_status": r1.status_code, "jupyter_status": r2.status_code},
        ),
        researcher_log,
    )
    assert ok, f"researcher blocked: grafana={r1.status_code}, jupyter={r2.status_code}"


def test_1_8_anon_jupyter_api(anon, anon_log, record):
    r = anon.get("/jupyter/api/contents/")
    ok = r.status_code == 302 and "/login" in (r.headers.get("location") or "")
    record(
        Finding(
            id="1.8",
            title="Anonymous /jupyter/api/* must redirect to /login",
            severity="High",
            status="verified" if ok else "vulnerable",
            summary="Jupyter API must not leak below the Authelia gate.",
            details={"status_code": r.status_code, "location": r.headers.get("location")},
        ),
        anon_log,
    )
    assert ok, f"jupyter API leak: {r.status_code} {r.headers.get('location')}"


def test_1_9_anon_grafana_datasources(anon, anon_log, record):
    r = anon.get("/grafana/api/datasources")
    ok = _expect_redirect_or_forbidden(r)
    record(
        Finding(
            id="1.9",
            title="Anonymous /grafana/api/datasources must require auth",
            severity="High",
            status="verified" if ok else "vulnerable",
            summary="Grafana admin API must be behind Authelia.",
            details={"status_code": r.status_code, "location": r.headers.get("location")},
        ),
        anon_log,
    )
    assert ok, f"unprotected Grafana API: {r.status_code}"


def test_1_10_grafana_health_public(anon, anon_log, record):
    r = anon.get("/grafana/api/health")
    ok = r.status_code == 200
    record(
        Finding(
            id="1.10",
            title="/grafana/api/health is public (documented exception)",
            severity="Informational",
            status="informational" if ok else "vulnerable",
            summary="Health check used by deploy.sh; must stay public.",
            details={"status_code": r.status_code},
        ),
        anon_log,
    )
    assert ok, f"health check not reachable: {r.status_code}"


@pytest.mark.parametrize("path", ["/FLASH/", "/Flash/api/v1/firmware", "/FLASH/api/firmware"])
def test_1_11_case_mutation(anon, anon_log, record, path):
    r = anon.get(path)
    ok = r.status_code == 404 or (
        r.status_code == 302 and "/login" in (r.headers.get("location") or "")
    )
    record(
        Finding(
            id=f"1.11({path})",
            title=f"Case-mutated path {path} must not match",
            severity="High",
            status="verified" if ok else "vulnerable",
            summary="Caddy must be case-sensitive on protected prefixes.",
            details={
                "path": path,
                "status_code": r.status_code,
                "location": r.headers.get("location"),
            },
        ),
        anon_log,
    )
    assert ok, f"{path} → {r.status_code}"


@pytest.mark.parametrize(
    "path", ["/flash/../grafana", "/grafana/%2e%2e/flash", "/flash/./api/firmware"]
)
def test_1_12_path_traversal(anon, anon_log, record, path):
    r = anon.get(path)
    ok = r.status_code in (302, 401, 403, 404)
    if r.status_code == 302:
        ok = "/login" in (r.headers.get("location") or "")
    record(
        Finding(
            id=f"1.12({path})",
            title=f"Path traversal {path} must not bypass auth",
            severity="High",
            status="verified" if ok else "vulnerable",
            summary="Normalised path must still hit the correct auth rule.",
            details={
                "path": path,
                "status_code": r.status_code,
                "location": r.headers.get("location"),
            },
        ),
        anon_log,
    )
    assert ok, f"{path} → {r.status_code}"


@pytest.mark.parametrize("path", ["/flash", "/flash/", "/flash?x=1"])
def test_1_13_trailing_slash(anon, anon_log, record, path):
    r = anon.get(path)
    ok = _expect_redirect_or_forbidden(r)
    record(
        Finding(
            id=f"1.13({path})",
            title=f"Trailing-slash variant {path} must require auth",
            severity="High",
            status="verified" if ok else "vulnerable",
            summary="All /flash* variants must hit the Authelia gate.",
            details={
                "path": path,
                "status_code": r.status_code,
                "location": r.headers.get("location"),
            },
        ),
        anon_log,
    )
    assert ok, f"{path} → {r.status_code}"


@pytest.mark.parametrize(
    "method,path", [("OPTIONS", "/flash/"), ("HEAD", "/flash/api/firmware")]
)
def test_1_14_method_confusion(anon, anon_log, record, method, path):
    r = anon.request(method, path)
    ok = _expect_redirect_or_forbidden(r) or r.status_code in (404, 405)
    record(
        Finding(
            id=f"1.14({method} {path})",
            title=f"{method} {path} must enforce same auth as GET",
            severity="High",
            status="verified" if ok else "vulnerable",
            summary="Non-GET verbs must not bypass forward_auth.",
            details={"method": method, "path": path, "status_code": r.status_code},
        ),
        anon_log,
    )
    assert ok, f"{method} {path} → {r.status_code}"


@pytest.mark.parametrize(
    "path,public_ok",
    [
        ("/auth/.well-known/openid-configuration", True),
        ("/auth/api/oidc/jwks.json", True),
        ("/auth/api/health", True),
        ("/auth/api/state", None),
        ("/auth/api/configuration", None),
        ("/auth/api/password-reset/identity/start", None),
    ],
)
def test_1_15_authelia_surface(anon, anon_log, record, path, public_ok):
    r = anon.get(path)
    body_excerpt = r.text[:400]
    if public_ok is True:
        ok = r.status_code == 200
        severity = "Informational"
        status = "informational" if ok else "vulnerable"
    else:
        ok = True
        severity = "Informational" if r.status_code in (200, 401, 403) else "Low"
        status = "informational"
    record(
        Finding(
            id=f"1.15({path})",
            title=f"Authelia surface {path}",
            severity=severity,
            status=status,
            summary=f"Exposed via /auth/* reverse_proxy. Status {r.status_code}.",
            details={
                "path": path,
                "status_code": r.status_code,
                "body_excerpt": body_excerpt[:200],
            },
        ),
        anon_log,
    )
    assert ok, f"{path} returned unexpected {r.status_code}"
