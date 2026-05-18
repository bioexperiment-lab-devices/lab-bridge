# Handoff: Lab Bridge — Web UI

## Overview

Lab Bridge is an enterprise lab-instrumentation platform: a single web portal that bridges physical lab instruments (pumps, valves, microscopes, sequencers, thermostats) connected to lab PCs to a shared JupyterLab notebook environment via secure reverse tunnels through the **SerialHop** agent.

This handoff covers the **server-side web UI** (the platform itself), specifically the surfaces the design owns:

1. **Platform navbar** — three states: expanded rail, compact rail, bookmark-tab overlay.
2. **Home page** — the platform's main entrypoint.
3. **Download Agent page** — distributes the SerialHop agent (Windows available; Linux/RPi planned).
4. **Docs page** — the documentation portal (MkDocs-style).

The Flasher is out of scope for this handoff (separate brief).

## About the Design Files

The files in `source/` are **design references created in HTML/React/JSX** — runnable prototypes that show the intended look and behavior. They are **not production code to copy directly**.

Your task: **recreate these designs in the target codebase's existing environment** (whatever stack the lab-bridge server uses for its UI — most likely a modern React/Vite or Next setup, or a server-rendered template with a sprinkle of JS). If no UI environment exists yet, choose the most appropriate framework for an enterprise SaaS portal (Next.js + React + Tailwind, SvelteKit, etc.) and implement there.

What to lift from the prototype:
- Visual design tokens (colors, typography, spacing, radii, shadows) — exact hex values.
- Component structure, hierarchy, and copy.
- Interaction patterns (rail expand/collapse, hover behaviors, theme/lang toggles).
- The minimum CSS rules to reproduce the look. The prototype's CSS uses ordinary classes and `data-*` attributes, so it ports cleanly to any framework's styling system.

What NOT to lift:
- The pan/zoom canvas (`design-canvas.jsx`) — that's a design-time-only wrapper to lay artboards out side by side. Do not include it in production.
- The tweaks panel (`tweaks-panel.jsx`) — same, design-time only.
- The dev-mode CDN imports of React/Babel.

## Fidelity

**High-fidelity (hifi).** Pixel-perfect: final colors, typography, spacing, and interaction states. Recreate exactly using the codebase's component primitives.

## Visual identity at a glance

- **Type system:** IBM Plex Sans (UI) + IBM Plex Mono (lab names, versions, code blocks, paths, eyebrow tags). Load from Google Fonts: weights 400/500/600/700 (sans) and 400/500/600 (mono).
- **Density:** Comfortable but information-dense. Default base size 13px in panels, 14.5px in docs article body.
- **Palette:** Warm-cream paper neutrals + a single deep-navy accent (`#1F3A8A`). Light theme leans on `#ECE9E0` (page) and `#FFFFFF` (surfaces); dark theme on `#1B1A17` (page) and `#232220` (surfaces).
- **Shapes:** Subtle borders (1px, low-contrast warm gray), 4–8px radii, very soft shadows. Avoids rounded-everything pill aesthetic. Square-ish, archival.
- **Iconography:** Custom-drawn 18×18 monoline SVG icons stroked with `currentColor`. Provided inline in `lab-bridge-navbar.jsx` as the `Icons` object — copy those SVG paths verbatim.

## Design tokens

Defined as CSS variables in `lab-bridge-styles.css` under `:root` (light) and `[data-theme="dark"]`. Reproduce these exactly.

### Colors — Light theme

| Variable | Value | Use |
|---|---|---|
| `--bg-page` | `#ECE9E0` | Page background outside surfaces |
| `--bg-window-outer` | `#2A2823` | Outermost window bezel (prototype only) |
| `--surface` | `#FFFFFF` | Cards, panels, rows |
| `--surface-sunken` | `#F8F6F0` | Recessed sections, hover state on rows |
| `--surface-strip` | `#FAF8F3` | Stripes, table headers, faint accents |
| `--surface-rail` | `#F3F0E6` | Navbar rail background |
| `--border` | `#E2DED2` | Default borders |
| `--border-strong` | `#C8C3B5` | Emphasized borders, dotted leaders |
| `--border-input` | `#C3BFB2` | Form input borders |
| `--text` | `#1A1916` | Primary body text |
| `--text-secondary` | `#514E47` | Secondary/quieter text |
| `--text-muted` | `#8A8678` | Tertiary, hints, metadata |
| `--text-inverse` | `#FAF8F3` | Text on dark/accent backgrounds |
| `--accent` | `#1F3A8A` | Active nav, links, buttons, brand mark |
| `--accent-hover` | `#182E6F` | Hover state of accent |
| `--accent-soft` | `#E7ECF6` | Accent-tinted backgrounds (active nav fill, primary card bg) |
| `--accent-border` | `#B8C2DC` | Accent-tinted borders |
| `--success` | `#2F7D3F` / `--success-soft` `#E5F1E6` / `--success-border` `#BCD7BE` | Online status |
| `--danger` | `#B23A2A` / `--danger-soft` `#F8E5E0` / `--danger-border` `#ECC5BC` | Offline status, caution admonitions |
| `--warning` | `#A37200` / `--warning-soft` `#F5EAC8` / `--warning-border` `#E2D096` | Outdated-version pill, warning admonitions |
| `--neutral-dot` | `#9F9B8E` | Neutral status dot |
| `--shadow-card` | `0 1px 0 rgba(26,25,22,0.04), 0 1px 2px rgba(26,25,22,0.06)` | Cards |
| `--shadow-popover` | `0 10px 24px -8px rgba(26,25,22,0.25), 0 2px 6px rgba(26,25,22,0.08)` | Popovers, bookmark overlay |
| `--shadow-overlay` | `0 24px 50px -20px rgba(26,25,22,0.45), 0 8px 18px -6px rgba(26,25,22,0.18)` | Bookmark expanded overlay |

### Colors — Dark theme

Critical: dark theme deliberately **brightens** the accent so blue text/icons stay AA-contrast on dark surfaces. The original navy `#1F3A8A` is unreadable on `#232220`.

| Variable | Value |
|---|---|
| `--bg-page` | `#1B1A17` |
| `--surface` | `#232220` |
| `--surface-sunken` | `#1D1C19` |
| `--surface-strip` | `#1F1E1B` |
| `--surface-rail` | `#1E1D1A` |
| `--border` | `#34322D` |
| `--border-strong` | `#4A4740` |
| `--text` | `#F0EDE3` |
| `--text-secondary` | `#B8B3A4` |
| `--text-muted` | `#7E7A6E` |
| `--accent` | `#BCCBF2` |
| `--accent-hover` | `#DBE3F8` |
| `--accent-soft` | `#2A3257` |
| `--accent-border` | `#4A5587` |
| `--success` | `#7CC18A` / soft `#1F2C22` / border `#335A3E` |
| `--danger` | `#E58879` / soft `#34211D` / border `#6A3D34` |
| `--warning` | `#E3C067` / soft `#2F2715` / border `#5E4C20` |

If the user picks a custom accent at runtime, the `App` component in `Lab Bridge.html` brightens it for dark mode by mixing ~62% toward white. Reproduce that behavior if you support custom accents.

### Typography

- Font stack: `'IBM Plex Sans', system-ui, sans-serif` (UI) and `'IBM Plex Mono', monospace` (mono).
- `body { font-size: 13px; line-height: 1.45 }`.
- Headings have negative letter-spacing (`-0.005em` to `-0.022em`) and `text-wrap: pretty`.

Type scale used in the design:

| Role | Size | Weight | Tracking | Family |
|---|---|---|---|---|
| Statement headline (Home intro) | 26px | 600 | -0.018em | Sans |
| Section / article H1 | 32px (docs) | 600 | -0.018em | Sans |
| Article H2 | 22px | 600 | -0.014em | Sans |
| Article H3 | 16px | 600 | -0.008em | Sans |
| Panel title | 15px | 600 | -0.01em | Sans |
| Body / paragraph | 13.5–14.5px | 400 | -0.003em | Sans |
| Section title (rule-flanked) | 11px | 600 | UPPER, 0.11em | Mono |
| Eyebrow pill | 10.5px | 600 | UPPER, 0.14em | Mono |
| Lab name (mono) | 13px | 600 | -0.005em | Mono |
| Version (mono) | 11.5px | 400 | 0 | Mono |
| Outdated pill | 9.5px | 600 | UPPER, 0.08em | Mono |
| Nav item label | 13px | 500 (600 active) | -0.003em | Sans |
| Inline code | 13px | 400 | 0 | Mono |

### Spacing

The design uses an implicit 4/8/16 grid with frequent half-steps (e.g., 6, 10, 14) because it's information-dense. Specifics:

- Page outer padding: 28px top / 32px sides.
- Section spacing: 28px bottom margin.
- Card padding: 14–18px.
- Row padding: 9–12px vertical, 14–16px horizontal.
- Form/list gap: 8–14px.

### Radii

- 2px — inline status pills
- 3px — small chips, eyebrow pills
- 4–5px — buttons, input fields, list cards
- 6px — primary panels, browser-window inner
- 8px — major window chrome, overlay cards

### Iconography

All icons live in `lab-bridge-navbar.jsx` under `const Icons = { … }`. Six platform icons + chevrons + sun/moon/copy/arrow utility icons. Drawn at 18×18 viewBox, `stroke-width: 1.5`, `stroke="currentColor"`. Copy these SVG paths verbatim. Important specifics:

- **Home, Docs, Download, Flasher** — monoline strokes.
- **JupyterLab** — three crossed elliptical orbits + filled center dot. *Generic atomic mark, not Project Jupyter's brand logo* (deliberate — third-party brand isn't reproduced).
- **Grafana** — generic bar+line chart. *Not Grafana's flame mark.* Same reason.
- **External link indicator** — `↗` (Unicode, not SVG) in `.lb-nav-item__ext`, font-size 10px, mono, muted.

---

## Screens / Views

### 1. Platform navbar — three modes

**Files:** `lab-bridge-navbar.jsx`, `.lb-rail*` and `.lb-bookmark*` rules in `lab-bridge-styles.css`.

Side rail on the left edge of every lab-bridge-owned page (Home, Docs, Download, Flasher). On JupyterLab and Grafana, instead, a tiny "bookmark" tab appears in the bottom-left corner and expands on hover.

#### Fixed nav items (in order)

| # | Label | Path | Internal/External |
|---|---|---|---|
| 1 | Home | `/` | internal |
| 2 | Docs | `/docs/` | internal |
| 3 | Download Agent | `/download/agent` | internal |
| 4 | JupyterLab | `/jupyter/` | external (`↗` icon) |
| 5 | Grafana | `/grafana/dashboards` | external |
| 6 | Flasher | `/flash/` | external |

`aria-current="page"` on the active item. Active item gets the accent-soft background, accent left bar (`::before`), accent-colored icon, and bold weight.

#### Mode 1A — Expanded rail (220px wide)

- Width: 220px
- Brand row at top: 56px tall, contains 28×28 brand mark (`var(--accent)` fill, see `.lb-rail__mark` for inner brackets+circle SVG-less treatment) + "lab-bridge" wordmark + version pill "v3.4" in mono uppercase
- Nav items: 32px tall each, icon (22px) left + label + external indicator
- Bottom block: theme toggle (icon + label) + chevron collapse button ("◀ Collapse")
- Transition `width 200ms cubic-bezier(.2,.7,.3,1)`
- A backdrop dim `.lb-rail__backdrop` (rgba(26,25,22,0.18)) sits over page content to make the expanded state feel temporary; clicking it should collapse the rail.

#### Mode 1B — Compact rail (56px wide)

- Same component, `data-mode="collapsed"` flag hides all label spans and centers icons
- Theme toggle becomes icon-only square; chevron flips (use `transform: rotate(180deg)`)

#### Mode 2 — Bookmark tab (over JupyterLab/Grafana)

A tiny tab pinned to **bottom-left** (`left: 12px; bottom: 12px`), 132×32, with the brand mark + "lab-bridge" + `›`. Takes **zero layout space** (must be `position: absolute` or `fixed`).

On hover (150ms delay in), expand into `.lb-bookmark-overlay` — a 240px-wide floating panel with all 6 nav items, theme toggle inside, "Esc to dismiss" hint at the bottom. On mouse-leave (300ms delay), collapse back. Esc and clicking outside also dismiss.

The overlay renders in lab-bridge's own theme regardless of JupyterLab's/Grafana's theme.

### 2. Home page

**File:** `lab-bridge-home.jsx`, `.lb-page--*`, `.lb-home-header*`, `.lb-intro-stmt*`, `.lb-status-row`, `.lb-equip*`, `.lb-lab*`, `.lb-topo*`, `.lb-quick*`, `.lb-start*` rules.

Public, unauthenticated landing page. Stack from top:

#### 2.1 Sticky header bar

`.lb-home-header` — thin top bar that sticks (`position: sticky; top: 0; z-index: 5`) with a faint shadow when content scrolls beneath.

- Left: small accent dot + "lab-bridge" wordmark (15px, weight 600) + "lab instrumentation platform" tagline (10.5px mono, uppercase, separated by a vertical rule)
- Right: EN/RU language toggle — `.lb-lang` segmented control, mono uppercase, 11px

Bilingual: toggle writes a 1-year cookie and re-renders. Russian strings live in `STRINGS.ru` in `lab-bridge-home.jsx`.

#### 2.2 Intro section — "Statement headline"

`.lb-intro-stmt` — bordered warm-cream card with a 3px accent stripe on the left edge.

- Eyebrow row: `WHAT LAB-BRIDGE IS` pill (accent fill, white text, 10.5px mono uppercase)
- Headline: 26px sans, weight 600, color `--text`. Copy: *"One bridge from every lab instrument to the researchers using it."* (RU equivalent in strings file)
- Support: two paragraphs in a 1.6fr/1fr grid (text-secondary, 13.5px, line-height 1.6)

#### 2.3 Lab status + Topology row

`.lb-status-row` — 2-column grid (1.7fr / 1fr, gap 28px).

**Left column — Lab status panel** (`.lb-equip`, max-width 560px):
- Panel head: bordered top section, "Registered labs" title, "updated 4s ago" meta on the right
- Two groups inside, with subtle bordered-top group headers:
  - **ONLINE · N** (mono uppercase 10px, muted) followed by online lab rows
  - **OFFLINE · N** followed by offline lab rows
- **Row** (`.lb-labrow`): status dot (8px circle, `var(--success|--danger)`) + lab name in mono (13px, weight 600) + optional "OUTDATED" pill in warning yellow + version in mono (11.5px muted). No description column, no last-seen column.
- Online labs come first.
- Offline rows: name color drops to `var(--text-secondary)`.

**Right column — Topology diagram** (`.lb-topo-section`, max-width 280px):
- Same section header treatment ("How it works")
- Three stacked node cards joined by dotted vertical lines + downward arrowhead glyph
- Middle node (lab-bridge) emphasized with `--accent-soft` background, accent border, white-on-accent icon

#### 2.4 Quick destinations

`.lb-quick` — 4-column grid of clickable cards. Each: 24×24 icon tile + title + arrow indicator + path in muted mono below.

- **JupyterLab** card is primary (`data-primary="true"`): accent-soft background, accent-tinted icon. `↗` external arrow.
- Other three cards (Browse docs, Download agent, Grafana): neutral surface.

#### 2.5 Getting started

`.lb-start` — 2-column grid of large cards.

Each card has:
- Role pill at top: "FOR RESEARCHERS" / "FOR LAB OPERATORS" in mono uppercase, with a small colored dot (accent for researcher, warning for operator)
- Bold 15px title (e.g. "Run your first notebook" / "Set up a new lab PC")
- Description paragraph
- The doc path in muted mono (`/docs/researcher/first-notebook`)
- 28×28 chevron in the top-right that fills with accent-soft + accent stroke + slides 2px right on card hover

### 3. Download Agent page (`/download/agent`)

**File:** `lab-bridge-download.jsx`, `.lb-dl-*` rules in `lab-bridge-styles.css`.

Single reading-width column (max 880px). Distributes the **SerialHop** agent — single-binary lab-PC daemon that opens a reverse tunnel back to lab-bridge. Three regions stacked:

#### 3.1 Sticky header

Same `.lb-home-header` component used on Home. EN/RU toggle on the right. (Brief originally said no toggle here, but stakeholder asked for visual consistency — final design keeps it.)

#### 3.2 Hero

`.lb-dl-hero` — 2-column row: 56×56 accent-filled logo glyph (stylized "S" plug) + body.

- Title: `SerialHop` in **mono** (`IBM Plex Mono`), 30px, weight 600, tracking `-0.018em`. Mono is deliberate — distinguishes the product name from sans-set platform copy and reinforces "agent / system tool" character.
- Lede: one sentence. *"Single-binary agent that exposes a lab PC's instruments to lab-bridge through a secure reverse tunnel."* (RU equivalent in `DL_STRINGS.ru`.)
- Source link: `Source, releases, and protocol notes:` label + de-emphasized mono link to `github.com/bioexperiment-lab-devices/serialhop`, dotted bottom border. Hover → accent.

Hero is separated from platform cards by a 1px bottom border.

#### 3.3 Platform cards

`.lb-dl-cards` — vertical flex column, gap 12px. Always shows **all three** cards in this order: Windows, Linux, Raspberry Pi. No OS detection, no tabs.

**Card structure** (`.lb-dl-card`):
- Header row (`.lb-dl-card__head`): 36×36 icon tile + platform name (16px sans, weight 600) + sub-line (mono 11px, e.g. `Windows 10 / 11 · 64-bit`) + right-aligned **status pill** (vertical stack of status text + optional small ETA line).
- Body — only on Available cards.

**Available card** (`.lb-dl-card--available`):
- Border: `--border-strong` (slightly emphasized), with `--shadow-card`.
- Status pill: `Available` in green (`--success-soft` bg, `--success` text).
- **Primary download button** (`.lb-dl-card__cta`) — full-width, accent-filled, 14px padding, grid of icon (download glyph) + 2-line stack:
  - Line 1: *"Download for Windows"* — 16px, weight 600.
  - Line 2: `v0.9.0 · 12.3 MB` — mono 11px, opacity 0.85. (Filename was originally also here but removed — too cluttered.)
  - On click: triggers download of e.g. `SerialHop-v0.9.0.exe`.
  - Hover: `--accent-hover` bg.
- **Browser-block explainer** (`.lb-dl-explainer`) — native `<details>` element, Windows-only, collapsed by default:
  - Summary: warning-tinted bar with circular `!` icon + summary text + `▾` chevron that rotates `-180deg` when open.
  - Body: bordered top, indented under the icon. Two `<h4>` step groups in mono-uppercase warning color:
    1. *"If the browser hides the download"* — 3 numbered steps, `<kbd>` chips for `Ctrl`+`J`, `<code>` chips for `⋯`, bold quoted button labels.
    2. *"If Windows blocks the .exe on first run"* — 2 numbered steps, bold quoted dialog button labels (`More info`, `Run anyway`).
  - **Fully bilingual** — every word renders in the chosen language (per the platform cookie).
- **Version metadata** (`.lb-dl-meta`) — sunken stripe-styled dl:
  - `Version` → `0.9.0` in mono `<code>` chip.
  - `Released` → ISO timestamp `2026-05-12T14:33:21Z` + muted "6 days ago".
  - `SHA-256` → 64-char hex digest in mono `<code>` (user-selectable, `user-select: all`) + a small "COPY" button matching the docs-page copy-button visuals.

**Coming-soon card** (`.lb-dl-card--coming`):
- Border: `--border` with **dashed** stroke.
- Background: `--surface-sunken` (subdued vs. Windows).
- Icon tile slightly dimmed (opacity 0.7).
- Status pill: `Coming soon` in muted neutral (`--text-muted`), with a small ETA sub-line below (e.g. `expected Q3 2026`).
- **No body** — header alone, no download button, no metadata.
- Linux: monoline Tux silhouette. Raspberry Pi: monoline berry+leaves silhouette.

**Build-not-yet-uploaded edge case** (not currently rendered — note for impl): if no Windows build exists, swap the CTA for a disabled "Not yet available — check back soon" pill button and hide the explainer + metadata. The card stays visible; this is distinct from "Coming soon".

#### 3.4 Optional Markdown body

`.lb-dl-bodymd` — operator-supplied free-form Markdown rendered with the same docs primitives (`.lb-docs-article` styles, no max-width constraint here). Currently only a one-paragraph "Setup notes" pointing to the operator-setup doc. The original Tip admonition + FAQ subsections were removed by stakeholder request — keep the section **hidden entirely** when the operator hasn't supplied a body.

### 4. Docs page, `.lb-docs-*`, `.lb-code*`, `.lb-adm*`, `.lb-tok-*` rules.

MkDocs Material vibe. Two-column shell:

#### 3.1 Sidebar (left, 256px)

`.lb-docs-side` — vertical scrolling sidebar.

- Top: "Documentation" header with the docs icon, mono uppercase
- Sections (Researchers, Lab operators, Server admins, Reference) as group headers in mono uppercase
- Items: 13px sans, 5px left-border accent on active, accent-soft background on active
- Folders use `›` (or `⌄` when open) glyph prefix
- RU translation indicator: small `[RU]` pill on the right of items that have a Russian companion

#### 3.2 Article (right, max-width 720px, 32–48px padding)

- Breadcrumb trail in mono muted (e.g. "Docs / Lab operators / SerialHop agent / Connecting a device")
- H1 in 32px serif-feel sans, with `text-wrap: pretty`
- EN/RU language toggle in the top-right of the article — only shown when a Russian translation exists
- H2: 22px, bottom-bordered, with hover-revealed `#` anchor
- H3: 16px
- Paragraphs: 14.5px, line-height 1.65
- Inline code: `--surface-sunken` background, `--accent` text (light) / `#C6D4F2`-ish accent text with tinted background (dark)
- Lists: standard indentation
- Links: accent text, underline color `var(--accent-border)`, hover darkens border
- **Code blocks** (`.lb-code`): dark surface always (`#1A1916`), language label + filename in mono header bar with a "Copy" button that toggles to "✓ copied" for 1.5s. Token classes: `.lb-tok-k` (keys, purple), `.lb-tok-s` (strings, green), `.lb-tok-n` (numbers, yellow), `.lb-tok-c` (comments, italic gray), `.lb-tok-p` (punctuation, blue), `.lb-tok-y` (red), `.lb-tok-v` (plain).
- **Admonitions** (`.lb-adm`) — five flavors via `data-kind`:
  - `note` → accent
  - `tip` → success
  - `important` → purple `#6B3FA0` (only color outside the standard palette)
  - `warning` → warning
  - `caution` → danger

  Each has: 28px column with circular accent icon + body. Icon glyphs: `i` (note/tip), `i`/`!` (important/warning), `×` (caution).
- Tables: bordered wrapper, mono uppercase header, monospace `<code>` in cells uses accent color
- Prev/Next footer links at the bottom of the article

## Interactions & Behavior

### Navbar rail
- Click chevron → expand/collapse
- Click backdrop while expanded → collapse
- `Esc` while expanded → collapse
- State persists in `localStorage` (or a cookie) per browser. Smooth `width` transition 200ms with `cubic-bezier(.2,.7,.3,1)`.

### Bookmark tab (over JupyterLab/Grafana)
- Hover 150ms delay → expand to overlay
- Mouse-leave 300ms delay → collapse
- Click backdrop or `Esc` → collapse
- The tab itself is `position: absolute`, no layout impact on underlying app

### Theme toggle
- Default: respect `prefers-color-scheme` on first visit
- After user toggles: manual choice wins, persisted in localStorage
- Scope: only lab-bridge-owned pages (Home, Docs, Download). Does NOT theme JupyterLab/Grafana.

### Language toggle (EN/RU)
- Lives on Home (top-right of sticky header) and on Docs (top-right of article)
- Writes a 1-year cookie, applied platform-wide
- Docs sidebar shows RU titles where translation exists, falls back to EN otherwise
- Docs toggle only renders on pages with a translation

### Copy buttons
- On code blocks (docs) and on lab names (home) — click copies to clipboard, swaps icon to ✓ for 1.5s, then resets.

### Sticky header
- The home/docs sticky header gains a subtle shadow `0 4px 10px -8px rgba(26,25,22,0.18)` once content scrolls beneath.

### Lab status sorting
- Online group first, then Offline. Sort alphabetical within each group.

### Outdated pill
- Shown when a lab's reported SerialHop version is behind the fleet's `latest`
- Tooltip: "This lab is on an older SerialHop than the rest of the fleet"
- Pill style: 9.5px mono uppercase, warning colors

## Responsive expectations

The prototype is laid out for ≥1280px viewports. On narrow viewports (designer proposal):

- The rail switches to bookmark-style behavior universally — small tab that opens a full-screen overlay on tap, dismisses on Esc/outside-tap.
- Docs columns stack: sidebar collapses behind a "Docs menu" toggle, content takes full width.
- Status row stacks: topology drops below the lab list.

This was proposed but not designed in detail. Confirm with design before implementing.

## Accessibility

- `<nav aria-label="Platform navigation">` wraps the rail
- Each nav link has `aria-label` matching its text (so collapsed mode still announces)
- Active item: `aria-current="page"`
- Chevron button: `aria-label` updates between "Expand sidebar" / "Collapse sidebar"
- All icons inside text containers: `aria-hidden="true"`
- Full keyboard reachability; Esc closes expanded rail / bookmark overlay
- Code-block copy button: focusable, announces "copied" via aria-live
- Color is never the sole signal: status icon dots are paired with text labels in group headers

## Assets

No bitmap images required. All visuals are:
- SVG icons defined inline (see `lab-bridge-navbar.jsx` and `lab-bridge-docs.jsx`)
- IBM Plex fonts loaded from Google Fonts CDN
- Pure CSS for color, type, layout

If your codebase has a custom icon library, replace the inline SVGs with library equivalents — but keep the same visual weight (1.5px stroke, 18×18 box, monoline).

## Source files in this bundle

Under `source/`:

- **`Lab Bridge.html`** — the runnable design canvas. Open in a browser to see all artboards laid out in a pan/zoom canvas. Each artboard inside a faux browser window.
- **`lab-bridge-styles.css`** — all CSS for the production surfaces (navbar, home, download, docs). The canvas/tweaks bits at the bottom of this file are design-time only and can be skipped.
- **`lab-bridge-navbar.jsx`** — `LBBrowser`, `LBRail`, `LBBookmarkTab`, `LBBookmarkOverlay`, the `Icons` map, and `NAV_ITEMS`. Lift verbatim except `LBFauxApp` (placeholder for the screenshot context).
- **`lab-bridge-home.jsx`** — `LBHome`, `HomeHeader`, `IntroSection`, `LabStatusPanel`, `LabChipGroup`, `TopologyDiagram`, `QuickDestinations`, `GettingStarted`, plus `STRINGS` (EN + RU). The `LABS` constant is sample data — replace with a backend feed.
- **`lab-bridge-download.jsx`** — `LBDownload`, `DLHeader`, `DLHero`, `DLPlatforms`, `DLCardWindows`, `DLCardComingSoon`, `BrowserBlockExplainer`, `DLBodyMarkdown`, plus `DL_STRINGS` (EN + RU, including the full bilingual explainer copy). `FLEET` is sample data — the version / size / sha / released values come from the build pipeline. `WindowsIcon`, `LinuxIcon`, `RaspberryIcon` are inline monoline SVGs.
- **`lab-bridge-docs.jsx`** — `LBDocs`, `DocsSidebar`, `DocsArticle`, `CodeBlock`. The sidebar items are sample; in production they'll be auto-built from `public_docs/` folder structure.
- **`design-canvas.jsx`** / **`tweaks-panel.jsx`** — **design-time only**. Don't include in production. They're the pan/zoom canvas and the in-design tweak panel respectively.

## What to build first

Recommended order:

1. **Design tokens** — port the CSS variables to whatever system the codebase uses (Tailwind theme, CSS custom properties, design tokens JSON).
2. **Browser shell can be skipped** — `.lb-window` and `.lb-chrome` are prototype framing; in production the navbar mounts directly to the viewport.
3. **Navbar (rail mode)** — three states, theme toggle, localStorage persistence, smooth expand/collapse, Esc handling, backdrop.
4. **Bookmark mode** — hover-expand timer, full overlay, render-above-everything z-stacking. Mount it on `/jupyter/*` and `/grafana/*` routes (or set up the JupyterLab/Grafana proxies to inject it).
5. **Home page** — status data from backend (`GET /api/labs` style), then static content.
6. **Download page** — version/size/sha come from the build pipeline JSON; rest of the page is static + operator-editable Markdown body. The browser-block explainer copy is in the strings file — translate carefully, it's user-critical.
7. **Docs page** — Markdown rendering (gray-matter + remark or your choice), folder-built sidebar, EN/RU resolution, the 5 admonition flavors, code-block copy.

## Caveats

- The Russian translations in the strings file are designer-written. Have a native speaker review before shipping.
- The "outdated" pill threshold (which version counts as outdated) is product policy — the design just shows the state. Define the rule on the backend.
- The home page's "How it works" topology diagram is a sticky sidebar — make sure it doesn't sticky-fight with the page's sticky header. Current implementation lets the page-header win.
- The light-theme accent (`#1F3A8A`) is intentionally dark for high contrast. In dark mode the accent must be brightened (`#BCCBF2`) or any tweakable accent must be programmatically lightened — see the `lightenForDark` helper in `Lab Bridge.html`.
