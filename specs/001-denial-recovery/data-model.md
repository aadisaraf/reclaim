# Data Model: Reclaim Evidence-First Denial Recovery

This is the Phase 1 output for [plan.md](plan.md). It covers Pydantic models in
`src/reclaim/models.py`, SQLite tables in `src/reclaim/repo.py` (stdlib `sqlite3`, one file), and
the case status machine.

All example values come from Appendix A.

## 1. SQLite tables

JSON columns hold serialized Pydantic models. Every timestamp is UTC ISO-8601.

| Table | Key | Columns | Notes |
|---|---|---|---|
| `remit_files` | `sha256` PK | `file_name`, `received_at`, `status` (`processed` \| `rejected`), `reject_rule` (e.g. `X-04`), `claim_count` | Dedupe key is the content SHA-256 (FR-005). A repeat delivery adds only an audit event. |
| `cases` | `case_id` PK | `hospital_claim_id` UNIQUE, `lane`, `status`, `payer_claim_id`, `payer`, `payer_id`, `member_id`, `rendering_npi`, `procedure_code`, `date_of_service`, `denial_code`, `denial_reason`, `billed_amount`, `paid_amount`, `denied_amount`, `remit_file`, `remit_sha256`, `needs_review_field`, `last_error`, `running` (0/1), `created_at`, `updated_at` | One row per CLP. Paid and other-denial claims get rows too, with status `paid`/`other-denial`. `case_id` = `case-` + the numeric suffix of CLP01 (e.g. `case-100028`). |
| `step_outputs` | (`case_id`, `step`) PK | `output_json`, `created_at` | Latest typed output of each step. Re-run overwrites it. |
| `audit_events` | `id` autoincrement | `case_id` (NULL for inbox events), `step`, `summary` (plain English), `detail_json`, `ehr_requests_json` (list of `"GET /fhir/R4/..."`), `llm_usage_json` (NULL if no LLM), `created_at` | Exactly one event per step run (Constitution VII). `ehr_requests_json` proves the request counts required by FR-009. |
| `tasks` | `task_id` PK | `case_id`, `task_type`, `requirement_id`, `assignee_role`, `question`, `status` (`open` \| `closed`), `close_note`, `created_at`, `closed_at` | `task_id` = `task-<caseId>-<requirementId>`. |
| `packets` | (`case_id`, `version`) PK | `status` (`blocked` \| `ready-for-review` \| `approved` \| `submitted`), `content_sha256`, `letter_json`, `blocked_reason`, `html`, `pdf` BLOB, `approved_by`, `approved_role`, `approved_at` | See section 5 for versioning. |
| `submissions` | `idempotency_key` PK | `case_id`, `version`, `request_sha256`, `status` (`pending` \| `confirmed` \| `refused`), `appeal_id`, `received_at`, `expected_resolution_days`, `payer_status` (`received` \| `in-review`), `error_code`, `error_message`, `updated_at` | Key: `appeal-<caseId>-v<version>` (e.g. `appeal-case-100028-v1`). |
| `documents` | `document_id` PK | `case_id`, `document_type` (`appeal-letter` \| `clinical-note` \| `order` \| `policy-snapshot`), `content_type`, `bytes` BLOB, `sha256`, `uploaded_at` (NULL until the payer accepts) | These are the exact bytes sent to the payer, so a retry sends identical bytes. |

Reset (`POST /api/demo/reset`, `make reset`) deletes all rows in every table and keeps
configuration.

## 2. Core models (Pydantic v2)

**RemitClaim** is parsed from one 835 2100 loop:
- `hospital_claim_id`, `claim_status` (CLP02), `billed`, `paid`, `patient_responsibility`
- `claim_filing_indicator` (CLP06), `payer_claim_id`, `member_id`, `rendering_npi`
- `date_of_service`, `procedure` (`qualifier`, `code`)
- `adjustments: list[Adjustment(group, reason, amount, level)]`
- `denial_code`, `lane`

Member names are never modelled.

**Remit** holds the envelope info (`isa13`, `gs06`, `st02`, `usage`), `payer_name`, `payer_id`,
`payee_npi`, `production_date`, `payment_date`, `total_paid`, and `claims: list[RemitClaim]`.

**OriginalClaim** is parsed from an 837P:
- `hospital_claim_id`, `billed`, `frequency_code`
- `member_id`, `group_number`, `payer_id`
- `billing_npi`, `billing_state`, `rendering_npi`
- `procedure` (`qualifier`, `code`), `units`, `diagnosis_code` (normalized `M54.16`), `date_of_service`

**ClaimMapEntry** comes from `fixtures/claim-map.json`: `patientId`, `mrn`, `encounterId`,
`dateOfService`, `procedureCode`, `diagnosisCode`.

**IdentityCheck** records one comparison: `field`, `source_a`, `value_a`, `source_b`, `value_b`, `passed`.
- `field` is one of `claimId`, `memberId`, `dateOfService`, `payerId`, `renderingNpi`,
  `procedureCode` (pre-request) and `encounterDate`, `encounterSubject`, `coverageSubscriberId`
  (post-read).
- The UI shows the six pre-request checks, and the post-read checks under them.

**EvidenceItem** is one fetched record:
- `resource` (`"Condition/condition-100"`), `resource_type`, `date`, `source_url`
- `included`, `exclusion_reason` (`"outside 6-month lookback"` \| `"no date"`), `summary`
- `document` (`"Binary/note-progress-031"` or null), `text` (decoded Binary text, or null)

**EvidenceSet** holds:
- `items` and `excluded_count`
- `search_counts: dict[type, int]`, which includes `MedicationRequest: 0`
- `lookback_start`, `lookback_end`
- `coverage_plan_type` (`"Commercial PPO"`)

**PayerDecision** mirrors the A6 decision JSON.

**Policy** mirrors the A7 JSON. **PolicySelection** is `policy | None` plus `failed_selector`
(`payerId` \| `planType` \| `state` \| `procedureCode` \| `dateOfService`).

**Deadline** holds:
- `deadline_of_record` (payer `appealDeadline`)
- `policy_window_date` (`decisionDate + appealWindowDays`)
- `days_left` (from `DEMO_TODAY`)
- `warning` (null when the two dates agree; the hero case has no warning)

**Citation**: `citation_id` (e.g. `R1-C1`), `resource`, `document`, `date`, `excerpt`, `verified`,
`rejection_reason`.

**MatrixRow**: `requirement_id`, `status` (`satisfied` \| `missing`), `reason`,
`evidence: list[Citation]`. Only verified citations are kept in `evidence`; rejected ones go to
the audit event.

**EvidenceMatrix**: `case_id`, `policy_id`, `policy_version`, `summary {satisfied, total}`,
`requirements: list[MatrixRow]`. This is the A8 shape.

**LetterStatement**: `statement_id`, `text`, `requirement_ids`, `citation_ids`.

**Letter**:
- `header: list[HeaderField(label, value, source)]`, where `source` is one of `remit`, `claim837`,
  `payerDecision`, `claimMap`, `policy`
- `body: list[LetterStatement]`
- `requested_action`, `attachments`, `required_approver`, `version`, `footer`

**Persona**: `userId`, `role`. The two personas are `billing-approver-01` (role
`authorized-billing-user`) and `viewer-01` (role `viewer`).

**LlmUsage**: `input_tokens`, `cached_tokens`, `output_tokens`, `reasoning_tokens`, `usd`.

LLM output schemas (strict) are described in prose here; the Pydantic classes are written at
implementation time:
- **MatrixProposal** is `requirements[]`. Each entry is `{requirementId, status, reason: str|null,
  citations[]{resource, excerpt}}`.
- **LetterDraft** is `statements[]`. Each entry is `{text, requirementIds[], citationIds[]}`.

## 3. Validation rules

| Area | Rule | Source |
|---|---|---|
| X12 | Rules X-01 to X-13 in [contracts/x12-fixtures.md](contracts/x12-fixtures.md). A failing file is rejected and creates no cases. | II |
| Lane | CLP02=4 and reason 50 gives `medical-necessity`. CLP02=4 with another reason gives `other-denial`. CLP02 in 1/2/3 with paid > 0 gives `paid`. | FR-002 |
| Denial reason | Lookup table `{"50": "Medical necessity"}`, used only for display. Other lanes display the code. | A2 |
| Identity (pre-request) | Six equalities, exact string compare after normalization: dates to `YYYY-MM-DD`; procedure as `qualifier:code`. A value missing on either side fails with that field. Frequency code 7 fails with `claimFrequency`. | III, FR-007 |
| Identity (post-read) | `Encounter.period.start[:10]` = DOS; `Encounter.subject.reference` = `Patient/<patientId>`; `Coverage.subscriberId` = member ID. The first failure stops all EHR calls. | III, FR-008 |
| Lookback | Inclusive window `[DOS − lookbackMonths, DOS]`. Month subtraction clamps to the end of the month. Hero: 2026-02-10 to 2026-08-10. | FR-012 |
| Resource date | Condition `recordedDate` (fallback `onsetDateTime`); DiagnosticReport `effectiveDateTime` (fallback `issued`); Observation `effectiveDateTime`; ServiceRequest `authoredOn`; Procedure `performedDateTime` or `performedPeriod.start`; DocumentReference `date`; MedicationRequest `authoredOn`. Patient, Encounter, and Coverage are context and not date-filtered. | FR-012 |
| Binary fetch | Only for DocumentReferences inside the window. `content[0].attachment.url` = `Binary/<id>`, where the id matches the DocumentReference id. | A5 |
| Policy selection | Exactly one policy where `payerId` = 837 NM1*PR, `planType` = Coverage `class[type=plan].name`, the 837 N4 state is in `states`, `procedureCodes` contains the code, and `effectiveStart ≤ DOS ≤ effectiveEnd` (null = open). Zero or more than one match gives no policy plus the first failing selector. | FR-015 |
| Deadline | `deadline_of_record` = payer `appealDeadline`. A warning shows when it differs from `decisionDate + appealWindowDays`. `days_left` = deadline − `DEMO_TODAY` (hero: 37). | FR-016, FR-017 |
| Citation verified | (a) `resource` is in this case's included EvidenceItems; (b) its type is in the requirement's `evidenceTypes`; (c) `excerpt` is at least 12 characters and an exact, case-sensitive substring of the decoded Binary text (DocumentReference) or of some string value in the resource JSON (other types). | IV, FR-020 |
| Matrix | Exactly one row per policy requirement. `satisfied` needs at least 1 verified citation, otherwise the row is `missing` with a reason. The proposal's own `missing` reason is kept. If every citation was rejected, the reason is `"All proposed citations failed verification: <reasons>"`. | FR-019 |
| Letter body | Every statement has at least 1 `citation_id`, and every id exists in the verified matrix. Its `requirement_ids` must equal the requirements of its cited rows. Every requirement is covered by at least one statement. Any failure gives packet `blocked` with the failing statement text. | IV, FR-026 |
| Attachments | Deterministic list, in this order: cited DocumentReferences (Binary text as `text/plain`, type `clinical-note`), cited ServiceRequests (resource JSON, type `order`), then `policy-snapshot-<policyId>` (policy JSON, type `policy-snapshot`). The letter `appeal-letter-<claim number>` is the packet PDF. For the hero case the attachments are `note-progress-031`, `treatment-note-022`, `order-901`, `policy-snapshot-NST-IMG-2026-04`. Condition resources are cited in the letter but not attached. | A6, A8 |
| Approval | Persona role = `authorized-billing-user`; the packet version is the latest; packet status = `ready-for-review`; every matrix row is satisfied; case status = `ready-for-review`. | V, FR-029 |

## 4. Case status transitions

Statuses: `new`, `claim-matched`, `needs-review`, `evidence-gathered`, `needs-evidence`,
`ready-for-review`, `approved`, `submitted`, `in-review`, `paid`, `other-denial`.

| From | Step / action | Condition | To |
|---|---|---|---|
| — | `ingest` | CLP02=4, CARC 50 | `new` |
| — | `ingest` | paid claim | `paid` (terminal) |
| — | `ingest` | any other denial | `other-denial` (terminal) |
| `new` | `fetch_claim` | 837 not in archive, or 837 fails validation | `needs-review` (`needs_review_field` = `originalClaim`) |
| `new` | `fetch_claim` + `resolve_identity` | all six checks pass | `claim-matched` |
| `new` | `resolve_identity` | any check fails or is missing, or frequency code 7 | `needs-review` (field named) |
| `claim-matched` | `gather_evidence` | a post-read check fails | `needs-review` (field named) |
| `claim-matched` | `gather_evidence` | no policy matches (selected right after the Coverage read, because the lookback window needs `lookbackMonths`) | `needs-review` (selector name); no clinical record requests |
| `claim-matched` | `gather_evidence` | success | `evidence-gathered` |
| `evidence-gathered` | `payer_context` | payer 404 `claim_not_found` | `needs-review` (`payerClaimId`) |
| `evidence-gathered` | `payer_context` | success | `evidence-gathered` (unchanged) |
| `evidence-gathered` | `build_matrix` | any requirement missing | `needs-evidence` |
| `evidence-gathered` | `build_matrix` + `draft_packet` | all satisfied, letter verified | `ready-for-review` (packet status `ready-for-review`) |
| `evidence-gathered` | `draft_packet` | uncited statement | `evidence-gathered` (packet status `blocked`, reason shown) |
| `ready-for-review` | approve (human) | role and version checks pass | `approved` |
| `ready-for-review` | approve (human) | wrong role or stale version | unchanged; refusal audit event |
| `approved` | submit | payer returns `appealId` (201 or 200 replay) | `submitted` |
| `approved` | submit | payer 4xx (e.g. 422 `appeal_window_closed`) | `approved` (unchanged); submission `refused` with the payer code and message shown |
| `submitted` | `track` | payer status `in-review` | `in-review` |
| any non-terminal pre-submission status (`new` through `ready-for-review`, including `needs-review` and `needs-evidence`) | re-run (presenter) | not `approved`, `submitted`, `in-review`, `paid`, `other-denial` | `new`, then the pipeline runs again |

Rules:
- A step error (timeout, LLM failure, replay miss, 5xx after retry) leaves the status unchanged,
  sets `last_error`, writes that step's audit event with the error, and stops the run. No
  automatic retry.
- `running` = 1 from the start of a pipeline run to its end. The UI polls while it is set.
- The approve endpoint performs `ready-for-review → approved → submitted` in one request, with an
  audit event for each step. The UI never shows "Submitted" before the payer returns `appealId`
  (FR-032).
- `track` runs from the background poller every 5 s for cases in `submitted`. It writes one audit
  event when the status changes, not on every poll.

## 5. Packet versioning

- `content_sha256` = SHA-256 of canonical JSON `{letter_json, attachment ids and sha256s, policy_id, policy_version}`.
- If `draft_packet` produces a hash equal to the latest version's hash, that version is reused.
  Otherwise the version becomes `max(version) + 1`. The first packet is v1.
- Approval and submission point to exactly one `(case_id, version)` (FR-028).
- A `blocked` packet still takes a version number, so the blocked content stays inspectable.
- Main demo: the hero case produces v1, which gives key `appeal-case-100028-v1`. In
  missing-evidence mode no packet exists. Turning the toggle off and re-running creates v1.

## 6. Clinical evidence request tasks

- One task per `missing` requirement, keyed by `task-<caseId>-<requirementId>`. It is created
  when that row first goes missing.
- Fixed fields: `taskType` `clinical-evidence-request` and `assigneeRole` `treating-clinician`.
- `question` is the A8 text for R2: "The policy requires documentation of prior conservative
  treatment. Please identify the relevant note or provide a factual attestation."
  - For other requirements the question is `"The policy requires <requirement text>. Please
    identify the relevant note or provide a factual attestation."`
  - The R2 wording comes from a per-requirement question map in `src/reclaim/steps/build_matrix.py`.
    It covers R2 only; the template is the fallback.
- Re-run with the row still missing: the existing open task is kept and no duplicate is created.
- Re-run with the row now satisfied: the task is closed with
  `close_note` = `"Requirement R2 is now satisfied by a verified citation."`
- `needs-evidence` shows "Needs N item(s)", where N = the count of open tasks for the case.
