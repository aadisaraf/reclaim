# Feature Specification: Reclaim Evidence-First Denial Recovery

**Feature Branch**: `001-denial-recovery`

**Created**: 2026-09-12

**Status**: Draft

**Input**: User description: "Reclaim: evidence-first denial recovery for medical-necessity denials. Exact demo values (claim IDs, member IDs, codes, dates, amounts, record IDs, on-screen text) are in docs/reclaim-speckit-prompts.md Appendix A. Use them verbatim in acceptance scenarios." (Full description: problem, users, 8 user stories, cross-cutting requirements, out of scope, and success criteria as supplied to `/speckit-specify`.)

**Source of truth**: every identifier, code, date, amount, record ID, and on-screen string below
comes from `docs/reclaim-speckit-prompts.md` Appendix A (sections A2 to A9). If this spec and
Appendix A ever disagree, Appendix A wins and the conflict is raised with the team.

## Problem

Hospitals lose money when insurers deny claims. Staff do four slow manual jobs: notice the
denial; find the original claim and the correct patient visit; dig through notes, orders, and
reports to see whether the insurer was wrong; then write and submit an appeal before the
deadline. Existing tools mostly help with the last job. Reclaim automates the investigation: it
turns a denial stream into a verified, source-cited appeal case and isolates the exact evidence
gap before an employee hunts through charts.

## Users

- **Billing specialist** (persona `billing-approver-01`, role `authorized-billing-user`): watches
  the denial queue, reviews packets, approves submission.
- **Treating clinician** (persona for Sam Lee, role `treating-clinician`): receives one targeted
  question, only when evidence is missing. Cannot approve or submit.
- **Demo presenter**: runs the scripted demo, flips the missing-evidence toggle, and resets the
  demo. Cannot approve or submit.

## Clarifications

### Session 2026-09-12

- Q: In the demo script, missing-evidence mode (step 7) follows submission (step 6). What does
  Re-run do on a case that has already been submitted? → A: Re-run is available only for cases
  that have not been submitted. Step 7 runs as: Reset, missing-evidence toggle on, "Simulate
  incoming remit", open the case. The main run keeps packet v1 and key `appeal-case-100028-v1`.
- Q: Claim details in the letter come from the remittance, original claim, and payer decision,
  not the evidence matrix. How does the citation rule apply to them? → A: Claim details sit in a
  structured letter header copied directly from the verified case record, never written by AI;
  selecting a header field shows its source record. The rule "every factual statement cites at
  least one verified matrix row" applies to every factual statement in the letter body.

## User Scenarios & Testing *(mandatory)*

The demo proves the stories in this order. Stories 1 to 6 together are the core demo path; each
is independently testable against fixed synthetic inputs.

### User Story 1 - A denial arrives on its own (Priority: P1)

The presenter presses "Simulate incoming remit". A remittance file lands in the clearinghouse
inbox (never a manual upload). Reclaim notices it, reads every claim in it, and within seconds a
$4,800 medical-necessity denial appears in the queue. The other claims in the same file are
handled correctly: the paid claim creates no work, and the missing-information denial is
labelled and left alone.

**Why this priority**: noticing the denial is the first manual job Reclaim removes. Nothing else
in the pipeline can start without it.

**Independent Test**: deliver `era-2026-09-12.835` to an empty inbox and check the queue, the
labels, the timeline, and that no chart data was requested for any claim other than the hero
claim.

**Acceptance Scenarios**:

1. **Given** a clean demo with an empty queue, **When** the presenter presses "Simulate incoming
   remit", **Then** `era-2026-09-12.835` is delivered to the clearinghouse inbox and a new case
   `case-100028` appears showing "Northstar Health · CO-50 Medical necessity · $4,800" for
   hospital claim `HSP-CLM-100028` (payer claim `PAYER-CLM-99281`), with status "new".
2. **Given** the same delivery, **When** the queue is displayed, **Then** it shows "1 paid claim,
   no action" for `HSP-CLM-100031` ($350 billed, $280 paid) and creates no work for it.
3. **Given** the same delivery, **When** the queue is displayed, **Then** it shows "1 other denial
   lane: not handled in this demo", and claim `HSP-CLM-100035` (CO-16, $620) is labelled "Other
   denial lane: not handled in this demo" with zero chart requests recorded for it.
4. **Given** `era-2026-09-12.835` has already been processed, **When** the same file is delivered
   again, **Then** no new cases are created and the timeline records that the file was already
   processed.

---

### User Story 2 - It resolves the denial to the exact claim and visit (Priority: P1)

For the medical-necessity denial, Reclaim finds the original claim the hospital sent and the
patient visit it billed for, and proves they belong together using identifiers only, never the
patient's name.

**Why this priority**: touching the wrong chart is the one mistake a hospital will not forgive.
No evidence may be gathered until identity is proven.

**Independent Test**: run the hero case and check the six passed checks; then run six variants
of the original claim, each with exactly one field changed, and check each lands in "Needs
review" naming that field with zero clinical record requests on the timeline.

**Acceptance Scenarios**:

1. **Given** case `case-100028`, **When** the billing specialist opens it, **Then** the screen
   shows `HSP-CLM-100028` → original claim `HSP-CLM-100028` → encounter
   `encounter-20260810-42`, with these 6 identity checks marked passed:

   | Check | Remittance value | Original claim value |
   |---|---|---|
   | Claim ID | `HSP-CLM-100028` | `HSP-CLM-100028` |
   | Member ID | `MEMBER-448820` | `MEMBER-448820` |
   | Date of service | 2026-08-10 | 2026-08-10 |
   | Payer | `NSTHLTH01` | `NSTHLTH01` |
   | Rendering provider NPI | `1234567893` | `1234567893` |
   | Procedure | CPT `72148` | CPT `72148` |

2. **Given** the checks above pass, **When** the encounter and coverage records are read,
   **Then** the encounter date (2026-08-10) matches the date of service and the coverage
   subscriber ID (`MEMBER-448820`) matches the member ID, and both checks are shown as passed.
3. **Given** an original claim identical to the hero claim except for one of the six fields,
   **When** the case is processed, **Then** the case status is "Needs review", the screen names
   the failing field, and the timeline shows zero record requests of any kind to the hospital's
   clinical system for that case.
4. **Given** the six pre-request checks pass but the coverage subscriber ID differs from
   `MEMBER-448820`, **When** the coverage record is read, **Then** the case becomes "Needs review"
   naming the member ID check, and no diagnosis, order, procedure, report, observation, note,
   medication, or document-content requests are made.
5. **Given** the remittance lacks one of the six identifiers, **When** the case is processed,
   **Then** the case is "Needs review" naming the missing field, with zero clinical record
   requests.

---

### User Story 3 - It gathers only relevant evidence (Priority: P1)

Once identity is proven, Reclaim reads the patient's clinical records for the visit and keeps
only those inside the policy's lookback window, showing where each item came from and what it
left out.

**Why this priority**: this is the chart hunt staff do by hand today. Limiting it to relevant
records keeps the case small, fast to review, and minimum-necessary.

**Independent Test**: after identity passes for the hero case, check the evidence list, the
source and date on every item, the exclusion count, and the empty medication result.

**Acceptance Scenarios**:

1. **Given** identity passed for `case-100028`, **When** the billing specialist opens the Evidence
   tab, **Then** it lists, each with source record and date: coverage `coverage-0042` (Commercial
   PPO); diagnosis `condition-100` (ICD-10-CM `M54.16`, 2026-05-28); order `order-901`
   (2026-08-10); procedure `procedure-902` (2026-08-10); lumbar spine X-ray report
   `report-xr-555` (2026-05-28); pain score `obs-pain-7781` (value 8, 2026-08-10); progress note
   `note-progress-031` (2026-08-10); and physical therapy discharge summary `treatment-note-022`
   (2026-07-14).
2. **Given** the lookback window is 2026-02-10 to 2026-08-10, **When** evidence is filtered,
   **Then** `note-ortho-2019-004` (2019-03-02) is excluded and the screen shows "1 record excluded
   (outside 6-month lookback)".
3. **Given** the medication search returns no records, **When** the Evidence tab is shown,
   **Then** it displays "MedicationRequest: 0 found" rather than hiding the search.

---

### User Story 4 - It tests the evidence against the payer's own rules (Priority: P1)

Reclaim fetches the payer's decision on the claim, selects the payer policy that applies to this
payer, plan, state, procedure, and service date, and fills a requirement-by-requirement evidence
matrix. A requirement is satisfied only by a cited excerpt that has been checked word for word
against a record fetched for this case.

**Why this priority**: this is the product. Letters are a commodity; verified evidence is not.

**Independent Test**: for the hero case, check the payer decision fields, the selected policy and
version, and that each of R1, R2, R3 turns green only with a verified excerpt. Then submit a
forged citation and a paraphrased excerpt and check both are rejected.

**Acceptance Scenarios**:

1. **Given** identity passed for `case-100028`, **When** the payer decision is fetched, **Then**
   the case shows decision "denied", decision date 2026-08-20, reason CO-50 "Insufficient
   documentation of medical necessity", appeal deadline 2026-10-19, allowed channels portal and
   fax, and the denial letter `denial-letter-99281` can be opened.
2. **Given** payer `NSTHLTH01`, plan Commercial PPO, state WA, procedure `72148`, and date of
   service 2026-08-10, **When** the policy is selected, **Then** the Matrix tab shows "Policy
   NST-IMG-2026-04 v2026.04" titled "Advanced imaging of the lumbar spine (SYNTHETIC)".
3. **Given** the full evidence set, **When** the matrix is built, **Then** R1, R2, and R3 turn
   green one by one: R1 cites `condition-100` and `note-progress-031`; R2 cites
   `treatment-note-022`; R3 cites `order-901`; every excerpt is an exact passage from its record,
   and the summary reads 3 of 3 satisfied.
4. **Given** a proposed citation to a record that was not fetched for this case, **When** it is
   verified, **Then** it is discarded, and if no other verified citation supports that
   requirement, the requirement shows "missing" with the reason.
5. **Given** a proposed excerpt that does not appear word for word in its cited record, **When**
   it is verified, **Then** it is discarded and handled as in scenario 4.
6. **Given** a payer, plan type, state, procedure, or service date that no policy covers,
   **When** policy selection runs, **Then** no policy is selected, no matrix or appeal is
   produced, and the timeline says why.

---

### User Story 5 - It generates a cited appeal packet (Priority: P1)

With every requirement satisfied, Reclaim drafts an appeal letter in which each factual
statement is tied to the requirement and excerpt that proves it, and assembles the full packet
for human review.

**Why this priority**: the packet is what recovers the money, and citations are what let a
reviewer trust it in minutes instead of re-reading the chart.

**Independent Test**: for the hero case, check the four status lines, select each letter body
statement and each header field and confirm what is highlighted, check the packet contents
against the Appendix A list, and confirm an uncited factual statement blocks the packet.

**Acceptance Scenarios**:

1. **Given** R1, R2, and R3 are satisfied, **When** the billing specialist opens the Packet tab,
   **Then** it shows "Ready for review", "Evidence completeness: 3/3 policy criteria satisfied",
   "Appeal deadline: October 19, 2026 (37 days left)", and "Expected recovery: $4,800".
2. **Given** the ready packet, **When** the billing specialist selects any factual statement in
   the letter body, **Then** the policy requirement and the chart excerpt behind it are
   highlighted.
3. **Given** the ready packet, **When** the billing specialist selects a field in the letter
   header (for example claim `HSP-CLM-100028` or amount $4,800), **Then** the case record it was
   copied from is shown (the remittance, original claim, or payer decision).
4. **Given** the ready packet, **When** its contents are listed, **Then** it contains: hospital
   claim `HSP-CLM-100028` and payer claim `PAYER-CLM-99281`; patient and member identifiers
   (`MRN-0042`, `MEMBER-448820`); procedure `72148`, diagnosis `M54.16`, rendering provider
   `1234567893`, service date 2026-08-10, amount $4,800; the stated denial reason; policy
   `NST-IMG-2026-04` version 2026.04; requirement-by-requirement citations; the requested action
   "reconsider and reprocess payment"; the attachment list (`note-progress-031`,
   `treatment-note-022`, `order-901`, `policy-snapshot-NST-IMG-2026-04`); the required human
   approver; the packet version (v1); and a "SYNTHETIC DEMO DATA" footer.
5. **Given** a draft letter whose body contains a factual statement with no verified citation,
   **When** the packet is checked, **Then** the packet is blocked, is not "Ready for review", and
   the uncited statement is identified.

---

### User Story 6 - A human approves, the system submits, and tracking begins (Priority: P1)

The billing specialist approves one specific packet version. Only then does Reclaim send the
letter and attachments to the payer and file the appeal. The case shows the payer's
confirmation and then follows the appeal's status.

**Why this priority**: appeals are legal correspondence; a person signs them. Recovery only
counts once the payer confirms receipt.

**Independent Test**: approve and submit the hero packet as `billing-approver-01` and check
the confirmation and tracking; repeat the submission and confirm no second appeal; attempt
approval as another persona and confirm refusal.

**Acceptance Scenarios**:

1. **Given** packet v1 for `case-100028` is "Ready for review", **When** `billing-approver-01`
   presses "Approve and submit", **Then** the letter and attachments reach the payer, and the
   case shows "Submitted · Northstar confirmation NST-APL-80126 · expected resolution 14 days"
   only after the payer returns that confirmation.
2. **Given** the appeal was received, **When** 30 seconds pass, **Then** the case shows "In
   review" from the payer's tracking status.
3. **Given** packet v1 was already submitted, **When** the same submission is sent again (retry
   or second click), **Then** the payer holds exactly one appeal for the case and the case shows
   the same confirmation `NST-APL-80126`.
4. **Given** the treating clinician or presenter persona is active, **When** they try to approve
   the packet, **Then** approval is refused, nothing is sent to the payer, and the timeline
   records the refusal.
5. **Given** the payer's appeal deadline has passed relative to the demo date, **When**
   submission is attempted, **Then** the case never shows "Submitted" and displays the payer's
   reason that the appeal window is closed.
6. **Given** the payer has not yet returned a confirmation, **When** the case is displayed,
   **Then** no screen uses the words "filed" or "submitted" for it.

---

### User Story 7 - Missing-evidence mode (Priority: P2)

A presenter toggle hides the physical therapy note so the audience sees what happens when the
chart lacks a required item: Reclaim names the exact gap, drafts nothing, blocks submission, and
sends one targeted question to the treating clinician.

**Why this priority**: isolating the exact evidence gap is half of the pitch, but the core path
(stories 1 to 6) must work first.

Because a submitted appeal cannot be undone, missing-evidence mode always runs on a case that
has not been submitted. In the demo script, step 7 runs as: Reset, toggle on, "Simulate incoming
remit", open the case.

**Independent Test**: from a clean demo, turn the toggle on, simulate the incoming remit, and
check the status line, the red R2 row and reason, the absence of a letter, the disabled
approval, and the single clinician request. Turn it off, re-run, and check the ready packet
returns.

**Acceptance Scenarios**:

1. **Given** a case that has not been submitted and the missing-evidence toggle is on, **When**
   the case is processed (by "Simulate incoming remit" after a reset, or by "Re-run"), **Then**
   it shows "Needs 1 item", the summary reads 2 of 3 satisfied, and R2 is red with reason "No
   DocumentReference or MedicationRequest in the lookback window documents a 6-week conservative
   treatment trial".
2. **Given** the same state, **When** the Packet tab is opened, **Then** no appeal letter exists
   and approval and submission are disabled.
3. **Given** the same state, **When** tasks are listed, **Then** exactly one request exists:
   `task-case-100028-R2`, a clinical evidence request for requirement R2 assigned to the treating
   clinician, asking: "The policy requires documentation of prior conservative treatment. Please
   identify the relevant note or provide a factual attestation." with status "open".
4. **Given** the toggle is turned off, **When** the case is re-run, **Then** R2 is satisfied
   again, the case returns to "Ready for review" with 3/3, and the R2 request is closed with a
   note that the requirement is now satisfied.
5. **Given** a case whose appeal the payer has confirmed, **When** the presenter views it,
   **Then** "Re-run" is unavailable, the screen explains that a submitted appeal cannot be
   re-run and that the demo must be reset first, and the submitted appeal is unchanged.

---

### User Story 8 - Demo operations (Priority: P3)

The presenter can return the whole demo to a clean state with one action, and the audience can
always see whether AI responses are live or replayed and which fixed date the demo runs on.

**Why this priority**: it makes the demo repeatable and honest, but adds no recovery capability.

**Independent Test**: complete the demo, press reset, and confirm the queue, inbox, tasks,
packets, submissions, and timeline are empty and the payer accepts a fresh submission; check the
header on every screen.

**Acceptance Scenarios**:

1. **Given** a demo with cases, tasks, a submitted appeal, and the toggle on, **When** the
   presenter presses reset, **Then** the inbox, queue, cases, tasks, packets, submissions, payer
   appeal records, and timeline are cleared and the missing-evidence toggle is off.
2. **Given** any screen, **When** it is displayed, **Then** it shows "SYNTHETIC DEMO DATA", "Demo
   date: 2026-09-12", and either "AI: live" or "AI: replay" matching the active mode.
3. **Given** replay mode, **When** the hero case runs, **Then** every AI response used comes from
   a recording of a real live run, and the case reaches the same outcome as in live mode.

---

### Edge Cases

- **Same file delivered twice**: no duplicate cases; the timeline records the repeat delivery.
- **One identity field differs or is missing** (claim ID, member ID, date of service, payer,
  rendering NPI, procedure): "Needs review" naming that field; zero requests to the clinical
  record system; no automatic retry.
- **Coverage subscriber ID or encounter date disagrees after being read**: "Needs review" naming
  the field; no further clinical record requests.
- **Forged citation or excerpt not word for word in its source**: discarded; requirement marked
  missing with the reason if nothing else supports it.
- **Uncited factual statement in the letter**: packet blocked.
- **Wrong approver role**: approval refused; nothing reaches the payer.
- **Duplicate submission**: exactly one appeal at the payer; the same confirmation is shown.
- **Submission after the appeal deadline**: payer refuses; the case is not shown as submitted.
- **Payer deadline disagrees with the policy window** (decision date plus 60 days): the payer's
  deadline is displayed and used, and a visible warning states both dates.
- **No matching policy** for payer, plan type, state, procedure, or service date: no matrix, no
  appeal; the timeline says which selector failed.
- **Denial in another lane** (for example CO-16): labelled, never worked, no chart access.
- **Paid claim**: recognized, no case work created.
- **Live AI unavailable or failing**: the step fails visibly on the timeline; nothing is invented;
  the system does not silently switch to replay.
- **Replay mode has no recording for a request**: the step fails visibly rather than using an
  unrelated recording.
- **A record that was fetched but falls outside the lookback window**: excluded from evidence,
  counted, and never cited.
- **Re-run requested on a submitted case**: unavailable; the submitted appeal is unchanged and
  the presenter is told to reset first.

## Requirements *(mandatory)*

### Functional Requirements

**Intake and lanes**

- **FR-001**: The system MUST pick up remittance files delivered to the clearinghouse inbox
  without any manual upload, and the demo MUST provide a "Simulate incoming remit" action that
  performs that delivery. There MUST be no path for uploading real data.
- **FR-002**: The system MUST read every claim in a remittance file and classify each as paid (no
  work), medical-necessity denial (CARC 50, worked end to end), or other denial lane (labelled,
  not worked).
- **FR-003**: The denial code MUST be formed as `<group>-<reason>` from the service-level
  adjustment when present, otherwise from the claim-level adjustment (for the hero claim:
  CO-50).
- **FR-004**: Other-lane denials MUST be labelled "Other denial lane: not handled in this demo"
  and MUST produce zero clinical record requests. The queue MUST summarize paid claims and
  other-lane denials with counts, as in "1 paid claim, no action" and "1 other denial lane: not
  handled in this demo".
- **FR-005**: Delivering a remittance file whose content was already processed MUST create no
  new cases. A claim that already has a case MUST NOT get a second case.

**Identity gate**

- **FR-006**: The system MUST NEVER match a patient by name.
- **FR-007**: Before any request to the hospital's clinical record system, the system MUST
  locate the original claim and confirm all six checks between the remittance and the original
  claim: claim ID, member ID, date of service, payer ID, rendering provider NPI, and procedure
  code.
- **FR-008**: After reading the encounter, the system MUST confirm the encounter date equals the
  date of service. After reading coverage, the system MUST confirm the coverage subscriber ID
  equals the member ID.
- **FR-009**: Any failed or missing identity check MUST set the case to "Needs review", name the
  failing field, and stop. A failure before the first clinical record request MUST result in zero
  requests of any kind; a failure after the encounter or coverage read MUST result in zero
  requests for diagnoses, orders, procedures, reports, observations, notes, medications, or
  document contents. The timeline MUST make the request count provable.
- **FR-010**: The system MUST NOT retry a failed identity match automatically. A needs-review
  case changes only when a person corrects the claim mapping.

**Evidence gathering**

- **FR-011**: After identity passes, the system MUST read the encounter, patient, coverage,
  diagnoses, orders, procedures, diagnostic reports, observations, clinical documents, and
  medication orders for the patient, plus the content of each clinical document inside the
  lookback window.
- **FR-012**: The system MUST keep only records dated within the policy's lookback window (for
  the hero case, 6 months: 2026-02-10 to 2026-08-10) plus the encounter itself, and MUST show how
  many records were excluded and why.
- **FR-013**: Every evidence item MUST show its source record and date. Searches that return
  nothing MUST be shown with a count of 0.

**Payer decision and policy**

- **FR-014**: The system MUST fetch and show the payer's decision for the claim: decision,
  decision date, reason code and text, appeal deadline, allowed submission channels, and the
  denial letter.
- **FR-015**: The system MUST select exactly one versioned payer policy matching payer, plan
  type, state, procedure, and date of service, and MUST show its ID and version. When none
  matches, the system MUST NOT build a matrix or draft an appeal and MUST say which selector
  failed.
- **FR-016**: The payer decision's appeal deadline MUST be the deadline of record. The system
  MUST also compute decision date plus the policy's appeal window and MUST show a warning naming
  both dates when they differ.
- **FR-017**: Deadlines MUST show days remaining counted from the fixed demo date, 2026-09-12.

**Evidence matrix**

- **FR-018**: The system MUST build and verify the evidence matrix before any appeal text is
  generated.
- **FR-019**: Each policy requirement MUST have status "satisfied" or "missing", and nothing else.
  A requirement is satisfied only when at least one citation is verified.
- **FR-020**: A citation MUST be verified only if it references a record fetched for this case
  and inside the lookback window, and its excerpt appears word for word in that record or its
  document content. A citation that fails verification MUST be discarded, and a requirement left
  without a verified citation MUST be marked missing with the reason.
- **FR-021**: AI MAY propose classifications, excerpts, and wording, but every fact AI proposes
  MUST pass a deterministic check before it is used; AI MUST NOT be the only check on any fact.

**Missing evidence**

- **FR-022**: If any requirement is missing, the system MUST NOT draft an appeal letter, MUST
  disable approval and submission, MUST show "Needs N item(s)" with N equal to the number of
  missing requirements, and MUST create exactly one clinical evidence request per missing
  requirement, assigned to the treating clinician and naming that requirement.
- **FR-023**: When a re-run finds a previously missing requirement satisfied, the system MUST
  close the matching open request with a note saying so.
- **FR-024**: The demo MUST provide a presenter toggle that hides the physical therapy note
  `treatment-note-022` from the clinical record system, and a "Re-run" action that processes the
  case again from the start. "Re-run" MUST be unavailable for any case whose appeal has been
  submitted.

**Appeal packet**

- **FR-025**: When every requirement is satisfied, the system MUST draft an appeal letter and
  assemble a packet containing every item listed in User Story 5, scenario 4.
- **FR-026**: The letter MUST have two parts. The header holds claim details (hospital and payer
  claim IDs, patient and member identifiers, procedure, diagnosis, provider, service date,
  amount, denial reason, policy ID and version), copied directly from the verified case record
  and never written by AI. The body holds the argument: every factual statement in the letter
  body MUST cite at least one verified matrix row, and any uncited factual statement MUST block
  the packet from "Ready for review".
- **FR-027**: Selecting a factual statement in the letter body MUST highlight the policy
  requirement and the chart excerpt that support it. Selecting a header field MUST show the case
  record it was copied from.
- **FR-028**: Each packet MUST carry a version (v1, v2, ...). Any change to a packet's content
  MUST create a new version. Approval and submission MUST each belong to exactly one version.

**Approval, submission, tracking**

- **FR-029**: Only a user with role `authorized-billing-user` MUST be able to approve, and only a
  packet version that is "Ready for review" with every requirement satisfied. Any other approval
  attempt MUST be refused and recorded.
- **FR-030**: The system MUST send nothing to the payer before approval. After approval it MUST
  deliver the letter and every attachment to the payer before filing the appeal that references
  them.
- **FR-031**: Every appeal submission MUST carry a key unique to the case and packet version (for
  the hero case, `appeal-case-100028-v1`) so that repeated submissions of the same version
  never create a second appeal.
- **FR-032**: The case MUST NOT be shown as "filed" or "submitted" until the payer returns a
  confirmation ID. The case MUST NOT be shown as "won" or "overturned" unless the payer reports
  that outcome. When the payer refuses a submission, the case MUST show the payer's reason.
- **FR-033**: After confirmation the case MUST move to tracking, show the confirmation ID and
  expected resolution time, and update its status from the payer ("received", then "in-review").

**Transparency and demo operations**

- **FR-034**: Every pipeline step MUST add one timeline entry to the case saying, in plain
  English, what it read, what it decided, and why.
- **FR-035**: Every screen, generated document, and PDF MUST visibly say "SYNTHETIC DEMO DATA".
  Every screen MUST show "Demo date: 2026-09-12" and "AI: live" or "AI: replay".
- **FR-036**: Replay mode MUST use only responses recorded from a real live run. The active mode
  MUST always be visible, and the system MUST NOT switch modes on its own.
- **FR-037**: A single reset action MUST return the demo to a clean state as described in User
  Story 8, scenario 1.
- **FR-038**: The demo MUST offer a persona picker (billing specialist `billing-approver-01`,
  treating clinician, presenter) in place of login.

**Standards**

- **FR-039**: Remittances and original claims MUST be standard X12 5010 835 and 837P
  transactions, clinical records MUST be FHIR R4 resources, and the payer MUST be a clearly
  labelled mock with a documented contract, as required by Constitution Principle II. All data
  MUST be synthetic fixtures (Principle I).

### Key Entities *(include if feature involves data)*

- **Remittance delivery**: one remittance file arriving in the clearinghouse inbox; identified by
  file name and content fingerprint; contains claim payment records.
- **Claim payment record**: one claim inside a remittance (hospital claim ID, payer claim ID,
  billed, paid, adjustments, member, provider, service date, procedure, lane).
- **Original claim**: the claim the hospital sent to the payer, found in the claim archive by
  hospital claim ID.
- **Case**: the unit of work for one denied claim; holds lane, identifiers, status (new, needs
  review, needs evidence, ready for review, submitted, in review, other lane), and its timeline.
- **Identity check**: one named comparison (field, remittance value, claim or chart value,
  passed or failed).
- **Evidence item**: one clinical record fetched for the case (type, record ID, date, source,
  included or excluded, exclusion reason).
- **Payer decision**: the payer's ruling on the claim (decision, dates, reason, deadline,
  channels, denial letter).
- **Payer policy**: a versioned rule set selected by payer, plan type, state, procedure, and
  service date; holds requirements, lookback months, and appeal window days.
- **Evidence matrix**: one row per policy requirement with status (satisfied or missing), reason
  when missing, and verified citations (record, document, date, exact excerpt).
- **Clinical evidence request**: a task naming one missing requirement, assigned to the treating
  clinician, with a question and an open or closed status.
- **Appeal packet**: a versioned bundle awaiting approval: a letter (a header copied from the case
  record plus a cited body), attachments, and citations.
- **Approval**: a named persona and role approving exactly one packet version.
- **Appeal submission**: the filing of one approved packet version with its idempotency key, the
  payer's confirmation ID, expected resolution time, and tracking status.
- **Timeline event**: a plain-English record of one pipeline step (what was read, what was
  decided, why).
- **Persona**: a demo identity with a role, chosen from the picker.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From remit arrival to "Ready for review" takes under 60 seconds with live AI and
  under 10 seconds with replayed AI.
- **SC-002**: 100% of factual statements in the appeal letter body cite at least one verified
  evidence item, and 100% of letter header fields match their source case record.
- **SC-003**: 0 clinical record requests are made for any case that fails an identity check,
  across all six field variants plus the coverage and encounter checks.
- **SC-004**: 0 duplicate cases result from repeated delivery of the same file, and 0 duplicate
  appeals result from repeated submission of the same packet version.
- **SC-005**: Missing-evidence mode produces exactly 1 targeted request naming the unmet
  requirement, and submission is blocked.
- **SC-006**: A presenter completes the 6-step demo in under 3 minutes without typing.
- **SC-007**: A reviewer can trace any factual statement in the letter body to its policy
  requirement and exact source excerpt, and any header field to its source record, with a single
  selection.
- **SC-008**: 0 screens show "filed", "submitted", or "won" without the matching payer response.
- **SC-009**: 100% of screens, generated documents, and PDFs show "SYNTHETIC DEMO DATA".

## Assumptions

- All data is synthetic and comes from the fixtures defined in Appendix A. The demo runs locally
  on a fixed demo date of 2026-09-12 so deadlines never drift.
- The hero case's appeal deadline, October 19, 2026, is the payer decision's deadline and agrees
  with decision date 2026-08-20 plus the policy's 60-day appeal window, so the demo shows no
  deadline warning.
- "Within seconds" for a new case to appear in the queue means under 5 seconds from delivery.
- The demo payer moves an appeal from "received" to "in-review" 30 seconds after submission and
  never reports a final outcome during the demo.
- The treating clinician's reply to an evidence request (attaching a note or attestation) is not
  part of this release; turning the toggle off and re-running stands in for it.
- A person corrects a needs-review claim mapping outside the demo path; the main demo never
  produces a needs-review case, and those scenarios run in tests.
- A later remittance for a claim that already has a case adds a timeline entry to that case
  rather than creating a new case.
- Reset clears demo state but keeps configuration such as the AI mode.
- "Expected recovery" is the denied amount on the claim.
- Out of scope: real patient data, real payer connections, corrected claims (837 frequency code
  7), working non-medical-necessity denials beyond labelling, real authentication, payment
  posting, and multi-tenant administration.
