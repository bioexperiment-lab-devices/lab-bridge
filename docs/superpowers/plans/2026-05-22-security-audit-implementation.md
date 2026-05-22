# Security audit harness implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pytest-based audit harness that probes the lab-bridge platform boundary (Caddy, Authelia, siteapp, flasher), run it against preprod `https://111.88.145.138`, and emit a Markdown findings report.

**Architecture:** Self-contained uv project at `tests/security/`. `httpx.Client` sessions for admin/researcher/anonymous; raw `socket` for direct-port probes. Evidence captured via httpx event hooks and surfaced through pytest `user_properties` → a `pytest_terminal_summary` hook that writes Markdown.

**Tech Stack:** Python 3.13, pytest, httpx, uv. Spec: `docs/superpowers/specs/2026-05-22-security-audit-design.md`.

---

## Task 1: Bootstrap `tests/security/` uv project

**Files:**
- Create: `tests/security/pyproject.toml`
- Create: `tests/security/.python-version`
- Create: `tests/security/__init__.py`

- [ ] **Step 1: Create the `__init__.py`**

```python
```

- [ ] **Step 2: Create `.python-version`**

Content (single line, no trailing newline):

```
3.13
```

- [ ] **Step 3: Create `pyproject.toml`**

```toml
[project]
name = "lab-bridge-security-audit"
version = "0.1.0"
description = "Security audit harness for lab-bridge platform"
requires-python = ">=3.13"
dependencies = [
    "httpx>=0.27,<0.29",
    "pytest>=8.3,<9",
    "pytest-asyncio>=0.24,<0.25",
]

[tool.pytest.ini_options]
addopts = "-v --tb=short"
asyncio_mode = "auto"
markers = [
    "slow: opt-in tests with cooldowns or large uploads (requires --slow)",
    "audit_only: one-off audit case, not promoted to regression CI",
    "regression: candidate for promotion to CI regression suite",
]

[tool.ruff]
line-length = 100
target-version = "py313"
```

- [ ] **Step 4: Verify uv can resolve**

Run: `cd tests/security && uv sync`
Expected: `Resolved N packages`, no errors. Creates `uv.lock` and `.venv/`.

- [ ] **Step 5: Commit**

```bash
git add tests/security/__init__.py tests/security/.python-version tests/security/pyproject.toml tests/security/uv.lock
git commit -m "test(security): bootstrap audit harness project"
```

---

## Task 2: Build the HTTP client helpers (`clients.py`)

**Files:**
- Create: `tests/security/clients.py`

- [ ] **Step 1: Create `clients.py`**

```python
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
        # keep scheme, mask token
        return TOKEN_RE.sub(r"\1<redacted>", value) if "bearer" in value.lower() else "<redacted>"
    if n == "cookie":
        # keep names, mask values
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
    # Set-Cookie: name=value; Path=/; ...
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
```

- [ ] **Step 2: Smoke-check syntax**

Run: `cd tests/security && uv run python -c "import clients; print(clients.MAX_BODY)"`
Expected: `2048`

- [ ] **Step 3: Commit**

```bash
git add tests/security/clients.py
git commit -m "test(security): add httpx session helpers with redaction"
```

---

## Task 3: Build `conftest.py` — fixtures + report hook

**Files:**
- Create: `tests/security/conftest.py`

- [ ] **Step 1: Create `conftest.py`**

```python
"""Pytest fixtures, CLI args, and Markdown report hook for the audit."""

from __future__ import annotations

import os
import socket
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from clients import SessionLog, login, make_client

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT = REPO_ROOT / "docs" / "security" / "2026-05-22-audit-report.md"

SEVERITY_ORDER = ["Critical", "High", "Medium", "Low", "Informational"]


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--target-url", default="https://111.88.145.138")
    parser.addoption("--insecure", default="true")
    parser.addoption("--slow", action="store_true", default=False)
    parser.addoption("--report", default=str(DEFAULT_REPORT))


@pytest.fixture(scope="session")
def target_url(request: pytest.FixtureRequest) -> str:
    return request.config.getoption("--target-url").rstrip("/")


@pytest.fixture(scope="session")
def target_host(target_url: str) -> str:
    return httpx.URL(target_url).host


@pytest.fixture(scope="session")
def verify_tls(request: pytest.FixtureRequest) -> bool:
    val = str(request.config.getoption("--insecure")).lower()
    return val not in ("1", "true", "yes")


@pytest.fixture(scope="session")
def admin_creds() -> tuple[str, str]:
    user = os.environ.get("LDS_AUDIT_ADMIN_USER", "khamitovdr")
    pw = os.environ.get("LDS_AUDIT_ADMIN_PASS")
    if not pw:
        pytest.skip("LDS_AUDIT_ADMIN_PASS not set")
    return user, pw


@pytest.fixture(scope="session")
def researcher_creds() -> tuple[str, str]:
    user = os.environ.get("LDS_AUDIT_RES_USER", "test")
    pw = os.environ.get("LDS_AUDIT_RES_PASS")
    if not pw:
        pytest.skip("LDS_AUDIT_RES_PASS not set")
    return user, pw


@pytest.fixture(scope="session")
def anon_log() -> SessionLog:
    return SessionLog()


@pytest.fixture(scope="session")
def admin_log() -> SessionLog:
    return SessionLog()


@pytest.fixture(scope="session")
def researcher_log() -> SessionLog:
    return SessionLog()


@pytest.fixture(scope="session")
def anon(target_url: str, verify_tls: bool, anon_log: SessionLog):
    with make_client(target_url, verify=verify_tls, log=anon_log) as c:
        yield c


@pytest.fixture(scope="session")
def admin(target_url, verify_tls, admin_creds, admin_log):
    client, _info = login(
        target_url,
        username=admin_creds[0],
        password=admin_creds[1],
        verify=verify_tls,
        log=admin_log,
    )
    try:
        yield client
    finally:
        client.close()


@pytest.fixture(scope="session")
def researcher(target_url, verify_tls, researcher_creds, researcher_log):
    client, _info = login(
        target_url,
        username=researcher_creds[0],
        password=researcher_creds[1],
        verify=verify_tls,
        log=researcher_log,
    )
    try:
        yield client
    finally:
        client.close()


@pytest.fixture(scope="session")
def slow_enabled(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--slow"))


@dataclass
class Finding:
    id: str
    title: str
    severity: str
    status: str  # "vulnerable", "verified", "skipped", "informational"
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)


def record_finding(item: pytest.Item, finding: Finding, log: SessionLog | None = None) -> None:
    if log is not None:
        finding.evidence = [ex.to_dict() for ex in log.latest(5)]
    item.user_properties.append(("finding", finding))


@pytest.fixture
def record(request: pytest.FixtureRequest):
    """Yield a callable that attaches a Finding to the current test item."""

    def _record(finding: Finding, log: SessionLog | None = None) -> None:
        record_finding(request.node, finding, log)

    return _record


def _git_sha() -> str:
    head = REPO_ROOT / ".git" / "HEAD"
    if not head.is_file():
        return "unknown"
    ref = head.read_text().strip()
    if ref.startswith("ref: "):
        ref_path = REPO_ROOT / ".git" / ref[5:]
        if ref_path.is_file():
            return ref_path.read_text().strip()[:12]
    return ref[:12]


def _fmt_evidence(evidence: list[dict[str, Any]]) -> str:
    if not evidence:
        return "_(no recorded exchanges)_"
    out = []
    for ex in evidence:
        out.append(f"- `{ex['method']} {ex['url']}` → `{ex['status']}`")
        rh = ", ".join(f"{k}: {v}" for k, v in ex["request_headers"].items())
        out.append(f"  - req headers: {rh or '(none)'}")
        if ex["request_body"]:
            out.append(f"  - req body: `{_short(ex['request_body'])}`")
        resp_h = ", ".join(
            f"{k}: {v}" for k, v in ex["response_headers"].items() if k.lower() in
            ("location", "set-cookie", "content-type", "www-authenticate", "strict-transport-security")
        )
        if resp_h:
            out.append(f"  - resp headers: {resp_h}")
        if ex["response_body"]:
            out.append(f"  - resp body: `{_short(ex['response_body'])}`")
    return "\n".join(out)


def _short(s: str) -> str:
    s = s.replace("\n", " ").replace("`", "\\`")
    return s[:240] + ("…" if len(s) > 240 else "")


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:
    findings: list[tuple[str, Finding]] = []
    for report_list in terminalreporter.stats.values():
        for r in report_list:
            if not hasattr(r, "user_properties"):
                continue
            for name, value in r.user_properties:
                if name == "finding" and isinstance(value, Finding):
                    findings.append((r.nodeid, value))

    report_path = Path(config.getoption("--report")).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)

    by_severity: dict[str, list[tuple[str, Finding]]] = defaultdict(list)
    for nodeid, f in findings:
        if f.status in ("vulnerable", "informational"):
            by_severity[f.severity].append((nodeid, f))

    target_url = config.getoption("--target-url")
    insecure = config.getoption("--insecure")
    slow = config.getoption("--slow")
    now = datetime.now(UTC).isoformat(timespec="seconds")
    sha = _git_sha()

    lines: list[str] = []
    lines.append("# lab-bridge security audit report")
    lines.append("")
    lines.append(f"- Target: `{target_url}`")
    lines.append(f"- Run at: {now}")
    lines.append(f"- Git SHA: `{sha}`")
    lines.append(f"- TLS verification disabled: `{insecure}`")
    lines.append(f"- --slow enabled: `{slow}`")
    lines.append("")
    lines.append("## Executive summary")
    lines.append("")
    lines.append("| Severity | Count |")
    lines.append("|---|---|")
    for sev in SEVERITY_ORDER:
        lines.append(f"| {sev} | {len(by_severity.get(sev, []))} |")
    lines.append("")
    passed = [(n, f) for n, f in findings if f.status == "verified"]
    lines.append(f"Passed controls: {len(passed)}")
    lines.append("")

    for sev in SEVERITY_ORDER:
        bucket = by_severity.get(sev, [])
        if not bucket:
            continue
        lines.append(f"## {sev} findings")
        lines.append("")
        for nodeid, f in bucket:
            lines.append(f"### {f.id} — {f.title}")
            lines.append("")
            lines.append(f"- Severity: **{sev}**")
            lines.append(f"- Status: `{f.status}`")
            lines.append(f"- Test: `{nodeid}`")
            lines.append("")
            lines.append(f"{f.summary}")
            lines.append("")
            if f.details:
                lines.append("**Details:**")
                lines.append("")
                for k, v in f.details.items():
                    lines.append(f"- {k}: `{v}`")
                lines.append("")
            lines.append("**Evidence:**")
            lines.append("")
            lines.append(_fmt_evidence(f.evidence))
            lines.append("")

    lines.append("## Passed controls")
    lines.append("")
    lines.append("<details>")
    lines.append("<summary>Click to expand</summary>")
    lines.append("")
    for nodeid, f in passed:
        lines.append(f"- `{f.id}` — {f.title} (`{nodeid}`)")
    lines.append("")
    lines.append("</details>")
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    terminalreporter.write_line(f"audit report written → {report_path}")
```

- [ ] **Step 2: Smoke-check pytest collects the conftest**

Run: `cd tests/security && uv run pytest --collect-only -q`
Expected: `no tests ran` (no test files yet) but no import errors.

- [ ] **Step 3: Commit**

```bash
git add tests/security/conftest.py
git commit -m "test(security): conftest with session fixtures and report hook"
```

---

## Task 4: Class 1 — direct-path auth bypass (`test_01_routing.py`)

**Files:**
- Create: `tests/security/test_01_routing.py`

- [ ] **Step 1: Create the test file**

```python
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
            summary=(
                "/flash/ must redirect anonymous users to /login or return 403."
            ),
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
            summary="The CI bearer surface must return 401 (no redirect), so the agent can detect missing creds without HTML.",
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
            summary="Write must not reach FastAPI (a 422 response would mean the request bypassed Authelia).",
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
    body = {"name": "audit-probe", "description": "", "firmware": ":020000040000FA\n:00000001FF\n", "tags": []}
    created_id = None
    try:
        r = researcher.post("/flash/api/firmware", json=body)
        ok = r.status_code in (302, 403)
        if r.status_code == 200:
            created_id = (r.json() or {}).get("id")
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
    # Caddy is case-sensitive — these must 404 or be redirected, never reach a service unauth'd
    ok = r.status_code == 404 or (r.status_code == 302 and "/login" in (r.headers.get("location") or ""))
    record(
        Finding(
            id=f"1.11({path})",
            title=f"Case-mutated path {path} must not match",
            severity="High",
            status="verified" if ok else "vulnerable",
            summary="Caddy must be case-sensitive on protected prefixes.",
            details={"path": path, "status_code": r.status_code, "location": r.headers.get("location")},
        ),
        anon_log,
    )
    assert ok, f"{path} → {r.status_code}"


@pytest.mark.parametrize("path", ["/flash/../grafana", "/grafana/%2e%2e/flash", "/flash/./api/firmware"])
def test_1_12_path_traversal(anon, anon_log, record, path):
    r = anon.get(path)
    # After normalisation, whichever path resolves should still require auth or 404
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
            details={"path": path, "status_code": r.status_code, "location": r.headers.get("location")},
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
            details={"path": path, "status_code": r.status_code, "location": r.headers.get("location")},
        ),
        anon_log,
    )
    assert ok, f"{path} → {r.status_code}"


@pytest.mark.parametrize("method,path", [("OPTIONS", "/flash/"), ("HEAD", "/flash/api/firmware")])
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
        # Unknown / case-by-case: record what we got, no hard assertion
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
            details={"path": path, "status_code": r.status_code, "body_excerpt": body_excerpt[:200]},
        ),
        anon_log,
    )
    assert ok, f"{path} returned unexpected {r.status_code}"
```

- [ ] **Step 2: Confirm collection**

Run: `cd tests/security && uv run pytest test_01_routing.py --collect-only -q`
Expected: lists ~20 test items including parametrised cases. No import errors.

- [ ] **Step 3: Commit**

```bash
git add tests/security/test_01_routing.py
git commit -m "test(security): class 1 direct-path auth bypass probes"
```

---

## Task 5: Class 5 — disclosure (`test_02_disclosure.py`)

**Files:**
- Create: `tests/security/test_02_disclosure.py`

- [ ] **Step 1: Create the test file**

```python
"""Class 5 — information disclosure and headers."""

from __future__ import annotations

import ssl
import socket

import httpx
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
    # Don't fail on hardening misses — they're surfaced as findings.


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
    escaped_present = "&lt;script&gt;alert(1)&lt;/script&gt;" in body or "&#x3C;script" in body
    ok = (not raw_present) or escaped_present
    record(
        Finding(
            id="5.5",
            title="attempted_path reflected XSS in 404/403",
            severity="High",
            status="verified" if ok else "vulnerable",
            summary="The 403/404 template must HTML-escape the attempted path.",
            details={"status_code": r.status_code, "raw_present": raw_present, "escaped_present": escaped_present},
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
            details={"status_code": r.status_code, "body_has_rd": "evil.example" in r.text},
        ),
        anon_log,
    )


def test_5_7_tls_protocols(target_host, anon_log, record):
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


@pytest.mark.parametrize("path", ["/loki/api/v1/labels", "/prometheus/", "/api/datasources/proxy/1/"])
def test_5_8_internal_observability_not_exposed(anon, anon_log, record, path):
    r = anon.get(path)
    ok = r.status_code == 404 or (r.status_code == 302 and "/login" in (r.headers.get("location") or ""))
    record(
        Finding(
            id=f"5.8({path})",
            title=f"Internal observability path {path} must not be reachable",
            severity="High",
            status="verified" if ok else "vulnerable",
            summary="Loki/Prometheus must not be proxied directly by Caddy.",
            details={"path": path, "status_code": r.status_code, "location": r.headers.get("location")},
        ),
        anon_log,
    )
    assert ok, f"{path} → {r.status_code}"
```

- [ ] **Step 2: Smoke-check collection**

Run: `cd tests/security && uv run pytest test_02_disclosure.py --collect-only -q`
Expected: ~11 items listed, no import errors.

- [ ] **Step 3: Commit**

```bash
git add tests/security/test_02_disclosure.py
git commit -m "test(security): class 5 disclosure and security-headers probes"
```

---

## Task 6: Class 4 — header smuggling (`test_03_smuggling.py`)

**Files:**
- Create: `tests/security/test_03_smuggling.py`

- [ ] **Step 1: Create the test file**

```python
"""Class 4 — header / X-Forwarded smuggling."""

from __future__ import annotations

import httpx

from conftest import Finding


def test_4_1_xforwarded_user_injection(target_url, verify_tls, anon_log, record):
    # Send headers Authelia uses to communicate identity to upstream services.
    # Caddy must strip/overwrite them before they reach flasher/grafana/jupyter.
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
    assert ok, f"identity-header smuggling worked: {r.status_code} → {r.headers.get('location')}"


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
    grants_access = r.status_code == 200 and r.cookies.get("authelia_session")
    record(
        Finding(
            id="4.3",
            title="Manipulated X-Forwarded-Uri must not grant access on bad creds",
            severity="Critical",
            status="vulnerable" if grants_access else "verified",
            summary="Forwarded headers must never bypass credential verification.",
            details={"status_code": r.status_code, "set_cookie_present": bool(r.cookies.get("authelia_session"))},
        ),
        anon_log,
    )
    assert ok and not grants_access


def test_4_4_host_header_injection(target_url, verify_tls, anon_log, record):
    with httpx.Client(
        base_url=target_url, verify=verify_tls, timeout=10.0, follow_redirects=False
    ) as c:
        r = c.get("/", headers={"Host": "evil.example"})
    # Caddy with default_sni and TLS termination: behaviour varies. A 200 here
    # would mean the site responds to arbitrary hosts; preferred is 404/421.
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
```

- [ ] **Step 2: Smoke-check**

Run: `cd tests/security && uv run pytest test_03_smuggling.py --collect-only -q`
Expected: 4 items.

- [ ] **Step 3: Commit**

```bash
git add tests/security/test_03_smuggling.py
git commit -m "test(security): class 4 header-smuggling probes"
```

---

## Task 7: Class 7 — direct-port exposure (`test_04_direct_ports.py`)

**Files:**
- Create: `tests/security/test_04_direct_ports.py`

- [ ] **Step 1: Create the test file**

```python
"""Class 7 — direct-port exposure on the VPS.

Uses raw sockets to probe ports that should be docker-network-only. A
successful TCP connect to e.g. :2019 (Caddy admin) is a Critical finding.
"""

from __future__ import annotations

import socket

import httpx
import pytest

from conftest import Finding


INTERNAL_PORTS = [
    (2019, "Caddy admin API"),
    (9091, "Authelia"),
    (3000, "Grafana"),
    (8000, "siteapp/flasher uvicorn"),
    (8888, "JupyterLab"),
    (3100, "Loki"),
    (9090, "Prometheus"),
    (9100, "node-exporter"),
    (8080, "cadvisor"),
]


def _tcp_open(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@pytest.mark.parametrize("port,label", INTERNAL_PORTS)
def test_7_internal_port_closed(target_host, anon_log, record, port, label):
    open_ = _tcp_open(target_host, port)
    severity = "Critical" if port == 2019 else "High"
    record(
        Finding(
            id=f"7.{port}",
            title=f"Port {port} ({label}) must not be reachable from the internet",
            severity=severity,
            status="vulnerable" if open_ else "verified",
            summary=f"TCP connect to {target_host}:{port} from the auditor's network.",
            details={"port": port, "label": label, "open": open_},
        ),
    )
    assert not open_, f"{label} ({port}) reachable externally"


def test_7_2_caddy_admin_http(target_host, anon_log, record):
    open_ = _tcp_open(target_host, 2019)
    if not open_:
        record(
            Finding(
                id="7.2",
                title="Caddy admin /config/ unreachable",
                severity="Informational",
                status="informational",
                summary="Port 2019 closed; admin surface not exposed.",
                details={"port": 2019, "open": False},
            ),
        )
        return
    # If we got here, the port IS open — try the actual config endpoint
    with httpx.Client(timeout=5.0) as c:
        r = c.get(f"http://{target_host}:2019/config/")
    leaked = r.status_code == 200 and "apps" in r.text
    record(
        Finding(
            id="7.2",
            title="Caddy admin /config/ reachable",
            severity="Critical",
            status="vulnerable" if leaked else "informational",
            summary="Port 2019 open and /config/ responding — full Caddy reconfig surface exposed.",
            details={"status_code": r.status_code, "body_excerpt": r.text[:200]},
        ),
    )
    assert not leaked, "Caddy admin surface exposed"


def test_7_4_chisel_port_documented(target_host, anon_log, record):
    # Per compose/pins.yaml chisel_listen_port=7000
    open_ = _tcp_open(target_host, 7000)
    record(
        Finding(
            id="7.4",
            title="Chisel server port 7000",
            severity="Informational",
            status="informational",
            summary="Chisel port is intentionally public for SerialHop reverse tunnels.",
            details={"port": 7000, "open": open_},
        ),
    )
```

- [ ] **Step 2: Smoke-check**

Run: `cd tests/security && uv run pytest test_04_direct_ports.py --collect-only -q`
Expected: ~11 items.

- [ ] **Step 3: Commit**

```bash
git add tests/security/test_04_direct_ports.py
git commit -m "test(security): class 7 direct-port exposure probes"
```

---

## Task 8: Class 3 — bearer-token surfaces (`test_05_bearer.py`)

**Files:**
- Create: `tests/security/test_05_bearer.py`

- [ ] **Step 1: Create the test file**

```python
"""Class 3 — bearer-token surfaces."""

from __future__ import annotations

import io
import time

import httpx
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
        # Record the hardening note as a separate Informational finding
        record(
            Finding(
                id="3.2-hardening",
                title="Flasher bearer compare is not constant-time",
                severity="Medium",
                status="informational",
                summary=(
                    "services/flasher/app/routes/firmware.py:76 uses `!=` to compare the bearer "
                    "token; switching to `secrets.compare_digest` removes a theoretical timing "
                    "side-channel. The agent.py upload endpoint already uses compare_digest."
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
    # Without knowing real tokens, we just verify both endpoints reject the SAME
    # arbitrary token — confirms compare_digest catches the cross-endpoint reuse
    # case. (Real-token tests would need secrets; out of scope.)
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


@pytest.mark.slow
def test_3_6_oversize_agent_upload(anon, anon_log, record, slow_enabled):
    if not slow_enabled:
        pytest.skip("requires --slow")
    # Generate 101 MiB to exceed MAX_AGENT_BYTES (100 MiB)
    big = io.BytesIO(b"\x00" * (101 * 1024 * 1024))
    r = anon.post(
        "/api/agent/upload",
        data={"version": "0.0.1"},
        files={"binary": ("agent.exe", big, "application/octet-stream")},
        headers={"Authorization": "Bearer x"},  # wrong bearer → 401 before size check
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
```

- [ ] **Step 2: Smoke-check**

Run: `cd tests/security && uv run pytest test_05_bearer.py --collect-only -q`
Expected: 6 items.

- [ ] **Step 3: Commit**

```bash
git add tests/security/test_05_bearer.py
git commit -m "test(security): class 3 bearer-token probes"
```

---

## Task 9: Class 2 — session / cookie lifecycle (`test_06_session.py`)

**Files:**
- Create: `tests/security/test_06_session.py`

- [ ] **Step 1: Create the test file**

```python
"""Class 2 — session and cookie lifecycle."""

from __future__ import annotations

import re
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
    # Logout via GET
    client.get("/logout")
    client.close()
    # Replay raw cookie
    with make_client(target_url, verify=verify_tls, log=log, cookies={"authelia_session": session_cookie}) as replay:
        r = replay.get("/flash/")
    ok = r.status_code == 302 and "/login" in (r.headers.get("location") or "")
    record(
        Finding(
            id="2.1",
            title="Cookie replay after GET /logout must fail",
            severity="High",
            status="verified" if ok else "vulnerable",
            summary="Server-side session must be invalidated, not just client-side cookie cleared.",
            details={"replay_status": r.status_code, "replay_location": r.headers.get("location")},
        ),
        log,
    )
    assert ok, f"stale cookie still works: {r.status_code} → {r.headers.get('location')}"


def test_2_2_replay_after_post_logout(target_url, verify_tls, admin_creds, record):
    client, info, log = _login_short(target_url, verify_tls, admin_creds)
    session_cookie = info.get("authelia_session", "")
    client.post("/logout")
    client.close()
    with make_client(target_url, verify=verify_tls, log=log, cookies={"authelia_session": session_cookie}) as replay:
        r = replay.get("/flash/")
    ok = r.status_code == 302 and "/login" in (r.headers.get("location") or "")
    record(
        Finding(
            id="2.2",
            title="Cookie replay after POST /logout must fail",
            severity="High",
            status="verified" if ok else "vulnerable",
            summary="POST /logout must invalidate the server-side session.",
            details={"replay_status": r.status_code, "replay_location": r.headers.get("location")},
        ),
        log,
    )
    assert ok, f"stale cookie after POST logout still works: {r.status_code}"


def test_2_3_concurrent_sessions_independent(target_url, verify_tls, admin_creds, record):
    a_client, a_info, log = _login_short(target_url, verify_tls, admin_creds)
    b_client, b_info, _ = _login_short(target_url, verify_tls, admin_creds)
    a_cookie = a_info.get("authelia_session")
    b_cookie = b_info.get("authelia_session")
    distinct = a_cookie != b_cookie
    # Log out session A
    a_client.get("/logout")
    a_client.close()
    # B should still work
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
            details={"distinct_cookies": distinct, "b_status_after_a_logout": r.status_code},
        ),
        log,
    )
    assert ok


def test_2_4_login_cookie_attributes(target_url, verify_tls, admin_creds, record):
    _, info, log = _login_short(target_url, verify_tls, admin_creds)
    raw = info.get("raw_set_cookies", "")
    session_lines = [line for line in raw.splitlines() if line.startswith("authelia_session=")]
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
    with make_client(target_url, verify=verify_tls, log=anon_log, cookies={"authelia_session": "A" * 64}) as c:
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
    with make_client(target_url, verify=verify_tls, log=log, cookies={"authelia_session": truncated}) as c:
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
def test_2_8_inactivity_timeout(target_url, verify_tls, admin_creds, slow_enabled, record):
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


def test_2_9_cross_role_cookie(target_url, verify_tls, admin_creds, researcher_creds, record):
    a_client, a_info, a_log = _login_short(target_url, verify_tls, admin_creds)
    r_client, r_info, r_log = _login_short(target_url, verify_tls, researcher_creds)
    a_cookie = a_info.get("authelia_session")
    r_cookie = r_info.get("authelia_session")
    distinct = a_cookie != r_cookie

    # Admin should reach /flash/
    admin_on_flash = a_client.get("/flash/")
    # Researcher should NOT reach /flash/
    res_on_flash = r_client.get("/flash/")

    a_client.close()
    r_client.close()

    admin_ok = admin_on_flash.status_code in (200, 302) and not (
        admin_on_flash.status_code == 302 and "/login" in (admin_on_flash.headers.get("location") or "")
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
    # Set a pre-login bogus session cookie, then perform login; the issued
    # cookie value must differ from the bogus pre-login one.
    log = SessionLog()
    bogus = "fixation-probe-" + "A" * 32
    with make_client(target_url, verify=verify_tls, log=log, cookies={"authelia_session": bogus}) as c:
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
            summary="The cookie value after login must differ from any pre-login attacker-set value.",
            details={"pre_login": bogus[:8] + "...", "issued_prefix": issued[:8] + "..." if issued else ""},
        ),
        log,
    )
    assert ok


def test_2_11_csrf_firstfactor_origin(target_url, verify_tls, admin_creds, record):
    log = SessionLog()
    with httpx.Client(
        base_url=target_url, verify=verify_tls, timeout=10.0, follow_redirects=False,
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
    # Authelia 4.38 does not enforce Origin on /api/firstfactor itself (the
    # SPA does). SameSite=Lax on the cookie limits the cross-site impact.
    grants = r.status_code == 200 and r.cookies.get("authelia_session")
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
            details={"status_code": r.status_code, "set_cookie_present": bool(r.cookies.get("authelia_session"))},
        ),
        log,
    )


def test_2_12_get_logout_csrf(target_url, verify_tls, admin_creds, record):
    client, info, log = _login_short(target_url, verify_tls, admin_creds)
    r = client.get("/logout")
    client.close()
    logged_out = r.status_code in (200, 302)
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
```

- [ ] **Step 2: Smoke-check**

Run: `cd tests/security && uv run pytest test_06_session.py --collect-only -q`
Expected: 12 items.

- [ ] **Step 3: Commit**

```bash
git add tests/security/test_06_session.py
git commit -m "test(security): class 2 session and cookie lifecycle probes"
```

---

## Task 10: Class 6 — auth state edge cases (`test_07_state.py`)

**Files:**
- Create: `tests/security/test_07_state.py`

- [ ] **Step 1: Create the test file**

```python
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
    # Regulation kicks in after max_retries=3. We expect *something* to change
    # by attempt 4 or 5 — either a different status code or a delay.
    distinct = len(set(statuses)) > 1
    record(
        Finding(
            id="6.1",
            title="Brute-force regulation triggers within max_retries+2",
            severity="Informational",
            status="informational" if distinct else "vulnerable",
            summary="Authelia is configured with max_retries=3, ban_time=5m. After 3 wrongs, response should change.",
            details={"probe_user": probe_user, "statuses": statuses, "distinct_responses": distinct},
        ),
        anon_log,
    )
    # Do NOT assert — the same status code on 1st and 5th attempt is a *finding*,
    # not a test failure. Surfacing it in the report is enough.


def test_6_3_oidc_admin_handshake(target_url, verify_tls, admin_creds, record):
    log = SessionLog()
    client, info = login(
        target_url, username=admin_creds[0], password=admin_creds[1], verify=verify_tls, log=log
    )
    try:
        # Hit /grafana/ — Authelia redirects through OIDC, lands on Grafana.
        # Follow up to 5 hops manually.
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
            # Stay on the same host
            if loc.startswith("http"):
                u = httpx.URL(loc)
                if u.host != httpx.URL(target_url).host:
                    break
                next_url = u.path + ("?" + u.query.decode() if u.query else "")
            else:
                next_url = loc
        landed = statuses and statuses[-1] in (200, 302)
    finally:
        client.close()
    record(
        Finding(
            id="6.3",
            title="Admin completes OIDC handshake into Grafana",
            severity="Informational",
            status="informational" if landed else "vulnerable",
            summary="Authelia OIDC → Grafana should complete in ≤5 hops with a 200 or final auth cookie.",
            details={"statuses": statuses},
        ),
        log,
    )


def test_6_4_oidc_researcher_handshake(target_url, verify_tls, researcher_creds, record):
    log = SessionLog()
    client, info = login(
        target_url, username=researcher_creds[0], password=researcher_creds[1], verify=verify_tls, log=log
    )
    try:
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
                next_url = u.path + ("?" + u.query.decode() if u.query else "")
            else:
                next_url = loc
        landed = statuses and statuses[-1] in (200, 302)
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
```

- [ ] **Step 2: Smoke-check**

Run: `cd tests/security && uv run pytest test_07_state.py --collect-only -q`
Expected: 3 items.

- [ ] **Step 3: Commit**

```bash
git add tests/security/test_07_state.py
git commit -m "test(security): class 6 auth state edge cases"
```

---

## Task 11: Wrapper script `scripts/security_audit.sh`

**Files:**
- Create: `scripts/security_audit.sh`

- [ ] **Step 1: Create the script**

```bash
#!/usr/bin/env bash
# Run the security audit harness against a target URL.
#
# Usage:
#   LDS_AUDIT_ADMIN_PASS=... LDS_AUDIT_RES_PASS=... \
#     scripts/security_audit.sh [--target-url=https://...] [--slow]
#
# Outputs:
#   docs/security/<date>-audit-report.md
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT/tests/security"

if [[ -z "${LDS_AUDIT_ADMIN_PASS:-}" ]]; then
    echo "error: LDS_AUDIT_ADMIN_PASS not set" >&2
    exit 2
fi
if [[ -z "${LDS_AUDIT_RES_PASS:-}" ]]; then
    echo "error: LDS_AUDIT_RES_PASS not set" >&2
    exit 2
fi

uv sync >&2
exec uv run pytest "$@"
```

- [ ] **Step 2: Mark executable**

Run: `chmod +x scripts/security_audit.sh`

- [ ] **Step 3: Commit**

```bash
git add scripts/security_audit.sh
git commit -m "test(security): wrapper script for the audit harness"
```

---

## Task 12: README for `tests/security/`

**Files:**
- Create: `tests/security/README.md`

- [ ] **Step 1: Write the README**

```markdown
# lab-bridge security audit harness

Pytest-based harness probing the platform's auth/routing surface. See
`docs/superpowers/specs/2026-05-22-security-audit-design.md` for the design.

## Run

```bash
export LDS_AUDIT_ADMIN_PASS='...'
export LDS_AUDIT_RES_PASS='...'
scripts/security_audit.sh --target-url=https://111.88.145.138
```

Flags:

- `--target-url=URL` — target host (default `https://111.88.145.138`).
- `--insecure=true|false` — TLS verification (default `true` for preprod).
- `--slow` — opt into tests with cooldowns and large uploads.
- `--report=PATH` — Markdown report destination.

## What it tests

Seven classes, executed in `test_01_*`…`test_07_*` order. Class numbers in the
test IDs match the spec.

| File | Class | Focus |
|---|---|---|
| `test_01_routing.py` | 1 | Direct-path auth bypass |
| `test_02_disclosure.py` | 5 | Info disclosure and security headers |
| `test_03_smuggling.py` | 4 | Header / X-Forwarded smuggling |
| `test_04_direct_ports.py` | 7 | Direct VPS port exposure |
| `test_05_bearer.py` | 3 | Bearer-token surfaces |
| `test_06_session.py` | 2 | Login, logout, cookie hygiene, replay |
| `test_07_state.py` | 6 | Brute-force regulation, OIDC handshake |

## Interpreting findings

The report is at `docs/security/<date>-audit-report.md`. Findings carry:

- **Severity**: Critical / High / Medium / Low / Informational
- **Status**: `verified` (control works), `vulnerable` (suspected weakness),
  `informational` (recorded, no action), `skipped`.

A `vulnerable` row is the signal to investigate. The report includes
truncated, redacted request/response evidence for each non-passing finding.

## Promotion to CI

Cases worth running continuously get `@pytest.mark.regression`; one-off
audit cases stay decorated with `@pytest.mark.audit_only`. The eventual CI
cell will collect only the regression marker.
```

- [ ] **Step 2: Commit**

```bash
git add tests/security/README.md
git commit -m "docs(security): README for the audit harness"
```

---

## Task 13: Run the audit against preprod

**Files:**
- Create: `docs/security/2026-05-22-audit-report.md` (generated)

- [ ] **Step 1: Confirm credentials are exported**

```bash
export LDS_AUDIT_ADMIN_USER='khamitovdr'
export LDS_AUDIT_ADMIN_PASS='U$rKtI3N2M*5*Wg'
export LDS_AUDIT_RES_USER='test'
export LDS_AUDIT_RES_PASS='test_researcher'
```

(Run in the working shell; the script reads from environment.)

- [ ] **Step 2: Pre-flight sanity check — target reachable**

Run: `curl -ksSI https://111.88.145.138/ | head -1`
Expected: `HTTP/2 200` or `HTTP/1.1 200`.

- [ ] **Step 3: Run the audit**

Run: `scripts/security_audit.sh --target-url=https://111.88.145.138`
Expected: pytest output with PASS/FAIL per test; `audit report written → …` final line.

If multiple FAILs reflect real findings, that is the expected outcome — the
harness is doing its job. Only an *import error* or *fixture error* would
indicate a harness bug to fix.

- [ ] **Step 4: Review the report**

Open `docs/security/2026-05-22-audit-report.md`. Cross-check counts against
the spec's pre-test predictions (logout cookie Secure, bearer compare_digest,
HSTS, GET logout CSRF). If any *unexpected* Critical/High shows up, capture a
note in the report's executive summary.

- [ ] **Step 5: Commit the report**

```bash
git add docs/security/2026-05-22-audit-report.md
git commit -m "docs(security): initial audit report against preprod"
```

---

## Task 14: Summarise findings for the user

- [ ] **Step 1: Write a short summary message**

Summarise (no file write) for the user:

- Total findings by severity
- Top 3 by severity
- Predictions confirmed vs falsified
- Recommended next step (e.g. open a PR for the `Secure` flag fix, switch
  bearer compare to `compare_digest`, etc.)

---

## Self-review notes

Checked the plan against the spec:

- All seven classes have a task with concrete code, not just headings.
- Each task ends in a commit step.
- File names match the spec's `test_NN_…` convention.
- `Finding` dataclass is defined in `conftest.py` and imported consistently.
- Session fixtures, log fixtures, and the `record` callable are wired through
  uniformly.
- The `--slow` opt-in path is honoured in 3.6 and 2.8.
- Direct-port probes do not require credentials and run independently of
  Authelia state.
- Cleanup logic is included in test 1.6 (the only write that could plausibly
  succeed if a vuln exists).
- No TODOs, no "fill this in", no "similar to task N" placeholders.
