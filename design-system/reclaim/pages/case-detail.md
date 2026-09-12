# Page override: Case Detail (`web/app/cases/[caseId]/`)

Overrides `../MASTER.md` for this page only.

## What was cloned, and what wasn't

The user supplied a reference CRM screenshot (a "Deal" detail view: dark global sidebar, a
left contact-profile panel with avatar/quick-actions/last-activity/key-facts, a tabbed main
panel with a stat-card row, and a document list with colored file-type icons and
accept/reject-style status circles) and asked to clone it for part of this dashboard.

**Cloned faithfully** (because Reclaim has a real equivalent for it):
- Two-column shell: a sticky left summary panel + tabbed right content (`.case-shell`,
  `.summary-panel` in globals.css).
- Left panel: avatar circle (colored by case-status bucket), quick actions ("Copy claim ID",
  "Denial letter" — real actions, not placeholders), "Last activity" from the real audit
  timeline, a key-facts list (payer claim ID, billed amount, denial reason, deadline, policy —
  all real `CaseDetail` fields), and the re-run control moved here from the old inline header.
- Breadcrumb above the shell (`Case queue / <hospitalClaimId>`).
- Stat-card row pattern (`StatCards.tsx`) — used on the Evidence tab (Included / Excluded /
  Medications found) and the Matrix tab (policy criteria satisfied, `X/Y`).
- Document-row pattern (`.doc-row`, `.doc-icon`) — used on the Evidence tab: a colored
  file-type-abbreviation square, a name/meta two-line block, and a check/x status circle.
- Check-circle / x-circle iconography (`components/icons.tsx`) replacing text-only
  Passed/Failed badges on the Identity and Matrix tabs — icon always paired with the status
  word, never icon-only (a11y, and this app's own rule that color/icon can never be the only
  signal).

**Deliberately NOT cloned** (because this app has no real equivalent, and faking one would be
dishonest UI — Constitution VII "no dead code", and the broader "never render information the
data doesn't support" principle that already governs this app's correctness rules):
- The dark global sidebar with app-wide nav (Overview/Contacts/Deals/Integration/Tasks/
  Settings/Help). Reclaim has exactly two routes (`/` and `/cases/[caseId]`); a decorative
  sidebar with links to screens that don't exist would be worse than no sidebar.
- "Add Member" / avatar-stack of team members — there's no multi-user assignment concept in
  this app's data model.
- "Add Template" / "Convert to PDF" / sub-tabs like "Portal Milestones" on the document list —
  no backing capability exists for any of these; the Evidence tab's items are pipeline-fetched,
  not user-uploaded or user-editable (Constitution I: no upload path at all).
- Interactive per-document accept/reject clicking — in the reference this looks like a reviewer
  action; in Reclaim, `EvidenceItem.included` is a deterministic pipeline decision (the lookback
  window), not a human judgment call, so the status icon is read-only.

## New shared primitives (Layer 3 tokens, not page-specific)

- `web/app/components/icons.tsx` — `CheckCircleIcon`, `XCircleIcon`, `AlertCircleIcon`,
  `DocumentStackIcon`, `MailIcon`, `CopyIcon`, `MoreIcon`. Inline SVG, sized via `size` prop.
  This is the only icon source in the app — no icon library dependency.
- `web/app/components/StatCards.tsx` — generic `{ stats: StatCardSpec[] }` stat-card row.
- CSS additions in `web/app/globals.css`: `.breadcrumb`, `.case-shell`, `.summary-panel`,
  `.avatar-circle` (+ `.bucket-*` status variants), `.icon-action-row` / `.icon-action-btn`,
  `.summary-facts`, `.stat-card-row` / `.stat-card`, `.doc-row` / `.doc-icon` / `.doc-meta` /
  `.doc-name` / `.doc-sub` / `.doc-status-icon`.

## Files touched for this page

`web/app/cases/[caseId]/page.tsx`, `CaseSummaryPanel.tsx` (new), `EvidenceTab.tsx`,
`MatrixTab.tsx`, `PacketTab.tsx`, `IdentityTab.tsx`, `TimelineTab.tsx`, plus the two new shared
component files and the globals.css additions above.
