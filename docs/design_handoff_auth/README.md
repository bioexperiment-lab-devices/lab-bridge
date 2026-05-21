# Handoff: SerialHop / lab-bridge — Auth UI surfaces

## Overview

This bundle contains the design references for **auth-related UI** in lab-bridge: the platform navbar (which carries login state), the sign-in page, error pages users see when they hit something they aren't allowed to, and the sign-out confirmation dialog.

Use these as the source of truth for styling new auth-related surfaces (e.g. password change, session expired, MFA setup) so they match the rest of the platform.

## About the design files

The `.jsx` and `.css` files here are **design references** authored as an in-canvas prototype. They are not meant to be dropped into the production codebase verbatim — recreate them in your codebase's existing environment (React, etc.), following your established patterns for routing, forms, i18n, accessibility, and state.

Open `preview.html` in a browser to see all surfaces rendered side-by-side.

## Fidelity

**High-fidelity.** Final colors, typography, spacing, copy, and component anatomy. Hex values, font sizes, border radii, etc. are intentional — match them. Where you see two-language copy (EN / RU), the production app uses the same i18n structure.

## Design tokens

The styling depends on a small set of CSS custom properties defined in `auth.css` under `:root` (light) and `[data-theme="dark"]`. They are shared with the rest of the lab-bridge surfaces. Key ones:

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg-page` | `#ECE9E0` | `#1B1A17` | Page background outside the surface card |
| `--surface` | `#FFFFFF` | `#232220` | Cards, inputs, modals |
| `--surface-sunken` | `#F8F6F0` | `#1D1C19` | Meta blocks, sunken panels |
| `--surface-strip` | `#FAF8F3` | `#1F1E1B` | Card heads/feet, secondary strips |
| `--surface-rail` | `#F3F0E6` | `#1E1D1A` | The side rail background |
| `--border` | `#E2DED2` | `#34322D` | Hairline borders |
| `--border-strong` | `#C8C3B5` | `#4A4740` | Card outlines, primary borders |
| `--border-input` | `#C3BFB2` | `#4A4740` | Form inputs |
| `--text` | `#1A1916` | `#F0EDE3` | Primary text |
| `--text-secondary` | `#514E47` | `#B8B3A4` | Secondary text |
| `--text-muted` | `#8A8678` | `#7E7A6E` | Hints, captions, mono labels |
| `--text-inverse` | `#FAF8F3` | `#1A1916` | Text on accent buttons |
| `--accent` | `#1F3A8A` | `#BCCBF2` | Primary CTAs, active state, focus ring |
| `--accent-hover` | `#182E6F` | `#DBE3F8` | Hover for primary CTAs |
| `--accent-soft` | `#E7ECF6` | `#2A3257` | Subtle accent fill (Sign-in btn, focus ring, role pills) |
| `--accent-border` | `#B8C2DC` | `#4A5587` | Subtle accent border |
| `--danger` | `#B23A2A` | `#E58879` | Destructive (Sign out btn, error banner) |
| `--danger-soft` / `--danger-border` | `#F8E5E0` / `#ECC5BC` | `#34211D` / `#6A3D34` | Error banner bg/border |
| `--warning` | `#A37200` | `#E3C067` | 403 lock badge |
| `--warning-soft` / `--warning-border` | `#F5EAC8` / `#E2D096` | `#2F2715` / `#5E4C20` | 403 lock badge bg/border |
| `--success` | `#2F7D3F` | `#7CC18A` | Live-session indicator on avatar |

### Type

- **UI:** IBM Plex Sans (weights 400, 500, 600, 700)
- **Mono / labels / kbd:** IBM Plex Mono (weights 400, 500, 600)
- Base body: 13px / 1.45, antialiased
- Form field input: 14px
- Section titles in cards: 15–16px
- Page titles (Sign-in / 403 / 404): 20–22px, weight 600, `letter-spacing: -0.012em` to `-0.014em`
- Mono labels (form field labels, eyebrows): 10.5px, weight 600, uppercase, `letter-spacing: 0.12em`, color `--text-muted`

### Spacing & shape

- Border radius: **3px** (inputs / small chips), **5px** (buttons, cards in the rail), **6px** (cards), **8px** (top-level surface cards)
- Card padding: **28px 30px** (sign-in, error pages), **16px / 18–20px** (modal head / body)
- Input height: **38px**; button height: **34px** (modal), **38–40px** (page primary), **32px** (rail buttons)
- Hairlines are 1px borders in `--border` or `--border-strong`. Avoid heavy shadows — the system uses very subtle `--shadow-card` and `--shadow-overlay` only on cards/modals.

### Iconography

Inline monoline SVGs, viewBox `0 0 14 14` to `0 0 24 24` (page-level icons are 18–22px square). `stroke="currentColor"`, `stroke-width: 1.4–1.6`. Never use emoji.

## Surfaces

### 1. Navbar — login state lives here

**File:** `navbar.jsx`, CSS classes `.lb-rail*`, `.lb-bookmark*`.

Side rail on the left of every lab-bridge page. The **user-identity block** sits at the top of `.lb-rail__bottom` (above theme toggle + collapse).

Three rail-bottom utility buttons share the `.lb-rail__btn` shape but have **different visual weight**:

| Button | Treatment | Intent |
|---|---|---|
| **Sign in** (signed-out only) | `bg: var(--accent-soft)`, border `var(--accent-border)`, text+icon `var(--accent)` | Light-accent CTA — visible action, not a heavy promo button |
| **Theme toggle** | `bg: var(--surface)`, border `var(--border)`, text `var(--text-secondary)`, icon `var(--text-muted)` | Neutral utility |
| **Collapse** | `bg: transparent`, no border, text `var(--text-muted)`, 26px tall | Recessive — sits "below" the others |

**Signed-in user block** (`.lb-rail__user`):
- Circular `.lb-rail__avatar` (26px, accent fill, mono initials uppercase) — with a **live-session dot** in `--success` at its bottom-right
- **Name only** (no role line on the rail — that lives elsewhere)
- Whole row is a button; opens a user menu (build menu separately, not in this bundle)

**Bookmark mode** (`.lb-bookmark`, `.lb-bookmark-overlay`) is for when lab-bridge nav overlays third-party apps (JupyterLab, Grafana) where it can't take chrome space. Same auth states inside the overlay.

**Collapsed rail** hides labels — auth block shrinks to just the avatar (with status dot) or just the key icon button.

### 2. Sign-in page

**File:** `login.jsx`, CSS section `Sign-in page` in `auth.css`.

Route: `/sign-in`. Two inputs only — **username** + **password** (with show/hide eye toggle) — plus a "Keep me signed in for 90 days" checkbox.

**No sign-up.** Credentials are issued by the server administrator. Don't add "forgot password" or "create account" links.

Rail stays on the left (collapsed, signed-out state). Form is centered in the rest of the viewport, max-width 420px.

States:
- **Default** — submit disabled until both fields filled
- **Loading** — submit shows a CSS spinner (`.lb-login__spinner`) + "Signing in…"
- **Error** — `.lb-login__error` red-left-border banner above the form

### 3. Access denied (403)

**File:** `forbidden.jsx`, CSS section `Access denied (403) page` in `auth.css`.

Shown when an **authenticated** user hits a path their role doesn't grant. The rail stays — this is **not** a logout. Layout:

- Small mono eyebrow: `Error 403 · Forbidden`
- Card with **icon-on-left + title-on-right** header row (`.lb-forbidden__head`). The icon is a lock in warning-soft fill.
- Body paragraph
- Meta block (`.lb-forbidden__meta`) showing only **Attempted path** (mono code chip)
- Single **Back** button calling `history.back()`

### 4. Page not found (404)

**File:** `not-found.jsx`. Same shell as 403, but:
- Eyebrow: `Error 404 · Not found`
- Icon: magnifying glass in **neutral surface-sunken** treatment (`.lb-forbidden__lock--404`) instead of warning amber. 404 is informational, not restrictive.

### 5. Sign-out confirmation dialog

**File:** `signout-dialog.jsx`, CSS section `Modal` in `auth.css`.

Centered modal triggered when the user picks "Sign out" from the rail user menu. Anatomy:
- Header: red logout icon (in `--danger-soft` badge), "Sign out?" title, close X
- Body: short warning ("Open sessions to JupyterLab, Grafana, and Flasher will end."), user card showing avatar + name (no role)
- Footer: neutral Cancel + red Sign out button

Backdrop is `rgba(26, 25, 22, 0.45)` with a 2px blur; clicking it cancels. Card animates in with a 160ms scale+fade (`@keyframes lb-modal-in`).

This modal pattern (`.lb-modal*` classes) is **reusable** for any destructive-confirmation dialog — swap header icon color, title, body, and the danger button label.

## Interaction & state

| Surface | State needed |
|---|---|
| Rail | `user: { name, role, initials } \| null` (provided by `LBAuthContext` in this bundle) |
| Login | `username`, `password`, `showPassword`, `rememberMe`, `loading`, `error` |
| 403 | `attemptedPath` (string from router) |
| 404 | `attemptedPath` (string from router) |
| Sign-out modal | `open` boolean; calls `onCancel` / `onConfirm` |

- All form submits should call `e.preventDefault()` and dispatch through your auth client.
- Submit button must be disabled while `loading === true` and when either field is empty.
- "Keep me signed in" controls cookie/token lifetime (90 days on the device); semantics defined server-side.
- The user-menu trigger and menu itself are out of scope for this bundle — the rail's `.lb-rail__user` button already has hover state; build the popover separately following the same surface/border/shadow tokens.

## Accessibility notes

- Lock icons are `aria-hidden="true"` — meaningful copy is always in text.
- Modal sets `role="dialog"`, `aria-modal="true"`, `aria-labelledby="…"`. Trap focus inside the card and return focus to the trigger on close (the prototype doesn't do this — your codebase should).
- Inputs use `autoComplete="username" / "current-password"` so password managers work.
- The password reveal button is a `<button type="button">` with `aria-label` + `aria-pressed`.
- The checkbox is visually hidden but focusable; the visible `.lb-check__box` shows focus ring via `:focus-visible` on the input.
- The submit button announces loading state via text content; the spinner is `aria-hidden`. Consider an `aria-live` region for error messages.

## i18n

All surfaces ship EN + RU copy in module-level `*_STRINGS` objects. Lift these into your i18n system; don't hardcode the strings inline when recreating.

## Files in this bundle

- `auth.css` — all CSS needed by these surfaces (incl. design tokens + dark theme). Drop it into your global stylesheet or split by component as fits your codebase.
- `navbar.jsx` — `LBBrowser`, `LBBrandMark`, `LBRail`, `LBRailUser`, `LBBookmarkTab`, `LBBookmarkOverlay`, `LBAuthContext`, `NAV_ITEMS`, `Icons`.
- `login.jsx` — `LBLogin`, `LoginIcons`, `LOGIN_STRINGS`.
- `forbidden.jsx` — `LBForbidden`, `FORBIDDEN_STRINGS`.
- `not-found.jsx` — `LBNotFound`, `NOT_FOUND_STRINGS`.
- `signout-dialog.jsx` — `LBSignOutDialog`, `SIGNOUT_STRINGS`.
- `preview.html` — self-contained runnable preview. Open in a browser; toggle dark mode via the button at top-right.
