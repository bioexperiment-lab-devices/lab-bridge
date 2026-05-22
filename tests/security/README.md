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
