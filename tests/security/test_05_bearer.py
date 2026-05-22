"""Class 3 — bearer-token surfaces."""

from __future__ import annotations

import io

import pytest

from conftest import Finding


VALID_FW = ":020000040000FA\n:00000001FF\n"


def test_3_1_flasher_bearer_missing(anon, anon_log, record):
    r = anon.post("/flash/api/v1/firmware", json={"name": "x", "firmware": VALID_FW})
    ok = r.status_code == 401
    record(
        Finding(
            id="3.1",
            title="/flash/api/v1/firmware without bearer must 401",
            severity="High",
            status="verified" if ok else "vulnerable",
            summary="CI upload endpoint must refuse anonymous POSTs.",
            details={"status_code": r.status_code},
        ),
        anon_log,
    )
    assert ok, f"missing-bearer not rejected: {r.status_code}"


def test_3_2_flasher_bearer_wrong(anon, anon_log, record):
    r = anon.post(
        "/flash/api/v1/firmware",
        json={"name": "x", "firmware": VALID_FW},
        headers={"Authorization": "Bearer aaaaaaaa-bogus-token-aaaaaaaa"},
    )
    ok = r.status_code == 401
    record(
        Finding(
            id="3.2",
            title="/flash/api/v1/firmware with wrong bearer must 401",
            severity="High",
            status="verified" if ok else "vulnerable",
            summary=(
                "Note: flasher's _require_bearer uses '!=' (not secrets.compare_digest); "
                "track as Medium hardening even when status is correct."
            ),
            details={"status_code": r.status_code, "constant_time_compare": False},
        ),
        anon_log,
    )
    if ok:
        record(
            Finding(
                id="3.2-hardening",
                title="Flasher bearer compare is not constant-time",
                severity="Medium",
                status="informational",
                summary=(
                    "services/flasher/app/routes/firmware.py:76 uses `!=` to compare the "
                    "bearer token; switching to `secrets.compare_digest` removes a "
                    "theoretical timing side-channel. The agent.py upload endpoint already "
                    "uses compare_digest."
                ),
                details={"file": "services/flasher/app/routes/firmware.py:76"},
            ),
        )
    assert ok, f"wrong-bearer not rejected: {r.status_code}"


def test_3_3_agent_upload_no_auth(anon, anon_log, record):
    r = anon.post(
        "/api/agent/upload",
        data={"version": "0.0.1"},
        files={"binary": ("agent.exe", io.BytesIO(b"PE\x00\x00"), "application/octet-stream")},
    )
    ok = r.status_code == 401
    record(
        Finding(
            id="3.3",
            title="POST /api/agent/upload without auth must 401",
            severity="Critical",
            status="verified" if ok else "vulnerable",
            summary="Unauthenticated agent.exe upload would let attackers ship malware as SerialHop.",
            details={"status_code": r.status_code},
        ),
        anon_log,
    )
    assert ok


def test_3_4_agent_upload_wrong_bearer(anon, anon_log, record):
    r = anon.post(
        "/api/agent/upload",
        data={"version": "0.0.1"},
        files={"binary": ("agent.exe", io.BytesIO(b"PE\x00\x00"), "application/octet-stream")},
        headers={"Authorization": "Bearer aaaaaaaa-bogus-token-aaaaaaaa"},
    )
    ok = r.status_code == 401
    record(
        Finding(
            id="3.4",
            title="POST /api/agent/upload with wrong bearer must 401",
            severity="Critical",
            status="verified" if ok else "vulnerable",
            summary="Wrong-bearer must not slip through compare_digest.",
            details={"status_code": r.status_code},
        ),
        anon_log,
    )
    assert ok


def test_3_5_token_separation(anon, anon_log, record):
    bogus = "Bearer xx-cross-endpoint-probe-xx"
    r1 = anon.post(
        "/flash/api/v1/firmware",
        json={"name": "x", "firmware": VALID_FW},
        headers={"Authorization": bogus},
    )
    r2 = anon.post(
        "/api/agent/upload",
        data={"version": "0.0.1"},
        files={"binary": ("agent.exe", io.BytesIO(b"PE\x00\x00"), "application/octet-stream")},
        headers={"Authorization": bogus},
    )
    ok = r1.status_code == 401 and r2.status_code == 401
    record(
        Finding(
            id="3.5",
            title="Tokens are not interchangeable across endpoints",
            severity="Informational",
            status="informational" if ok else "vulnerable",
            summary="Confirms a single bogus value is rejected on both endpoints.",
            details={"flash_status": r1.status_code, "agent_status": r2.status_code},
        ),
        anon_log,
    )
    assert ok


@pytest.mark.regression
def test_3_7_bearer_validation_order(anon, anon_log, record):
    """Bearer endpoints should check auth BEFORE schema validation.

    Hitting /flash/api/v1/firmware as GET with no sha256 query: if the bearer
    check runs first, we expect 401. If pydantic validation runs first, we get
    422 (exposing the schema to unauthenticated probes).
    """
    r = anon.get("/flash/api/v1/firmware")  # no sha256 param, no Authorization
    record(
        Finding(
            id="3.7",
            title="Bearer check ordering on /flash/api/v1/firmware",
            severity="Low",
            status="verified" if r.status_code == 401 else "vulnerable",
            summary=(
                "If the endpoint returns 422 (validation error) to an unauthenticated "
                "request missing the sha256 query, the schema is enumerable without "
                "credentials. Bearer enforcement should precede pydantic validation."
            ),
            details={"status_code": r.status_code, "body_excerpt": r.text[:200]},
        ),
        anon_log,
    )


@pytest.mark.slow
def test_3_6_oversize_agent_upload(anon, anon_log, record, slow_enabled):
    if not slow_enabled:
        pytest.skip("requires --slow")
    big = io.BytesIO(b"\x00" * (101 * 1024 * 1024))
    r = anon.post(
        "/api/agent/upload",
        data={"version": "0.0.1"},
        files={"binary": ("agent.exe", big, "application/octet-stream")},
        headers={"Authorization": "Bearer x"},
    )
    record(
        Finding(
            id="3.6",
            title="Oversize agent upload handled",
            severity="Informational",
            status="informational",
            summary=(
                "Probe sends 101 MiB. With a wrong bearer we should see 401 before any "
                "size check; with a valid bearer (not available here) we would expect 413."
            ),
            details={"status_code": r.status_code},
        ),
        anon_log,
    )
