# Implementation Plan: Reclaim Evidence-First Denial Recovery

**Branch**: `001-denial-recovery` | **Date**: 2026-09-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-denial-recovery/spec.md`. Canonical values come
from `docs/reclaim-speckit-prompts.md` Appendix A.

## Summary

Reclaim watches a mock clearinghouse SFTP inbox for X12 835 remits. It classifies each claim and
works only CARC 50 medical-necessity denials. For each one it runs a single async pipeline
function with nine steps:

1. ingest
2. fetch_claim
3. resolve_identity
4. gather_evidence
5. payer_context
6. build_matrix
7. draft_packet
8. approve_and_submit (human)
9. track

What the pipeline does:
- Proves identity with six identifier checks before any FHIR request.
- Reads only the lookback-window evidence from a mock FHIR R4 hospital.
- Selects the versioned payer policy.
- Has the LLM propose an evidence matrix, which a deterministic verifier checks word for word.
- Drafts a cited letter only when every requirement is satisfied.
- Submits to a mock payer with an idempotency key, and only after an `authorized-billing-user`
  approves.

The whole run is one laptop: docker compose with 5 services, one SQLite file, and a Next.js UI
that polls once per second. The LLM is gpt-5.6-luna through the Responses API, with exactly 2
calls per happy case (1 in missing-evidence mode) and replay recordings for the demo.

## Technical Context

**Language/Version**: Python 3.12 (backend, mocks, scripts); TypeScript with Next.js 16.3 on
Node ≥ 20.9 (web).

**Primary Dependencies**:
- FastAPI, Pydantic v2, httpx, uvicorn
- paramiko 5 (SFTP)
- openai 3.13 (Responses API; note it depends on `httpx2`, see research §2)
- reportlab 5 (PDF)
- fhir.resources 8.3 R4B (tests only)
- `atmoz/sftp` image
- @playwright/test

Versions are pinned in `uv.lock` and `web/package-lock.json`.

**Storage**: one SQLite file (`.local/reclaim.db`) using stdlib `sqlite3` behind
`src/reclaim/repo.py`. Fixtures are files under `fixtures/`.

**Testing**: pytest with pytest-asyncio (Docker-free: mocks in-process through
`httpx.ASGITransport`, fake inbox and LLM), plus one Playwright smoke test against the compose
stack in replay mode. `make test` runs both.

**Target Platform**: a single developer laptop (macOS or Linux) with Docker Desktop. Local only;
not deployed.

**Project Type**: web application (API + pipeline) with two mock services and a web UI.

**Performance Goals**:
- Remit arrival to "Ready for review" in under 60 s live and under 10 s replay (SC-001).
- A new case appears in under 5 s.

**Constraints**:
- `DEMO_TODAY=2026-09-12`.
- Synthetic data only.
- `store=false`, 45 s LLM timeout, one 429/5xx retry.
- Secrets only in a gitignored `.env`.
- Every module explainable in under 2 minutes.

**Scale/Scope**:
- One remit file (3 claims) and one worked case, plus test variants.
- 2 UI pages and about 12 app endpoints.
- Team of 3 to 4.

No NEEDS CLARIFICATION remains; the research findings are in [research.md](research.md).

## Constitution Check

*GATE: must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Evidence in this plan |
|---|---|---|
| I. Synthetic Data Only | PASS | `fixtures/` is the only data source. "Simulate incoming remit" copies a committed fixture, and no upload endpoint exists ([app-api](contracts/app-api.openapi.yaml)). The layout header plus the PDF footer carry "SYNTHETIC DEMO DATA", and both mocks label themselves. |
| II. Standards-Exact Interfaces | PASS, with a note | X12 envelopes, SE counts, balancing, delimiters from ISA, and CAS at either level with REF/DTM/AMT/QTY/LQ after SVC are all covered by tests ([x12-fixtures](contracts/x12-fixtures.md)). FHIR R4 searchsets as `application/fhir+json` ([mock-hospital-fhir](contracts/mock-hospital-fhir.md)). The payer is a labelled mock with an OpenAPI contract. **Note**: automated FHIR validation uses R4B models, because fhir.resources has no R4 package. The two R4/R4B differences (Observation and DiagnosticReport `subject` targets) get hand-written checks. Mock hosts use http locally, not https (research §11). |
| III. Identity Before Evidence | PASS | `resolve_identity` runs the six checks before `gather_evidence` creates any EHR request. Post-read checks cover Encounter date and Coverage.subscriberId, plus Encounter.subject. `EhrClient.requests_made` is copied into every audit event, so "zero requests" can be proven. Tests: one per field, plus a missing identifier and each post-read check. No name matching: member names are never parsed into models. |
| IV. Evidence Before Prose | PASS, with a noted reading | `build_matrix` runs and verifies before `draft_packet`. The verifier drops citations that are unfetched, outside the window, of the wrong type, or non-verbatim. Missing gives one task per requirement and no draft. Every letter body statement must cite at least one verified citation, or the packet is blocked. **Noted reading**: letter header fields (claim IDs, amounts, codes) are copied data from the verified case record, not generated statements, so the citation rule applies to the body (spec Clarifications, FR-026). **Honest limit**: the verifier proves provenance (the excerpt exists verbatim in a record fetched for this case). Whether an excerpt *meets* a criterion (for example "at least 6 weeks") is the LLM's judgment, and a second check is the human approver, who sees each excerpt beside its requirement. **Recommend** `/speckit-constitution` PATCH 1.0.1 to write down the header reading before `/speckit-analyze`. |
| V. Human Approval Before Submission | PASS | The server checks role, latest version, and `ready-for-review` status. Nothing is sent to the payer before approval. The UI shows "Submitted" only after `appealId` returns. Key is `appeal-<caseId>-v<version>`. Tests: wrong role, duplicate submission, after deadline. |
| VI. Adapters at Every Boundary | PASS | Six Protocols ([adapters](contracts/adapters.md)). Real and fake implementations share them. All URLs and tokens come from config and `.env`. Secrets guard test: `.env` is git-ignored, and no API-key pattern appears under `fixtures/` (including llm-replay) or `docs/`. Replay files store outputs and usage only. |
| VII. Explainable Simplicity | PASS, with justified complexity | Uses none of the forbidden items: no orchestration framework, broker, task queue, second database, Kubernetes, vault, or custom auth. The pipeline is one async function, and the poller is one asyncio task. One audit event per step. The complexity that *is* added (SFTP container, two mock services, a separate Node web app) is justified below. The dead-code rule is enforced in tasks (a sweep before converge). |
| VIII. Honest Verification | PASS | Two lockfiles. A clean clone runs `make setup && make test && make demo`. Expected values are written by hand from Appendix A, with no self-generated snapshots. All nine required negative tests are listed in [quickstart](quickstart.md) §1. AI cost comes from measured usage, and caching savings are claimed only if `cached_tokens > 0` is logged. No accuracy numbers are claimed. |

**Gate result (pre-research)**: PASS. No unjustified violations.

**Re-check after Phase 1 design**: PASS.
- The design artifacts add nothing that the constitution forbids.
- Items added beyond the plan input are listed in research §14; each is small and tied to a
  requirement or test.
- The IV noted reading and the PATCH recommendation still stand.

## Project Structure

### Documentation (this feature)

```text
specs/001-denial-recovery/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── app-api.openapi.yaml
│   ├── mock-northstar-payer.openapi.yaml
│   ├── mock-hospital-fhir.md
│   ├── x12-fixtures.md
│   └── adapters.md
├── checklists/requirements.md
└── tasks.md              # /speckit-tasks (not created here)
```

### Source Code (repository root)

```text
pyproject.toml  uv.lock  Makefile  docker-compose.yml  Dockerfile  .env.example  .gitignore
src/reclaim/
├── main.py            # FastAPI app factory, adapter wiring, starts poller task
├── api.py             # app API routes (contracts/app-api.openapi.yaml)
├── config.py          # env + .env; DEMO_TODAY, base URLs, tokens, prices, efforts
├── models.py          # Pydantic models (data-model.md §2)
├── repo.py            # sqlite3 tables and queries
├── pipeline.py        # run_case(): steps in order, persist output + audit event each step
├── poller.py          # asyncio loop: inbox every 1 s, track every 5 s
├── steps/             # ingest, fetch_claim, resolve_identity, gather_evidence,
│                      # payer_context, build_matrix, draft_packet, approve_and_submit, track
├── x12/               # tokenizer.py, remit835.py, claim837.py, validate.py
├── verify.py          # citation and letter verifier (Constitution IV)
├── pdf.py             # reportlab packet renderer
├── demo.py            # simulate remit, toggle, reset (mocks' /_control)
├── prompts/           # build_matrix.py, draft_packet.py (instructions + output rules)
└── adapters/          # protocols.py, sftp.py, fhir.py, payer.py, policy.py, llm.py
mocks/
├── hospital/app.py    # FHIR R4 mock + /auth/token + /_control
└── northstar/app.py   # A6 payer mock + /_control
fixtures/
├── x12/               # era-2026-09-12.835, HSP-CLM-100028.837 (+ tests/ variants)
├── fhir/              # one JSON per resource (A5)
├── payer/             # payer-decision.json, denial-letter.pdf, appeal-response.json
├── policies/          # NST-IMG-2026-04.json
├── claim-map.json
└── llm-replay/        # recorded outputs + usage
scripts/               # make_denial_letter.py, record_replay.py
tests/
├── fakes.py
├── fixtures/          # X12 + FHIR fixture validation
├── unit/              # tokenizer, 835, 837, identity, lookback, verifier, policy, llm client, deadline
├── contract/          # mock-hospital, mock payer (A6), app API
├── integration/       # dedupe, hero happy path (fake LLM), missing-evidence path, needs-review
└── test_secrets_guard.py
web/
├── app/page.tsx                   # queue + presenter bar
├── app/cases/[caseId]/page.tsx    # Identity, Evidence, Matrix, Packet, Timeline tabs
├── lib/api.ts
├── e2e/demo.spec.ts               # Playwright 6-step smoke (replay)
└── Dockerfile
docs/explain/          # one page per pipeline step (updated when a step changes)
```

**Structure Decision**:
- One repo and one Python package (`src/reclaim`).
- Both mocks live in `mocks/` and share the root `Dockerfile` with the app; only the uvicorn
  target changes.
- The UI is a separate `web/` Next.js app.
- Compose services: `app`, `web`, `mock-clearinghouse`, `mock-hospital`, `mock-northstar-health`.

**Make targets**:
- `setup`: uv sync, npm ci, `.env` from example, SFTP host keys, Playwright browser.
- `test`: pytest, then the Playwright smoke test on the compose stack in replay mode.
- `demo`: `docker compose up -d --build --wait`, then seed.
- `reset`: `POST /api/demo/reset`.
- `record`: `scripts/record_replay.py` in live mode.

## Spec alignment notes (from plan conflicts; the user chose the recommended answers)

1. **A9 step 7 vs spec**: the spec won. A9 row 7 in `docs/reclaim-speckit-prompts.md` now reads
   "Reset demo, Missing-evidence toggle on, Simulate incoming remit, open the case". **Done.**
2. **Personas**: the plan uses two personas, `billing-approver-01` (authorized-billing-user) and
   `viewer-01` (read-only). Presenter controls work under any persona. `treating-clinician` is a
   task assignee role, not a login. **Spec lines to update** (not yet edited):
   - Users section, [spec.md:26](spec.md#L26): the treating clinician and presenter bullets.
   - US6 scenario 4, [spec.md:257](spec.md#L257): "treating clinician or presenter persona"
     becomes `viewer-01`.
   - FR-038, [spec.md:495](spec.md#L495): the picker lists `billing-approver-01` and `viewer-01`.
3. **Constitution IV header fields**: pass with the noted reading above. Recommend a PATCH to
   1.0.1 via `/speckit-constitution`.
4. **Local deviations from Appendix A** (flagged, not blockers): mock base URLs use http, not
   https (research §11). The live-mode R2 reason wording may vary; replay is checked against A8
   (research §4).

## Complexity Tracking

| Added complexity | Why needed (demo claim) | Simpler alternative rejected because |
|---|---|---|
| `mock-clearinghouse` SFTP container (`atmoz/sftp`, amd64 under emulation on Apple Silicon) | US1 / FR-001: "A denial arrives on its own. Never a manual upload." SFTP is how clearinghouses deliver 835s, so the `RemitInbox` adapter is the one a hospital would keep. | A watched local folder proves nothing about the transport, and the adapter swap would be untested. If emulation fails on a machine, swap in `drakkan/sftpgo` (research §6). |
| `mock-hospital` FastAPI service | US2/US3, Constitution III: "zero clinical record requests on identity failure" must be provable from real HTTP requests, with bearer auth and searchsets. | An in-process fixture loader makes no FHIR calls, so request counts, auth, and OperationOutcome handling would be fiction. |
| `mock-northstar-health` FastAPI service | US6, Constitution V: "Submitted only after the payer confirms; retries never duplicate". Idempotent replay (200), 409, and 422 must happen over HTTP against the A6 contract. | An in-process fake can't prove the `PayerAdapter` honors the HTTP contract (headers, multipart, error envelope). |
| Separate `web` Next.js service (second toolchain) | SC-006: a presenter clicks the 6-step demo with live polling and no typing. Next.js was chosen by the user in the plan input. | FastAPI server-rendered templates would avoid Node, but the user specified Next.js. Mitigation: client components only, two pages, no server-side state. |

Mitigations that keep the added pieces explainable:
- Both mocks are single files sharing one Python image.
- Every mock is covered by a contract test.
- None of them appears in the forbidden list in Principle VII.
