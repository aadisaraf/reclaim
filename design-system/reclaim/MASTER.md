# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/reclaim/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** Reclaim
**Generated:** 2026-09-12 (hand-corrected from generator output — see note below)
**Category:** Internal ops console / audit-log dashboard
**Design Dials:** Variance 4/10 (Balanced) | Motion 3/10 (Subtle) | Density 7/10 (Standard)

**Note:** the generator's top-level `--design-system` query pattern-matched "healthcare" to a
*marketing landing page* pattern (Trust & Authority + Conversion: hero, proof, CTA, red/gold
palette, GSAP scroll-reveal). Reclaim is not a landing page — it's an internal case-review tool a
billing specialist stares at all day. The palette and typography below instead come from direct
`--domain color` / `--domain typography` queries for "enterprise dashboard" / "dashboard data",
which are the right category match. This file documents that substitution so a future session
doesn't regenerate over it and reintroduce the mismatch.

---

## Global Rules

### Color Palette

Light mode only (constitution: explainable simplicity, one laptop, no dark-mode requirement in
the spec). Neutral slate base — the UI must not compete with the semantic status colors below.

| Role | Hex | CSS Variable |
|------|-----|--------------|
| Primary | `#334155` | `--color-primary` |
| On Primary | `#FFFFFF` | `--color-on-primary` |
| Secondary | `#475569` | `--color-secondary` |
| Accent | `#059669` | `--color-accent` |
| On Accent | `#FFFFFF` | `--color-on-accent` |
| Background | `#F8FAFC` | `--color-background` |
| Foreground | `#0F172A` | `--color-foreground` |
| Card | `#FFFFFF` | `--color-card` |
| Card Foreground | `#0F172A` | `--color-card-foreground` |
| Muted | `#F2F3F4` | `--color-muted` |
| Muted Foreground | `#64748B` | `--color-muted-foreground` |
| Border | `#E6E8EA` | `--color-border` |
| Destructive | `#DC2626` | `--color-destructive` |
| On Destructive | `#FFFFFF` | `--color-on-destructive` |
| Ring | `#334155` | `--color-ring` |

**Color Notes:** Industrial slate + stock green (`--domain color`, "enterprise SaaS dashboard
neutral slate palette", Result 1 — "Inventory & Stock Management"). Chosen because it leaves the
status-badge palette below free to carry all the semantic meaning; nothing else on screen should
be a saturated color.

### Status Badge Colors

`CaseStatus` (per `contracts/app-api.openapi.yaml`) has 11 values. Group them into 4 semantic
buckets so a presenter can read the queue at a glance without memorizing 11 colors:

| Bucket | Statuses | Background | Text | CSS Variable prefix |
|---|---|---|---|---|
| Neutral / in progress | `new`, `claim-matched`, `evidence-gathered`, `approved` | `#F1F5F9` | `#334155` | `--status-progress-*` |
| Attention (amber) | `needs-review`, `needs-evidence` | `#FEF3C7` | `#92400E` | `--status-attention-*` |
| Success (green) | `ready-for-review`, `submitted`, `in-review`, `paid` | `#DCFCE7` | `#166534` | `--status-success-*` |
| Muted (gray, no action) | `other-denial` | `#F1F5F9` | `#64748B` | `--status-muted-*` |

Badges are pill-shaped, `font-weight: 600`, `font-size: 0.8125rem` (13px), never the only signal —
always paired with the status word itself as text, never color/icon alone (a11y + the constitution's
"explainable" requirement: nothing on screen should require decoding a color key).

### Typography

- **Heading / UI Font:** Fira Sans
- **Data / Code Font (monospace):** Fira Code — used for claim IDs, member IDs, NPIs, CPT/ICD
  codes, dollar amounts, dates, and anything copied verbatim from a record. This is the one
  deliberate, non-generic move: a claims record is mostly identifiers and codes, and setting them
  in a distinct monospace face makes "this value came from a specific field" visually legible
  before you even read the label.
- **Mood:** dashboard, data, precise, auditable
- **Google Fonts:** [Fira Sans + Fira Code](https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=Fira+Sans:wght@300;400;500;600;700&display=swap)

**CSS Import:**
```css
@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=Fira+Sans:wght@300;400;500;600;700&display=swap');
```

```css
--font-sans: 'Fira Sans', system-ui, sans-serif;
--font-mono: 'Fira Code', ui-monospace, 'SFMono-Regular', monospace;
```

Type scale (density 7/10 — standard, not spacious):

| Token | Size / Line-height | Usage |
|---|---|---|
| `--text-xs` | 12px / 16px | Timestamps, audit metadata |
| `--text-sm` | 13px / 20px | Table cells, badges, secondary text |
| `--text-base` | 14px / 22px | Body text, form labels |
| `--text-md` | 16px / 24px | Section headers within a tab |
| `--text-lg` | 20px / 28px | Case headline on the case page |
| `--text-xl` | 24px / 32px | Not used — this app has no marketing-scale type |

### Spacing Variables

*Density: 7/10 — Standard, dashboard-tight, not spacious.*

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | `4px` / `0.25rem` | Tight gaps (badge padding, icon gaps) |
| `--space-sm` | `8px` / `0.5rem` | Inline spacing, table cell padding |
| `--space-md` | `12px` / `0.75rem` | Standard component padding |
| `--space-lg` | `16px` / `1rem` | Card padding, section gaps |
| `--space-xl` | `24px` / `1.5rem` | Section margins |
| `--space-2xl` | `32px` / `2rem` | Page-level gaps |

No `--space-3xl` — this app has no hero sections.

### Shadow Depths

Flat by default. Reserve shadow for one level of elevation only (cards sitting on the page
background); never stack multiple shadow levels.

| Level | Value | Usage |
|-------|-------|-------|
| `--shadow-sm` | `0 1px 2px rgba(15,23,42,0.06)` | Card resting state |
| `--shadow-md` | `0 2px 8px rgba(15,23,42,0.08)` | Dropdowns, the persona picker menu |

No `--shadow-lg`/`--shadow-xl` — no modals in this app (approval is inline on the Packet tab).

---

## Component Specs

### Status Badge

```css
.badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-xs);
  padding: 2px 10px;
  border-radius: 999px;
  font-family: var(--font-sans);
  font-weight: 600;
  font-size: var(--text-sm);
  line-height: 20px;
  white-space: nowrap;
}
.badge-progress   { background: #F1F5F9; color: #334155; }
.badge-attention  { background: #FEF3C7; color: #92400E; }
.badge-success    { background: #DCFCE7; color: #166534; }
.badge-muted      { background: #F1F5F9; color: #64748B; }
```

### Buttons

```css
.btn-primary {
  background: var(--color-accent);
  color: var(--color-on-accent);
  padding: 8px 16px;
  border-radius: 6px;
  font-weight: 600;
  font-size: var(--text-sm);
  border: none;
  cursor: pointer;
  transition: background 150ms ease;
}
.btn-primary:hover:not(:disabled) { background: #047857; }
.btn-primary:disabled { background: var(--color-muted); color: var(--color-muted-foreground); cursor: not-allowed; }

.btn-secondary {
  background: var(--color-card);
  color: var(--color-foreground);
  border: 1px solid var(--color-border);
  padding: 8px 16px;
  border-radius: 6px;
  font-weight: 500;
  font-size: var(--text-sm);
  cursor: pointer;
  transition: border-color 150ms ease, background 150ms ease;
}
.btn-secondary:hover { background: var(--color-muted); border-color: var(--color-secondary); }

.btn-danger-outline {
  background: transparent;
  color: var(--color-destructive);
  border: 1px solid var(--color-destructive);
  padding: 8px 16px;
  border-radius: 6px;
  font-weight: 500;
  font-size: var(--text-sm);
  cursor: pointer;
}
```

### Cards / Tab Panels

No hover-lift, no transform — this is a document you read, not a product you browse.

```css
.card {
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: var(--space-lg);
  box-shadow: var(--shadow-sm);
}
```

### Tabs

```css
.tabs {
  display: flex;
  gap: var(--space-xs);
  border-bottom: 1px solid var(--color-border);
}
.tab {
  padding: 10px 16px;
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--color-muted-foreground);
  border-bottom: 2px solid transparent;
  cursor: pointer;
  transition: color 150ms ease, border-color 150ms ease;
}
.tab:hover { color: var(--color-foreground); }
.tab[aria-selected="true"] {
  color: var(--color-primary);
  border-bottom-color: var(--color-accent);
  font-weight: 600;
}
```

### Identifier / Code Text

```css
.code-value {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--color-foreground);
}
```

### Timeline Row

```css
.timeline-row {
  display: flex;
  gap: var(--space-md);
  padding: var(--space-sm) 0;
  border-bottom: 1px solid var(--color-border);
  font-size: var(--text-sm);
}
.timeline-row:last-child { border-bottom: none; }
```

### Inputs / Persona Picker

```css
.select {
  padding: 6px 12px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: var(--text-sm);
  background: var(--color-card);
  cursor: pointer;
}
.select:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px var(--color-ring);
}
```

### Synthetic Data Banner

Constitution I requires "SYNTHETIC DEMO DATA" visible on every screen and PDF. Treat it as a
permanent, unobtrusive strip, not an alert:

```css
.synthetic-banner {
  background: #FEF3C7;
  color: #92400E;
  font-size: var(--text-xs);
  font-weight: 600;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  padding: 4px var(--space-lg);
  text-align: center;
}
```

---

## Style Guidelines

**Style:** Explainable ops console — closer to a Stripe/Linear internal tool or a git-log viewer
than a product marketing site. Every screen should look like documentation of a decision, not a
pitch for one.

**Keywords:** dense, neutral, legible, monospace-for-data, no chrome, no hero, no CTA funnel.

**Best For:** case review, audit trails, claims/insurance ops, developer tools.

### Page Pattern (this app has exactly two page types)

1. **Queue page** (`/`): header banner → presenter action bar (Simulate remit / Missing-evidence
   toggle / Reset) → case list (status badge + headline, click-through) → paid/other-denial
   summary lines below the fold, visually de-emphasized (muted text, no badges).
2. **Case detail page** (`/cases/[caseId]`): header banner → case headline + top-level status line
   → tab bar (Identity, Evidence, Matrix, Packet, Timeline) → active tab panel as a `.card`.

No sidebar, no global nav beyond the header — there are only two routes.

---

## Motion

Motion dial is 3/10 (subtle) and the constitution explicitly forbids anything that looks like a
"framework" doing work the reader can't see. The only motion in this app:

1. **Matrix row reveal** (explicitly specified in tasks.md T085): when a policy requirement row
   flips from pending to satisfied, fade+color it in over 400ms. This is a state change the user
   should notice, not decoration.

```css
@media (prefers-reduced-motion: no-preference) {
  .matrix-row-satisfied {
    animation: matrix-row-in 400ms ease-out;
  }
}
@keyframes matrix-row-in {
  from { background-color: #FEF3C7; }
  to   { background-color: #DCFCE7; }
}
```

2. **Polling refresh**: no spinner-on-every-tick. Only show a small "Updating…" indicator the
   first time a page starts polling, then let content swap in place.

No GSAP, no ScrollTrigger, no scroll-reveal — this app has no scrolling marketing content, and
pulling in an animation library for a 2-page CRUD-ish dashboard would violate Constitution VII
(Explainable Simplicity: "no orchestration frameworks unless justified").

---

## Anti-Patterns (Do NOT Use)

- ❌ Hero + subtitle + CTA button anywhere — this app has no marketing surface
- ❌ Card hover-lift / `transform: translateY` on static content — nothing here is "browsable"
- ❌ Saturated primary color competing with the status-badge palette
- ❌ Color as the only status signal (always pair with the status word)
- ❌ GSAP/scroll-reveal or any animation library — not justified by Constitution VII
- ❌ Modals — every action (approve, rerun, reset) happens inline with a confirm, not a dialog
  overlay, except the native `confirm()` for "Reset demo" (destructive, needs a hard stop)
- ❌ Emojis as icons — use inline SVG (or plain text labels; this app can ship with zero icons)
- ❌ AI purple/pink gradients
- ❌ Rounded-2xl / heavy shadow on every surface — this is a document, not a landing card

---

## Pre-Delivery Checklist

- [ ] "SYNTHETIC DEMO DATA" visible on every page (banner) and every PDF (footer)
- [ ] Every status badge shows both color and the status word as text
- [ ] `cursor-pointer` on all clickable elements
- [ ] Focus states visible for keyboard navigation (`:focus-visible`, ring token)
- [ ] Text contrast 4.5:1 minimum (all pairs above chosen to clear this)
- [ ] `prefers-reduced-motion` respected (the one animation is gated on it)
- [ ] Responsive down to 375px (presenter may demo from a laptop trackpad, not a phone, but must
  not break if resized)
- [ ] No secret values (`OPENAI_API_KEY`, `PAYER_TOKEN`, etc.) ever rendered in the DOM
- [ ] Never render the word "Submitted" without a real `submission.appealId` present (FR from
  Constitution V — this is a UI correctness rule, not just a style rule)
