# Docs sidebar — manifest-driven nav

**Date:** 2026-05-22
**Status:** Spec (pre-plan)
**Touches:** `services/siteapp/`, `public_docs/`, `.github/workflows/pr-siteapp.yml`

## Problem

`build_nav()` in `services/siteapp/app/nav.py` walks `public_docs/` and emits the
sidebar by sorting directories alphabetically, then files alphabetically. The H1
of `<dir>/index.md` becomes the section label.

Two consequences hurt the reader experience:

- **Order is wrong by default.** `admin → operator → reference → researcher` is
  alphabetical, not narrative. The natural reading flow is
  `system-overview → researcher → operator → admin → reference`.
- **No way to override the sidebar label.** Today the section label is
  identical to the H1 of `index.md`. Editorial cases where the in-page heading
  ("Setting up your lab PC") differs from the sidebar entry ("Lab PC setup")
  have no escape hatch.

Section 1 picks an explicit, reviewable mechanism over filename conventions or
per-file frontmatter.

## Goals

1. Order of sidebar entries is editorially controlled, at every depth.
2. Sidebar labels can be overridden independently of in-page H1 titles.
3. Docs can be reachable by URL but omitted from the sidebar.
4. Drift between filesystem and manifest is caught in CI, not in production.
5. Top-level ordering becomes manifest-driven too — no hard-coded
   `Home → dirs → root files` rule.

## Non-goals

- External-link entries in the sidebar (Grafana, GitHub, etc.). Easy follow-up
  if a real use case appears; currently speculative.
- Per-file frontmatter as a secondary metadata channel. The manifest is the
  single source of truth.
- Search, doc-relative cross-section next/prev, sidebar collapse state changes.
  Out of scope for this spec.

## Design

### Manifest file

Each docs directory under `public_docs/` carries a `_nav.yaml` listing its
children in display order. List-of-records form, one entry per child:

```yaml
# public_docs/_nav.yaml — root
- name: system-overview
- name: technical-overview
- name: researcher
- name: operator
- name: admin
  title: "Administrator guide"
- name: reference
```

```yaml
# public_docs/researcher/_nav.yaml — section
- name: first-notebook
- name: advanced-topics
  hidden: true
```

**Schema** (per entry):

| Field    | Type | Required | Meaning                                              |
|----------|------|----------|------------------------------------------------------|
| `name`   | str  | yes      | Stem of a `.md` file OR a subdirectory name.         |
| `title`  | str  | no       | Sidebar label override. Defaults to H1 (see below).  |
| `hidden` | bool | no       | If `true`, the doc is reachable by URL but omitted from the sidebar. Defaults to `false`. |

Unknown fields fail validation (rule 6 below).

### Resolution rules

- `name: foo` resolves to `<dir>/foo.md` if present, otherwise `<dir>/foo/`
  (which must contain `index.md`). File wins over directory if both somehow
  exist.
- **`index` is implicit at every depth and never listed in a manifest.**
  - At the root, `index.md` becomes the "Home" sidebar entry, pinned to the top.
  - In a section, `index.md` is the section landing page — the section header
    IS the index, so listing it would render two sidebar entries for the same
    URL.
- **Translations (`*.ru.md`) are never listed.** They attach automatically via
  the existing `_read_titles` lookup; manifest does not carry translations.
- **Asset-only directories** (no descendant `.md` files anywhere in the
  subtree, e.g. `public_docs/icons/`) are ignored by the validator. No
  `_nav.yaml` required, no listing required.

### Title precedence

For the sidebar label:

1. `title:` field in `_nav.yaml` (if present).
2. H1 of the target file (`<name>.md` or `<name>/index.md`).
3. Stem fallback (`name` itself).

Russian sidebar titles still come from the `.ru.md` H1. The manifest does not
carry localized titles in this iteration — keeps the manifest small and the
escape hatch (English label only) is what's actually requested.

### Strict validation

The validator runs at two moments, both calling the same code:

1. **Siteapp startup**, inside `build_nav()`. Malformed `public_docs/` → siteapp
   fails to boot → e2e step in `pr-siteapp.yml` catches it against the
   just-built image. Production-grade safety net.
2. **`docs_lint` CLI**, run in `pr-siteapp.yml` before e2e. Same checks,
   friendlier multi-error output. Author-facing.

**Rules** (each rule, when violated, raises `DocsNavError`):

| # | Rule | Failure message shape |
|---|---|---|
| 1 | `_nav.yaml` exists for every directory that has at least one listable child — a non-index `.md` file or a docs subdirectory. A directory with only `index.md` (plus translations and assets) needs no manifest. | `MissingManifest: public_docs/researcher/_nav.yaml not found` |
| 2 | Every `name` in `_nav.yaml` resolves to `<name>.md` or `<name>/index.md`. | `UnknownEntry: researcher/_nav.yaml lists 'foo' but no foo.md or foo/index.md exists` |
| 3 | Every `.md` file (excluding `index.md` and `*.ru.md`) and every docs subdirectory present in the dir is referenced in `_nav.yaml`. | `UnlistedEntry: researcher/first-notebook.md exists but is not in _nav.yaml` |
| 4 | No duplicate `name` within one manifest. | `DuplicateEntry: 'admin' listed twice in _nav.yaml` |
| 5 | `hidden: true` entries still must resolve (rule 2 applies). | Same as rule 2. |
| 6 | Unknown keys in an entry. | `UnknownField: 'order' in researcher/_nav.yaml — schema is name/title/hidden` |

The validator collects **all** errors per directory before raising, so authors
fixing docs locally see the full list, not just the first.

### Implementation surface

| File | Change |
|---|---|
| `services/siteapp/app/nav.py` | Replace `_walk` with manifest-driven traversal. Extract validator + manifest reader into helpers. Raise `DocsNavError` on violations. |
| `services/siteapp/app/docs_lint.py` | **New.** CLI wrapper around the validator. `python -m app.docs_lint <docs_root>`. Exit 0 clean, 1 on errors. |
| `services/siteapp/pyproject.toml` | Add `PyYAML`. |
| `public_docs/_nav.yaml` | **New.** Root manifest. |
| `public_docs/{admin,operator,researcher,reference}/_nav.yaml` | **New.** Section manifests. |
| `services/siteapp/tests/test_nav.py` | Expand: manifest happy path, each rule's failure mode, `hidden`, title override, title precedence. |
| `services/siteapp/tests/e2e/test_docs_manifest.py` (new file or appended to existing) | One smoke test: corrupt `_nav.yaml` in mounted docs → container fails to come up. |
| `.github/workflows/pr-siteapp.yml` | Add `docs_lint` step before the e2e step, gated by the existing `dorny/paths-filter@v3` (`services/siteapp/**` or `public_docs/**`). |

### Migration order

The implementation plan splits into three commits, in order:

1. **Validator + manifest reader, behind a fallback.** Add the new code paths;
   when `_nav.yaml` is absent, fall back to the current alphabetic `_walk()`.
   Existing `public_docs/` keeps rendering unchanged. Unit tests cover both
   paths.
2. **Populate `_nav.yaml` files** under `public_docs/` (root + four sections).
   Verify locally that the new order matches the editorial intent. Site keeps
   rendering, now via the manifest path.
3. **Flip to strict.** Remove the fallback. Missing manifest = error. This is
   the breaking change, isolated in its own commit for easy revert.

## Test plan

Per CLAUDE.md's three-layer convention:

- **Unit** (`services/siteapp/tests/test_nav.py`): bulk of coverage. Synthetic
  temp `docs_root` fixtures, one test per validation rule, plus
  title-precedence, hidden behavior, root-ordering, and translation pairing.
- **Service e2e** (`services/siteapp/tests/e2e/`): one test that mounts a
  malformed `public_docs/` into the just-built container and asserts the
  container exits non-zero (uvicorn refuses to start because `build_nav()`
  raised).
- **Platform integration** (bats): no change. Cross-service wiring is not
  affected.

## Risks

- **YAML parser as a new dependency.** PyYAML is the obvious pick; widely used,
  small, no native code. Alternative `ruamel.yaml` is overkill for our schema.
- **Authors forgetting to update `_nav.yaml`.** This is the failure mode that
  kills the manifest approach. Mitigations: strict validation at startup
  (deploy-blocking), `docs_lint` step in CI (PR-blocking), and clear error
  messages naming the missing entry.
- **URL stability.** The manifest controls order, not URLs. Existing
  `/docs/admin/`, `/docs/researcher/first-notebook` etc. are unchanged.
