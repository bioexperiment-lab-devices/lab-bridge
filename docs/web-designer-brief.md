# lab-bridge — Web Designer Brief

This document describes **what** the platform is, **how people use it**, and **every UI surface** the designer will own. Current visual styling is intentionally omitted — the designer is expected to design everything from scratch. Only structure, content, and behavior are specified.

---

## 1. What the platform is

**lab-bridge** is a self-hosted web portal for a research/bioinformatics lab. It is the single front door to every shared lab resource:

- **Shared analysis environment** — a multi-user JupyterLab where lab members write and run notebooks.
- **Lab instrument access** — physical lab devices (microscopes, sequencers, controllers, etc.) sit on a private network inside the lab. lab-bridge bridges them out to the notebook environment over secure reverse tunnels, so a notebook can talk to a device that isn't on the public internet.
- **Firmware flasher** — a web UI that server administrators use to (re-)flash firmware onto lab devices remotely.
- **Monitoring dashboards** — Grafana dashboards that show device health, log volume, errors, and connection status.
- **Public documentation** — onboarding and operating instructions for all users (bilingual EN/RU).
- **Agent download** — a small program ("SerialHop") that a lab operator installs on the lab PC connected to lab instruments. The agent opens a reverse tunnel back to lab-bridge so the devices become reachable from the notebook environment. Windows is shipping today; Linux and Raspberry Pi support is planned.

A single host (a VPS on the public internet) runs everything behind one domain. The whole platform is reached at `https://<vps-host>/`.

### Who uses it

Three distinct personas, each with a clearly different journey through the platform:

1. **Lab member (researcher)** — runs experiments and analyzes results. Lives almost entirely inside JupyterLab.
2. **Lab operator / device owner** — runs a specific lab site (one physical lab with its PC and instruments). Installs and maintains the SerialHop agent on the lab PC; keeps the lab's instruments connected and healthy.
3. **Server administrator** — operates the lab-bridge platform itself. Provisions SerialHop accounts for lab operators, pushes firmware updates to devices remotely, watches the platform's system health.

Authentication is per-service: JupyterLab and Grafana have their own logins, the Flasher is admin-gated. The docs and download pages are public. SerialHop agents authenticate to the server with credentials issued by the server administrator (created out-of-band via CLI, then delivered to the lab operator).

---

## 2. Main user flows

The three personas above each have a distinct flow through the platform. A cross-cutting concern — **reading docs in Russian** — is described at the end (§2.4).

### 2.1 Lab member (researcher)

The lab member is the heaviest day-to-day user but interacts with the **least** lab-bridge-owned UI. They mostly live inside JupyterLab.

1. Open JupyterLab directly (bookmarked URL, or via the platform navbar's **JupyterLab** item).
2. Log in (shared JupyterLab password).
3. Inside notebooks, address lab equipment **by its lab client name** (e.g. `microscope-1`) — this is the same name the server administrator assigned when provisioning the lab. The notebook talks to the device over the chisel reverse tunnel that the lab operator's SerialHop agent maintains.
4. Set up experiments, run them, analyze results — all inside JupyterLab.
5. Occasionally surface back to lab-bridge via the navbar's bookmark tab (e.g. to read a doc or check Grafana). Inside JupyterLab the platform navbar appears only as a small corner tab that does **not** take space from the notebook UI; hovering expands it, leaving collapses it (see §3.2).

**Design implication:** the lab member rarely sees the platform's own pages. The navbar bookmark tab is their primary touchpoint with lab-bridge — it must be unobtrusive but reliably discoverable.

### 2.2 Lab operator / device owner

The lab operator owns the *physical* side of one lab. Their flow is front-loaded (a one-time setup) and then ongoing maintenance.

**One-time setup:**

1. Open lab-bridge → click **Download Agent** in the platform navbar.
2. Download the SerialHop installer for their platform (Windows today; Linux and Raspberry Pi planned — see §5). For Windows the download page walks them through the "browser/Windows may try to block this unsigned binary" hurdles.
3. Install SerialHop on the lab's PC (the machine physically connected to the instruments).
4. Enter the **username + password** issued by the server administrator (delivered out-of-band — email, chat, etc.). These authenticate this specific lab's SerialHop instance against the lab-bridge server.
5. Fill in the rest of the local configuration (instrument names, COM ports, etc.) — done on the lab PC itself, not in lab-bridge.

**Ongoing maintenance:**

6. Keep the SerialHop service running and the connected lab devices healthy.
7. Use **Grafana** (via the platform navbar) to inspect their lab's SerialHop agent logs — verify the agent is connected, see error trends, diagnose flaky devices.

**Design implication:** the download page is *the* single most important lab-bridge-owned page for this persona. It must be confidence-inspiring (an unsigned `.exe` is intrinsically scary), make the version + integrity information unmissable, and walk the user past the browser / SmartScreen friction. The lab operator should also be able to easily find out where to look in Grafana — likely via a docs page that the download page or navbar links to.

### 2.3 Server administrator

The server admin operates the whole platform. Most of their work is **not** in lab-bridge's web UI — account provisioning, deploys, and ops are CLI-driven from their laptop. But they do have web-facing flows:

1. **Create and manage SerialHop accounts** — assign a lab a client name (`microscope-1`, etc.) and credentials. Done via CLI on the operator laptop (`task secrets:add-client …`), then the credentials are sent to the lab operator out-of-band. *No web UI for this today.*
2. **Push firmware to lab devices remotely** — open the **Flasher** in the platform navbar, authenticate (admin password), and use it to push a new firmware build to a specific device. This is how a server admin remotely supports a lab.
3. **Watch system logs** — open **Grafana** to monitor platform-wide health: device connectivity, log volume per client, errors, current agent versions in the field.
4. Read internal operational docs.

**Design implication:** the server admin will mostly bypass the lab-bridge home/docs surface entirely once they're up and running — but they live in the navbar (Flasher + Grafana are their two daily web destinations). The navbar's bookmark-tab behavior on Grafana is especially important for them, because Grafana is full-viewport.

### 2.4 Cross-cutting: reading the platform in Russian

Some users (any of the three personas) are Russian-speaking. EN is the default; the user can switch to RU via a language toggle. The toggle is surfaced on the **Home page (§6) and on translated Docs pages (§4.4)** — *not* in the navbar, and *not* on the Download page. The chosen language is stored in a 1-year cookie and applied platform-wide: every page with Russian content (Home, translated docs, the Download page's bilingual browser-block explainer) renders in the cookie-selected language. Pages with no Russian translation render in English regardless.

---

> **Note for designer — explicit scope:** JupyterLab and Grafana are **out of scope for this design entirely**. Do not design, restyle, or theme their internal UIs in any way — they are third-party applications with their own UIs and themes, and we are not touching them. The **only** thing you produce that lives over those pages is the navbar's **bookmark view** (§3.2 Mode 2) — a small affordance that floats above JupyterLab / Grafana and expands on hover. The Flasher is likewise out of scope for now (separate operator tool, will be styled later). What you do design: (a) the platform navbar (including how its bookmark view appears over JupyterLab/Grafana), (b) the docs portal, (c) the download page, and (d) the home page.

---

## 3. Main navbar (platform-wide)

The navbar is the **only** UI element that is shared across **every** page of the platform — including third-party services like JupyterLab and Grafana. It is the user's home base.

### 3.1 What it contains

Six navigation items, in this fixed order:

| # | Label | Destination | Purpose |
|---|---|---|---|
| 1 | **Home** | `/` | Platform landing page |
| 2 | **Docs** | `/docs/` | Documentation portal |
| 3 | **Download Agent** | `/download/agent` | SerialHop Windows agent download |
| 4 | **JupyterLab** | `/jupyter/` | Shared notebook environment |
| 5 | **Grafana** | `/grafana/dashboards` | Monitoring dashboards |
| 6 | **Flasher** | `/flash/` | Operator firmware-flashing UI |

Each item shows a small icon + a text label. Designer should produce a fresh icon set; the meaning of each icon should be obvious enough to recognize the destination even when the label is hidden (collapsed mode — see below).

There is also a **toggle button** at the bottom (or end) of the navbar — a chevron that expands or collapses the navbar, and flips direction depending on state.

**Theme toggle.** Pinned in the navbar (near the collapse chevron — bottom of the rail in persistent mode, inside the expanded overlay in bookmark mode). Two states: **light** and **dark**. The icon should change to communicate state (sun / moon is the conventional pair) and remain meaningful in both collapsed (icon-only) and expanded (icon + label) navbar states.

- **Default:** respect the user's system preference (`prefers-color-scheme`) on first visit. Once the user toggles, the manual choice wins and persists across sessions (localStorage or cookie).
- **Scope:** the theme controls **lab-bridge-owned surfaces only** — the navbar itself, the Home page, Docs, and the Download page. It does **not** drive JupyterLab's or Grafana's themes (each is a separate application with its own theme settings). If the user picks dark lab-bridge while their JupyterLab is light, that's expected — the navbar tab floating over JupyterLab simply renders in lab-bridge's theme, and the underlying JupyterLab keeps its own.
- The toggle does not require login; it is a per-browser preference like the language choice.

Outside the navbar itself there is one more global element: a small **footer** at the bottom of every page (on the platform-owned pages — Home, Docs, Download) with a single "lab-bridge" link back to `/`. Keep it minimal; it exists only as a back-to-home anchor.

### 3.2 How it works — two modes

The navbar adapts to **where the user currently is**, because some pages it overlays (JupyterLab, Grafana) need every pixel for their own UI.

**Mode 1 — Persistent rail** (used on Home, Docs, Download Agent, Flasher — the platform's own pages)

- The navbar lives as a **vertical rail on the left edge** of the page.
- Two states: **collapsed** (narrow — icons only, no labels) and **expanded** (wider — icons + labels).
- User toggles between the two states by clicking the chevron button. State is remembered in the browser, so the user's preference persists across pages and sessions.
- Pressing **Escape** while expanded collapses it.
- Page content sits to the right of the rail and automatically reflows when the rail expands/collapses (smooth transition, not a jump).
- When expanded, a dim **backdrop overlay** appears over the page content. Clicking the backdrop collapses the rail. (This makes the expanded state feel like a temporary lookup, not a permanent layout shift.)

**Mode 2 — Bookmark tab** (used on JupyterLab and Grafana, which "own" the full viewport)

> JupyterLab and Grafana themselves are **out of scope** for this design. The bookmark tab is the *only* lab-bridge-owned UI that appears on those pages, and the only thing the designer produces for that context.

- The navbar is **not** a rail. Instead it shrinks to a tiny **bookmark tab** pinned to one corner of the screen (bottom-left in the current implementation; designer can revisit the anchor).
- The tab is just an affordance — a hint that the platform navbar is there.
- **On hover** (~150 ms delay so it doesn't trigger on accidental cursor passes), the tab expands into the full navbar overlay with all six items.
- **On mouse leave** (~300 ms delay so the user doesn't lose it by skimming the edge), it collapses back to the tab.
- Clicking the backdrop, or pressing Escape, also collapses it.
- Crucially, the bookmark tab takes **zero layout space** from the underlying page — it floats above it.
- The bookmark/overlay renders in lab-bridge's own theme (light/dark per §3.1) regardless of what theme JupyterLab or Grafana are using. Visual harmony with the underlying app is **not** a design goal — clear separation is.

### 3.3 The "current page" / active state

Whichever navbar item matches the page the user is on is shown as **active** (visually distinct + announced to screen readers). On nested pages (e.g. anywhere under `/docs/...`), the **Docs** item stays active throughout.

### 3.4 Accessibility expectations

- The navbar is a `<nav>` region with an accessible name ("Platform navigation").
- Each link has an `aria-label` matching its text label (so collapsed/icon-only mode still announces correctly).
- The active item has `aria-current="page"`.
- The toggle button has an `aria-label` that updates based on state ("Expand sidebar" / "Collapse sidebar").
- Full keyboard reachability; Escape collapses an expanded navbar.

### 3.5 Responsive expectations

The current implementation does not yet have a clearly-designed mobile/narrow-viewport story for the navbar. **This is something the designer should propose.** Likely answer: on narrow viewports, treat the navbar like the "bookmark" mode everywhere — a small affordance that expands to a full-screen / modal overlay on tap, then dismisses.

### 3.6 What the navbar is NOT

- It is **not** a top horizontal bar with a logo + menu. It is a **side rail**. This is intentional: the platform is service-heavy, and the rail metaphor (Slack, VS Code, GitHub) is a better fit than a marketing-style topbar. Designer should preserve this side-rail metaphor.
- It does **not** contain search, user account/profile, or notifications. (Those don't exist platform-wide today; if the designer thinks any of them belong in the navbar, call it out as a proposal rather than assuming it.)
- It does **not** contain the language toggle — that lives on Home (§6) and Docs (§4.4) only. The theme toggle is the *only* preference control in the navbar.
- It does **not** brand itself loudly. The branding (logotype "lab-bridge") should appear once, subtly — likely in/near the navbar — not as a giant header on every page.

---

## 4. Docs page UI

The docs portal is reached at `/docs/`. It serves Markdown content (the operators write `.md` files; the server renders them into pages). The portal must look like a **calm reading environment** — comfortable line length, clear hierarchy, fast scanning.

**Design reference: [MkDocs Material](https://squidfunk.github.io/mkdocs-material/).** Use it for the overall feel — clean left sidebar, single reading column, restrained typography, comfortable admonitions and code blocks, light/dark theme story. **Borrow the vibe and structural pattern, not the full feature set.** MkDocs Material ships with rich features (right-side in-page TOC, full-text search, version selector, content tabs, instant navigation, etc.) — **we do not need any of those right now.** Our documentation is tiny; the UI should stay lean and grow features only when the docs actually justify them.

The essentials below are what the design must cover. Anything not listed is deliberately omitted — do not invent extras.

### 4.1 Page layout

Two-column layout on wide viewports:

- **Left column — Documentation sidebar (navigation between docs).** This is *different from and additional to* the platform navbar in §3. The platform navbar sits to the left of this sidebar (or above it on narrow screens). Think: VS Code-style "activity bar (platform navbar) + file explorer (docs sidebar) + editor (content)".
- **Right column — Article content.** Constrained reading width so lines stay scannable (~720px feels right today; designer can revisit).

On narrow viewports the two columns stack — content first, sidebar below (or collapsed behind a "Docs menu" toggle).

### 4.2 Docs sidebar

- Hierarchical tree of every documentation page, auto-built from the folder structure of `public_docs/`.
- Each entry is a link with the page's title (e.g. "Getting started", "Connecting a device", "FAQ").
- Folders can contain pages and sub-folders. Nesting is rendered as an indented tree, with parent folders shown as section labels.
- The page the user is currently reading is highlighted as **active**.
- If the user has selected Russian, the sidebar shows Russian titles for any page that has a translation, and English titles for the rest (the EN title is always the fallback).

### 4.3 Article content area

The article body is rendered HTML from Markdown. The designer styles **only the essential primitives** below — these are what real docs in `public_docs/` actually use:

- **Headings** (`h1` through `h3` are the ones in active use; `h4`–`h6` should render readably but don't need heavy design). `h1` is the page title (one per page). `h2`/`h3` are major / minor sections — they need clear visual rhythm so the page can be scanned. Each heading has an anchor (clickable link icon next to it) for deep linking; the anchor handle reveals on hover.
- **Paragraphs, ordered/unordered lists (with simple nesting), blockquotes.**
- **Inline code** — short monospaced spans within a sentence.
- **Code blocks** — fenced multi-line code with **syntax highlighting** (server emits class-based highlighting; designer provides a code-block color theme in both light and dark). Each code block has a **"copy to clipboard"** button that appears (e.g. on hover) in the top-right corner; after clicking, the button shows a confirmation state (checkmark) for ~1.5 s, then resets.
- **GitHub-style admonitions / alerts** — five flavors to distinguish: `NOTE`, `TIP`, `IMPORTANT`, `WARNING`, `CAUTION`. Each has an icon + colored accent + label prefix. Calm but unmistakable. (These get used a lot — important to design well.)
- **Tables** — readable on wide content; should gracefully scroll horizontally on narrow viewports rather than break the layout.
- **Images** — fit the content column, with optional caption; responsive.
- **Mermaid diagrams** — diagrams written in code inside the Markdown source are rendered into SVG by Mermaid's own renderer. The designer doesn't need to style the diagram internals; only the surrounding container should fit the page's visual language.

**Lower-priority primitives** — the Markdown renderer also emits **task lists** (`- [ ]` / `- [x]` checkbox items) and **footnotes** (superscript references with notes at the bottom of the article). These appear rarely in current docs. They just need to render correctly with default-readable styling — no bespoke treatment required.

**Not in scope right now** (do not design these, they don't exist in our docs): right-side in-page table of contents, content tabs, version selector, "edit this page" links, contributor avatars, last-modified timestamps, comments / feedback widgets.

### 4.4 Language toggle

- **EN / RU**, English is the default on first visit.
- The toggle lives **on the docs page itself** (not in the platform navbar). Suggested placement: top of the article area, near the page title, or the top-right corner of the article column. Designer picks within the docs-page scope.
- **Shown only when a translation exists.** Any docs page that has a `*.ru.md` companion to its `*.md` shows the toggle; English-only pages show no toggle. A user who is in RU mode and lands on an English-only page sees that page in English with no toggle visible — they remain in RU for every other translated page.
- When the user toggles, the choice persists in a **1-year cookie** and applies platform-wide. All subsequent navigations (docs sidebar, the Home page, the Download page's bilingual sections, internal links) render in the chosen language.

### 4.5 Search

**No search in this design.** Our documentation is small enough that the sidebar tree is sufficient. Search may be added later when the doc set grows — at that point the UI can be revisited. Do not design a search bar or reserve space for one now.

### 4.6 Docs welcome page

`/docs/` (with no further path) is the **docs welcome page**. It is reached via the platform navbar's **Docs** item or from the home page (§6). It is *not* the platform's main entrypoint — that role belongs to the home page now.

It should:

- Orient the visitor to **the docs themselves**: how they're organized, where to start.
- Offer at least two starting paths: one for researchers ("Run your first notebook") and one for lab operators ("Set up a lab PC").
- It is itself just a Markdown doc, so its content uses the same primitives as any other doc page.

### 4.7 Footer on docs pages

Same minimal global footer described in §3.1 (single "lab-bridge" link back to `/`). No other footer content (no copyright line, no nav, no social links) is expected at this stage.

---

## 5. Download page UI (`/download/agent`)

This page distributes the **SerialHop** agent. It is reached from the platform navbar's "Download Agent" item.

SerialHop will ship on three platforms. Only one is available today:

| Platform | Status |
|---|---|
| Windows | available |
| Linux | coming soon |
| Raspberry Pi | coming soon |

The page is a single reading-width column. Three stacked regions, top-to-bottom: hero, platform downloads, optional body.

### 5.1 Hero section

- **Title** — `SerialHop`.
- **Lede paragraph** — one sentence explaining what SerialHop is, in plain language. Should be **platform-neutral** (no longer Windows-specific). Suggested wording: *"Single-binary agent that exposes a lab PC's instruments to lab-bridge through a secure reverse tunnel."* Designer may rephrase, but keep it one or two sentences.
- **Secondary link** — below the lede, a small "Source, releases, and protocol notes:" line linking out to the SerialHop GitHub repo (`https://github.com/bioexperiment-lab-devices/serialhop`). De-emphasized.

The hero does **not** contain a download button — actual downloads live per-platform in §5.2.

### 5.2 Platform downloads

A **vertical list of platform cards**, one card per supported platform. Currently three cards in this order: Windows, Linux, Raspberry Pi. **All three are always shown** — no OS auto-detection, no tabs, no "show other platforms" toggle. The user sees the full set every time and picks for themselves.

Cards share the same structural skeleton (header with platform name + icon + status indicator); their body differs by state (§5.2.A available vs. §5.2.B coming-soon). The available card is visually the primary CTA on the page; coming-soon cards are visibly subdued so the eye lands on what is actually downloadable today, while still making it obvious the other platforms are *planned, not broken*.

#### 5.2.A Available card (Windows today)

Order of elements inside the card, top to bottom:

1. **Card header** — platform name ("Windows"), platform icon, no badge (or a subtle "Available" indicator if the designer wants symmetry with the coming-soon cards).
2. **Primary download button** — large, unmissable, the visual focal point of the entire page. Its label includes:
   - the platform (`Download for Windows`),
   - the version (`v0.9.0`),
   - and the file size (`12.3 MB`).
   - Example label: *"Download for Windows · v0.9.0 · 12.3 MB"*.
   - Clicking it downloads a file like `SerialHop-v0.9.0.exe`.
3. **Browser-block explainer** (Windows-only — see §5.3 for full content). Collapsed by default, sits directly under the button because that's the moment a user needs it (they just clicked and the browser hid the file).
4. **Version metadata** — a definition list with three label-value pairs:
   - **Version** — e.g. `0.9.0`.
   - **Released** — the upload timestamp, ISO format, e.g. `2026-05-12T14:33:21Z` (designer may humanize the formatting).
   - **SHA-256** — a 64-character hex digest in a monospaced font. Selectable (so the user can copy it), ideally with a copy-to-clipboard button matching the docs' code blocks. The SHA is the integrity check the browser-block explainer refers to ("verify against the value your server admin sent you").

**Build-not-yet-uploaded edge case** — if no Windows build has been uploaded yet (rare, but happens between releases), the download button is replaced by a disabled-looking button reading *"Not yet available — check back soon"*, and the metadata + browser-block sections hide. The card itself stays visible; it does not collapse to a "coming soon" state (this is a distinct state — "build pipeline temporarily empty", not "platform not supported").

#### 5.2.B Coming-soon card (Linux, Raspberry Pi)

- **Card header** — platform name + platform icon, plus a clearly visible **"Coming soon"** badge.
- **Body** — a single line of muted text. Suggested wording: *"Linux build is on the way."* / *"Raspberry Pi build is on the way."* Designer may add a more interesting treatment (illustration, a date/quarter hint if known, a "notify me when ready" link to a mailing list, etc.) but it must clearly read as *planned, not broken*.
- **No download button, no version metadata, no install notes.**
- The card should be visually **subdued** relative to the available card (lower contrast, dimmer background, smaller footprint) so the user's eye is unambiguously drawn to the platform they can actually use today. They are present primarily as a signal of platform breadth.

When new platforms come online, their card gains the full Available treatment (button + metadata + any platform-specific install notes — Linux will likely need a `chmod +x` / systemd snippet, Raspberry Pi may need architecture selection). Those platform-specific notes will be added in a follow-up brief at that time.

### 5.3 "Your browser may block this download" — collapsible explainer (Windows-only)

This explainer lives **inside the Windows card** (§5.2.A, slot 3). It is Windows-specific: the unsigned `.exe` triggers Microsoft Defender SmartScreen, and users get stuck unless we walk them through it. It does **not** appear on Linux or Raspberry Pi cards (those platforms don't have the SmartScreen issue, and Linux/RPi users typically expect to mark binaries executable themselves).

- **Summary line** (always visible) — e.g. *"Your browser may block this download"* with a warning icon and a chevron that rotates as the section expands.
- **Expanded content** — explains in plain language that:
  1. The binary is fresh and unsigned, has no SmartScreen reputation yet, and is safe.
  2. They can verify it by checking the SHA-256 against the value their server admin sent them (the SHA-256 is shown right above, in §5.2.A slot 4).
  3. **What to do if the browser hides the download** — a numbered list of clicks: open the downloads list (Ctrl+J), find the file, click `⋯` → "Keep", and if a second "this file might harm your computer" prompt appears, choose "Keep dangerous file".
  4. **What to do when Windows blocks the .exe on first run** — a numbered list: in the SmartScreen dialog, click "More info" (the "Run anyway" button is hidden until you do), then click "Run anyway"; Windows remembers the choice for next time.

This section must be **fully bilingual** — when the user has selected Russian, the entire content of the explainer (summary, body paragraphs, numbered steps, button labels referenced inline) renders in Russian. The English version is the default fallback.

Visual treatment: this is a *warning* but not an *error*. It should read as "here's an annoying-but-expected hurdle and the way past it", not as "something is wrong". A left-edge color accent + warning icon + slightly tinted background is the established pattern.

### 5.4 Optional body Markdown

Below the platform downloads, the page may render an additional free-form Markdown body (operator-supplied, optional). This is **platform-agnostic** content — general SerialHop background, links to related docs, FAQ entries, troubleshooting notes that apply to every platform. When present, it uses the **same Markdown primitives** as the docs (§4.3). When absent, this section is omitted entirely — there is no empty placeholder. Designer should make sure the visual flow works equally well with or without this section.

---

## 6. Home page (`/`)

The home page is **the platform's main entrypoint**. Every user who opens the root URL lands here. (The previous "`/` redirects to `/docs/`" behavior is going away; redesign the home page as a real page.)

**The home page is not a marketing page.** lab-bridge is not selling anything. The page exists to help the people who already use the platform do their work faster, and to orient the people who are just starting out. No hero pitch, no "Why lab-bridge", no testimonials, no feature carousel, no signup CTA.

### 6.1 Audience

In priority order:

1. **Lab member (researcher)** — the heaviest day-to-day audience. They come to the home page to check on equipment or jump into JupyterLab.
2. **Lab operator** — they come to check on their lab's connection or find the agent download.
3. **First-time visitors and potential clients** — people who arrive at the home page (and `/docs/`) without credentials and want to understand what lab-bridge is. Home and Docs are publicly reachable; the intro section (§6.4.1) is what this audience reads.

**Server administrators are explicitly out of scope.** They already know the platform inside out and operate it via Grafana / Flasher / CLI. Do not design any section "for them".

### 6.2 Anonymity (no per-user state)

The home page is **public and unauthenticated**. lab-bridge has no unified login (each service auths separately). Do **not** design widgets that assume a signed-in user: no "welcome back, X", no "your recent notebooks", no "your activity". There is no identity to draw from.

### 6.3 Not Markdown — full design freedom

Unlike the docs (§4), the home page is **not** rendered from Markdown. It is a fully custom-designed page — bespoke components, status widgets, layouts, anything that helps the audiences above is fair game. The designer owns its primitives entirely.

### 6.4 Content sections

These are the sections we know are useful. The designer can re-order, merge, or propose additional sections — but any subtraction should be justified (each section earns its place by being useful to the researcher or the lab operator).

#### 6.4.1 Header bar + intro (top)

A thin **header bar** anchored at the top of the page, containing:

- "lab-bridge" wordmark (left).
- **Language toggle (EN / RU)** (right). EN is the default; the home page is always available in both languages (the designer produces both versions). Toggling here flips the page immediately and writes the 1-year platform-wide cookie (§2.4) — every subsequent Docs / Download visit will render in the chosen language.

Directly below the header bar, an **intro / about-the-platform section** for the third audience: first-time visitors and potential clients who arrived without credentials and need to understand what lab-bridge is. This section should:

- Explain in **plain language, two to four sentences**, what lab-bridge does. Example wording to adapt: *"lab-bridge connects research labs to a shared cloud notebook environment. A lab's instruments (pumps, valves, densitometers, thermostats, etc.) are connected over serial ports to a lab PC running the SerialHop agent. The agent exposes those instruments to a JupyterLab server, so a researcher can run an experiment from anywhere."*
- Optionally include a **small "how it works" diagram** — a single line of three labelled boxes is enough: `Lab PC (devices + SerialHop)` → `lab-bridge server` → `Researcher in JupyterLab`. Designer chooses whether to include and how to draw it; the goal is one-glance comprehension of the topology.
- Optionally include a **one-line "who this is for"** statement, e.g. *"Built for research labs running serial-port instrumentation."* Keep it factual, not promotional.

Constraints for this intro section:

- **Informative, not promotional.** No marketing phrasing ("the future of…", "revolutionizing…", "empowering scientists to…"), no call-to-action buttons, no testimonials, no logos-of-customers grid, no signup form. The platform is not selling anything; this section exists only to orient newcomers, not to convert them.
- **Modest footprint.** Daily users (researchers + lab operators) skim past this every visit, so it must not dominate the page or push the equipment status panel below the fold. A tasteful, compact block sitting above the equipment panel — not a hero banner.
- The intro renders in the user's chosen language (EN default, RU if the toggle is flipped); designer produces both versions.

#### 6.4.2 Lab status (primary section — the killer feature)

The single most useful thing on the home page for daily users. Make it the visually dominant region below the intro.

A panel showing **every registered lab and its current connection status.** A *lab* here means one SerialHop installation on one lab PC. Each lab exposes a set of physical instruments (pumps, valves, densitometers, etc.) to the platform, but those device-level details are not shown on the home page — only the lab itself and whether its SerialHop is currently connected.

Each row in the list shows:

- **Lab name** — monospaced, copyable (this is the same identifier a researcher uses when addressing the lab from a notebook).
- **Status indicator** — `online` / `offline` (a transient `connecting` state is acceptable if the data supports it).
- **Last seen** — timestamp for offline labs; hidden / "now" for online ones.
- **SerialHop version** — the version string reported by that lab's SerialHop agent (e.g. `v0.10.2`). De-emphasized text — researchers ignore it; lab operators glance at it to see whether auto-update has rolled out. If a lab is on an older version than the rest of the fleet (auto-update stuck or pending), the value should be visually flagged (e.g. an "outdated" pill or a muted warning color) so it stands out without screaming.
- **Optional friendly label** — a human-readable name or location ("Bench 4", "Müller group, room 214") if the server admin provided one.

Recommended sort: problems first (offline → connecting → online), then alphabetical within each group. Researchers want to see at a glance whether the lab they're about to work with is up; lab operators want to see "is my lab offline?" without scanning.

**Empty state** — if no labs are registered yet, show *"No labs connected yet"* + a link to the lab-operator setup doc. Don't render an empty panel skeleton.

**This panel serves both daily-user audiences:** a researcher about to start an experiment glances here to confirm `lab-3` is up; a lab operator glances here to confirm their lab's SerialHop is still reporting in.

Per-device status (which pump is alive, which thermostat dropped off) is **not** shown on the home page — that level of detail belongs in Grafana or a docs page. The home page is the at-a-glance layer.

#### 6.4.3 Quick destinations

A small set of clearly-presented entry points to the platform's primary services. Suggested set, in audience-priority order:

- **Open JupyterLab** (for researchers — most prominent).
- **Browse docs** (everyone).
- **Download SerialHop agent** (for lab operators).
- **Grafana dashboards** (secondary — for lab operators monitoring their agent logs).

These overlap with the navbar by design. The navbar is the always-available global rail; these home-page entry points are bigger, clearer one-click affordances for users who haven't yet internalized the navbar, and a way to make the day-one primary path visually obvious.

Visual weight: clear and clickable, but **not enormous**. They are utility tiles, not marketing CTAs.

#### 6.4.4 Getting started

A small "first time here?" panel pointing newcomers to onboarding docs. **Two clearly-labeled paths** matching the two in-scope audiences:

- **For researchers** → link to the "Run your first notebook" doc.
- **For lab operators** → link to the "Set up a new lab PC" doc.

Two side-by-side cards or two stacked links — designer's call. **Low-key visual weight**: experienced users should be able to skip past it without it competing with the equipment status panel for attention.

### 6.5 What the home page is NOT

The intro section (§6.4.1) is informative, not promotional — keep that distinction sharp. The home page is still **not**:

- **Not a hero pitch** with a giant headline + CTA button. The intro is a modest block, not a banner.
- **Not a feature list / "Why lab-bridge?"** section, not a comparison table.
- **Not a marketing landing page** — no testimonials, social proof, screenshots-as-marketing, "trusted by" logos, signup forms.
- **Not a logged-in dashboard** with per-user data.
- **Not a docs page** — docs live at `/docs/` (§4); the home page is *not* Markdown content with a sidebar.
- **Not a complete system-status dashboard** — surface only the few things daily users actually need at a glance. Per-device health, log volume, error rates, and other detailed metrics live in Grafana, not on the home page.
- **Not an announcements feed.** Don't design a "what's new" panel.

---

## 7. Out of scope for the designer

**Explicitly out of scope** — do not design, restyle, theme, or propose changes to any of the following:

- **JupyterLab** (third-party application). Its internal UI, layout, theme, and authentication screens are entirely its own. The only lab-bridge UI on these pages is the navbar's bookmark view (§3.2 Mode 2).
- **Grafana** (third-party application). Same as JupyterLab — out of scope; bookmark view of the navbar is the only thing we put on top.
- **The Flasher's internal screens** (separate operator tool, will be styled in a future brief).

For these out-of-scope services, the designer's *only* deliverable touching them is the **bookmark view of the platform navbar** that floats above them (§3.2 Mode 2).

The designer **is** responsible for:

- The platform navbar (§3) — both the persistent rail mode and the bookmark/overlay mode that appears over JupyterLab / Grafana / Flasher.
- The docs portal (§4).
- The download page (§5).
- The home page (§6).
- The global footer.
- The visual identity (typography, color palette, light/dark theme, iconography, spacing) that unifies all of the above.
