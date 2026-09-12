<!--
Sync Impact Report
==================
Version change: (unversioned template) → 1.0.0
Bump rationale: initial ratification; every placeholder replaced with project content.

Principles (template placeholder → ratified title):
- [PRINCIPLE_1_NAME] → I. Synthetic Data Only (NON-NEGOTIABLE)
- [PRINCIPLE_2_NAME] → II. Standards-Exact Interfaces
- [PRINCIPLE_3_NAME] → III. Identity Before Evidence (NON-NEGOTIABLE)
- [PRINCIPLE_4_NAME] → IV. Evidence Before Prose (NON-NEGOTIABLE)
- [PRINCIPLE_5_NAME] → V. Human Approval Before Submission (NON-NEGOTIABLE)
- (new) → VI. Adapters at Every Boundary
- (new) → VII. Explainable Simplicity
- (new) → VIII. Honest Verification

Sections:
- [SECTION_2_NAME] → Security and Privacy Posture
- [SECTION_3_NAME] → Scope Boundaries
- Added: Development Workflow
- Governance: filled in (amendment procedure, versioning policy, compliance review)
- Removed: none (template example comments dropped once replaced)

Clarifications drawn from docs/reclaim-speckit-prompts.md Appendix A:
- III: source segments for each identity check (A3 table); Encounter.period.start date
  check after the Encounter read (A3 lists it as a chart-side value); "clinical record
  requests" defined as the evidence searches and Binary reads (A5 call list).
- Scope Boundaries: paid claims in the 835 are ignored, as in A2 and A9.

Dependent templates (read the constitution at runtime; not modified by this command):
- .specify/templates/plan-template.md: "Constitution Check" gate and "Complexity Tracking"
  table are the enforcement points for Principle VII and Governance. No edit required.
- .specify/templates/spec-template.md, tasks-template.md, checklist-template.md:
  no edit required.

Deferred TODOs: none.
-->

# Reclaim Constitution

Reclaim is an evidence-first denial recovery agent. It is a hackathon demo that MUST also be
production-shaped: every boundary, format, and gate is the one a hospital would deploy, and
every shortcut is named as a shortcut.

## Core Principles

### I. Synthetic Data Only (NON-NEGOTIABLE)

- Every patient, member, claim, clinician, payer, policy, letter, and payer response MUST be
  invented from scratch. No real or "de-identified" records, ever.
- Every screen, generated document, and PDF MUST visibly say "SYNTHETIC DEMO DATA".
- Fixtures in `fixtures/` MUST be the only data source. There MUST be no upload path for real
  data.

**Rationale**: we show a real hospital workflow without touching PHI, and we say so out loud.

### II. Standards-Exact Interfaces

- Where a real standard exists we MUST use it for real:
  - X12 5010 835 (`005010X221A1`) and 837P (`005010X222A1`) text with full
    ISA/GS/ST/SE/GE/IEA envelopes and correct SE segment counts.
  - 835 balancing: billed minus paid equals adjustments at each level, and BPR02 equals
    total paid.
  - FHIR R4 resources and `searchset` Bundles with real field names, served as
    `application/fhir+json`.
- The X12 parser MUST read its delimiters from the ISA segment, tolerate line breaks between
  segments, read CAS at claim or service level, and handle REF, DTM, AMT, QTY, and LQ segments
  after SVC.
- Fixtures MUST pass automated validation tests before any feature code relies on them.
- Where no standard exists (payer portals) we MUST NOT pretend one does. The payer MUST be a
  clearly labelled mock behind an adapter with a documented contract.

**Rationale**: judges can check the formats; exact formats are what make "implementable
tomorrow" true.

### III. Identity Before Evidence (NON-NEGOTIABLE)

- The system MUST NEVER match a patient by name.
- Before any EHR request, the identity gate MUST confirm all six checks:
  1. 835 claim ID (CLP01) equals 837 claim ID (CLM01).
  2. 835 member ID (NM1*QC) equals 837 member ID (NM1*IL).
  3. Date of service matches (835 DTM*472 / DTM*232 against 837 DTP*472).
  4. Payer ID matches (835 REF*2U against 837 NM1*PR).
  5. Rendering provider NPI matches (835 NM1*82 against 837 NM1*82).
  6. Procedure code matches (835 SVC01 against 837 SV101).
- After the Encounter read, the date of `Encounter.period.start` MUST equal the date of service.
  After the Coverage read, `Coverage.subscriberId` MUST equal the member ID.
- Any mismatch or missing identifier MUST set the case to `needs-review` naming the failing
  field, and MUST produce zero clinical record requests for that case, provable from the audit
  log. Clinical record requests are the Condition, ServiceRequest, Procedure, DiagnosticReport,
  Observation, DocumentReference, MedicationRequest, and Binary requests. A failure in the
  pre-request gate MUST produce zero EHR requests of any kind, and a failed post-read check
  MUST stop all further EHR requests for the case.

**Rationale**: touching the wrong chart is the one mistake a hospital will not forgive.

### IV. Evidence Before Prose (NON-NEGOTIABLE)

- The evidence matrix MUST be built and verified before any appeal text is generated.
- Every citation MUST reference a resource fetched for this case, and every excerpt MUST appear
  verbatim in that resource or its Binary. A citation that fails verification MUST be
  discarded, and its requirement MUST be marked `missing` with the reason.
- Every factual statement in the appeal letter MUST cite at least one verified matrix row. Any
  uncited factual statement MUST block the packet.
- If any policy requirement is missing, the system MUST NOT draft an appeal. It MUST create
  exactly one targeted `clinical-evidence-request` task per missing requirement.
- The LLM MAY classify, extract, and phrase. It MUST NOT be the only check on any fact.

**Rationale**: this is the product. Letters are a commodity; verified evidence is not.

### V. Human Approval Before Submission (NON-NEGOTIABLE)

- The system MUST NOT send anything to a payer until a user with role
  `authorized-billing-user` approves a specific packet version that is `ready-for-review` with
  every requirement satisfied.
- The UI MUST NOT say "filed" or "submitted" until the payer adapter returns a confirmation ID.
- Every submission MUST send `Idempotency-Key: appeal-<caseId>-v<packetVersion>`, so retries
  never create duplicate appeals.

**Rationale**: appeals are legal correspondence; a person signs them.

### VI. Adapters at Every Boundary

- Each external system MUST sit behind one small interface:
  - `RemitInbox`: 835 delivery.
  - `ClaimArchive`: 837 lookup.
  - `EhrClient`: FHIR R4.
  - `PayerAdapter`: decision, documents, appeals, tracking.
  - `PolicyStore`: versioned policies selected by payer, plan type, state, procedure, and date
    of service.
  - `LlmClient`: live or replay.
- Mocks MUST implement the same interface and contract a production adapter would. Base URLs,
  tokens, and credentials MUST come from configuration, never code.
- Secrets (the OpenAI API key, mock tokens) MUST live only in a gitignored `.env`. They MUST
  NEVER appear in code, fixtures, LLM replay files, logs, audit events, docs, or commits, and a
  test MUST fail if `.env` is not ignored.

**Rationale**: this is the scale story. A new payer or EHR is a new adapter, not a rewrite. And
one of our earlier public repos leaked a `.env`; never again.

### VII. Explainable Simplicity

- Every module MUST be explainable by one teammate in under two minutes. A plain function
  pipeline MUST be preferred over frameworks.
- The following are forbidden unless `plan.md` justifies them in Complexity Tracking against a
  concrete demo need: agent or graph orchestration frameworks, message brokers, task queues,
  more than one database, Kubernetes, secret vaults, custom auth or password hashing.
- No dead code. Every module MUST be exercised by the demo path or a test. Unused code MUST be
  deleted, not commented out.
- Every pipeline step MUST write one human-readable audit event (what it read, what it decided,
  why) that the UI displays.

**Rationale**: the judges dock points for any part nobody on the team can explain.

### VIII. Honest Verification

- Every dependency MUST be declared in the lockfile. A clean clone MUST pass `make test` and
  start with `make demo`.
- Tests MUST NOT be circular: never assert a component's output against a snapshot produced by
  that same component. Expected values MUST come from Appendix A of
  `docs/reclaim-speckit-prompts.md` or be written by hand.
- These negative tests are required: identity mismatch for each field, forged citation, excerpt
  not in source, uncited statement, missing requirement, duplicate 835 delivery, duplicate
  submission, wrong approver role, submission after deadline.
- We MUST NOT claim accuracy numbers we did not measure. Demo claims MUST be limited to what
  tests prove.

**Rationale**: our last repo had missing dependencies and self-confirming tests; we are not
repeating that.

## Security and Privacy Posture

**Demo scope (what we build):**

- Synthetic data only (Principle I).
- Runs locally only.
- A persona picker replaces login. There are no passwords and no password hashing.
- Mock tokens for the mock EHR and mock payer, loaded from `.env` (Principle VI).
- LLM requests MUST set `store=false` and MUST send only the lookback-filtered evidence for the
  case, never the whole chart.

**Production requirements (what we state but do not build):**

- SMART Backend Services authorization (signed JWT client assertion) at the hospital's FHIR
  endpoint.
- A Business Associate Agreement and zero-data-retention terms with the LLM provider.
- Encryption at rest.
- HIPAA minimum necessary applied to every EHR read and every LLM request.
- Audit log retention.

The demo MUST NOT present any production requirement as built. Docs and the pitch MUST describe
these items as the production path.

## Scope Boundaries

- This release works medical-necessity denials (CARC 50) end to end.
- Other denials MUST be ingested and labelled with their lane but not worked.
- Paid claims in an 835 MUST be recognized and take no action.
- Corrected claims (837 frequency code 7) are out of scope.

A feature spec that works a lane other than CARC 50, or that touches corrected claims, is a
scope amendment and MUST go through Governance first.

## Development Workflow

- Work follows the Spec Kit flow: constitution → specify → clarify → plan → checklists → tasks
  → analyze → implement (phase by phase) → converge.
- `docs/reclaim-speckit-prompts.md` Appendix A is the source of truth for every identifier,
  code, date, amount, and endpoint. Appendix B lists mistakes from the last repo that MUST NOT
  recur. When a spec, plan, or task conflicts with Appendix A, work MUST stop and the conflict
  MUST be raised with the team.
- Commit after each task phase.
- `make test` MUST be green before every commit.
- `docs/explain/` MUST be updated whenever a pipeline step changes.

## Governance

- This constitution supersedes every other practice, guide, and prompt in the repository.
- Amendments MUST be made only via `/speckit-constitution`. Each amendment MUST update the Sync
  Impact Report and the version line below.
- Versioning follows semantic versioning:
  - MAJOR: a principle or governance rule is removed or redefined incompatibly.
  - MINOR: a principle or section is added, or guidance is materially expanded.
  - PATCH: clarifications, wording, and typo fixes with no semantic change.
- Compliance review:
  - Every `plan.md` MUST pass its Constitution Check gate before research and again after
    design.
  - Every item forbidden by Principle VII MUST be justified in that plan's Complexity Tracking
    table before use.
  - `/speckit-analyze` and `/speckit-converge` MUST treat any violation of this constitution as
    CRITICAL.

**Version**: 1.0.0 | **Ratified**: 2026-09-12 | **Last Amended**: 2026-09-12
