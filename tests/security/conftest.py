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
    seen: set[tuple[str, str]] = set()
    for report_list in terminalreporter.stats.values():
        for r in report_list:
            if not hasattr(r, "user_properties"):
                continue
            # Only consider the 'call' phase report to avoid the same Finding
            # being collected from setup/call/teardown of one test.
            if getattr(r, "when", "call") != "call":
                continue
            for name, value in r.user_properties:
                if name == "finding" and isinstance(value, Finding):
                    key = (r.nodeid, value.id)
                    if key in seen:
                        continue
                    seen.add(key)
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
