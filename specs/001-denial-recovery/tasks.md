---
description: "Task list for Reclaim evidence-first denial recovery"
---

# Tasks: Reclaim Evidence-First Denial Recovery

**Input**: design documents in `specs/001-denial-recovery/`: [plan.md](plan.md), [spec.md](spec.md),
[research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), and
[quickstart.md](quickstart.md). Canonical values are in `docs/reclaim-speckit-prompts.md` Appendix A.

**Tests**: tests are required and written first. Each test task comes before the implementation it
covers and must fail when first run. Expected values are written by hand from Appendix A, never
taken from the code's own output (Constitution VIII).

**Organization**: tasks are grouped as follows:
- Setup
- Foundational
- One phase per user story, in spec priority order
- Post-MVP work
- Polish

The MVP is Phases 1–8, which covers demo steps 1–6 in replay mode.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel. The task touches different files and doesn't depend on an unfinished task.
- **[Story]**: US1–US8 from spec.md.
- Every task names its exact files, and no task touches more than 3 files.

## Notes that apply to every task

- **Synthetic data only.** Never add an upload path. The UI and every PDF must show
  "SYNTHETIC DEMO DATA".
- **Secrets** live only in the gitignored `.env`. Never put a key in code, fixtures, replay files,
  logs, audit events, or docs.
- **One audit event per step run.** Each pipeline step returns a typed output and writes exactly
  one plain-English audit event through `src/reclaim/audit.py`.
- **Policy selection moves into `gather_evidence`.** The policy is selected right after the
  Coverage read, because the lookback window and the Binary fetches need
  `policy.lookbackMonths`. `payer_context` keeps the payer decision, the denial letter, and the
  deadline cross-check. `data-model.md` §4 is updated to match. Plan.md step 5 still describes
  selection there. If the team prefers a fixed lookback instead, stop and raise it.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: an empty repo that installs, locks, and composes.

- [X] T001 Create `pyproject.toml` and `.python-version`, then run `uv lock` to produce `uv.lock`.
  - `pyproject.toml`:
    - `requires-python = ">=3.12,<3.13"` and the `src/reclaim` package layout.
    - Dependencies: fastapi 0.141.1, uvicorn 0.52.4, pydantic 2.13.5, httpx 0.28.1,
      python-multipart, python-dotenv, paramiko 5.0.0, reportlab 5.0.1, openai 3.13.0.
    - Dev group: pytest 9.1.1, pytest-asyncio 1.4.0, fhir.resources 8.3.0.
    - `[tool.pytest.ini_options]` with `asyncio_mode = "auto"`, `testpaths = ["tests"]`, and a
      registered `docker` marker.
  - `.python-version` contains `3.12`.
- [X] T002 [P] Create `.gitignore` and `.env.example`.
  - `.gitignore` covers `.env`, `.local/`, `.venv/`, `__pycache__/`, `web/node_modules/`,
    `web/.next/`, `web/test-results/`, and `web/playwright-report/`.
  - `.env.example` holds every key with safe defaults:
    - AI: `LLM_MODE=replay`, `OPENAI_MODEL=gpt-5.6-luna`, `OPENAI_API_KEY=` (empty),
      `EFFORT_BUILD_MATRIX=medium`, `EFFORT_DRAFT_PACKET=low`, `LLM_CONCURRENCY=4`.
    - Prices: `PRICE_INPUT_PER_M=0.20`, `PRICE_CACHED_INPUT_PER_M=0.02`, `PRICE_OUTPUT_PER_M=1.20`.
    - Demo: `DEMO_TODAY=2026-09-12`.
    - Base URLs: `EHR_BASE_URL=http://mock-hospital.example/fhir/R4`,
      `PAYER_BASE_URL=http://mock-northstar-health.example/api/v1`.
    - SFTP: `SFTP_HOST=mock-clearinghouse`, `SFTP_PORT=22`, `SFTP_USER=reclaim`, `SFTP_PASSWORD=`.
    - Mock credentials: `HOSPITAL_CLIENT_ID=reclaim`, `HOSPITAL_CLIENT_SECRET=`, `PAYER_TOKEN=`.
    - Paths: `DATABASE_PATH=.local/reclaim.db`, `NEXT_PUBLIC_API_BASE=http://localhost:8000`.
- [X] T003 [P] Create `Dockerfile` and `.dockerignore`.
  - `Dockerfile`: python:3.12-slim with uv. Copy `pyproject.toml` and `uv.lock`, then run
    `uv sync --locked --no-dev`. Copy `src/`, `mocks/`, and `fixtures/`. The default
    `CMD ["uv","run","uvicorn","reclaim.main:app","--host","0.0.0.0","--port","8000"]` is
    overridden per service.
  - `.dockerignore` excludes `.env`, `.local`, `.venv`, `web/node_modules`, and `.git`.
- [X] T004 [P] Scaffold the Next.js app by hand in `web/package.json`, `web/next.config.ts`, and
  `web/tsconfig.json`.
  - `web/package.json`: next 16.3.5, react, react-dom, typescript, @types/react,
    @playwright/test 1.63.0, with scripts `dev`, `build`, `start`, and `e2e`.
  - `web/next.config.ts` sets `output: 'standalone'`.
- [X] T005 Run `npm install` in `web/` to produce `web/package-lock.json`, and create
  `web/Dockerfile`: a node:20 multi-stage build of the standalone output on port 3000, with the
  `NEXT_PUBLIC_API_BASE` build arg.
- [X] T006 Create `docker-compose.yml` with five services. All use `env_file: [{path: .env, required: false}]`.
  - `app`: root Dockerfile, port 8000, `DATABASE_PATH=/data/reclaim.db` on a `.local/data` bind mount.
  - `web`: `web/Dockerfile`, port 3000.
  - `mock-hospital`: root Dockerfile, command `uvicorn mocks.hospital.app:app --port 80`,
    network alias `mock-hospital.example`.
  - `mock-northstar-health`: root Dockerfile, command `uvicorn mocks.northstar.app:app --port 80`,
    network alias `mock-northstar-health.example`.
  - `mock-clearinghouse`: `atmoz/sftp` with `platform: linux/amd64` and command
    `reclaim:${SFTP_PASSWORD}:1001`. Mounts:
    - `./fixtures/x12/HSP-CLM-100028.837` read-only at
      `/home/reclaim/claim-archive/837/HSP-CLM-100028.837`
    - `./.local/sftp/outbound-835` at `/home/reclaim/outbound/835`
    - `./.local/sftp/ssh_host_ed25519_key` at `/etc/ssh/ssh_host_ed25519_key`
    - host port 2222
  - Healthchecks on app and both mocks.
- [X] T007 Create `Makefile`. Targets:
  - `setup`: `uv sync --locked`; `npm ci` in `web/`; if `.env` is missing, copy `.env.example`
    and fill `SFTP_PASSWORD`, `HOSPITAL_CLIENT_SECRET`, and `PAYER_TOKEN` with
    `uv run python -c "import secrets;print(secrets.token_urlsafe(24))"`; `mkdir -p .local/sftp/outbound-835 .local/data`;
    `ssh-keygen -t ed25519 -N '' -f .local/sftp/ssh_host_ed25519_key` if missing; write
    `.local/sftp/known_hosts`; `npx playwright install chromium` in `web/`.
  - `test`: `uv run pytest` (T124 extends this).
  - `demo`: `docker compose up -d --build --wait`.
  - `reset`: `curl -fsS -X POST localhost:8000/api/demo/reset`.
  - `record`: `LLM_MODE=live uv run python scripts/record_replay.py`.
- [X] T008 [P] Write `tests/test_secrets_guard.py`. It asserts that `git check-ignore .env` exits 0.
  It also fails if any file under `fixtures/` or `docs/` matches `sk-[A-Za-z0-9_-]{20,}` or
  `OPENAI_API_KEY\s*=\s*\S+`, or if `.env.example` gives `OPENAI_API_KEY` a value.

**Checkpoint**: `make setup && uv run pytest tests/test_secrets_guard.py` passes.
`docker compose config` is valid.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: validated fixtures, then the tokenizer, storage, audit writer, Protocols, policy
store, both mocks, SFTP, and the app/web shell. No user story work starts until this phase is done.

### Fixtures first (each validation test before its fixture)

- [X] T009 [P] Write `tests/fixtures/test_x12_fixtures.py`. It uses raw-text checks with a small
  inline `~`/`*` split and inline Luhn helper, not `src/`.
  - Both files match Appendix A2/A3 byte for byte (the expected text is pasted into the test).
  - ISA is 106 characters.
  - SE01: 37 for the 835, 25 for the 837P.
  - Control numbers match: `000000905`/`905`, and `000000712`/`712`.
  - Per-claim balancing: 4800−0=4800, 350−280=70, 620−0=620. BPR02 = 280.
  - NPIs `1234567893` and `1245319599` pass the Luhn check with the 80840 prefix.
  - CLM02 4800 = SV102.
  - `REF*6R` follows SVC on every 835 claim.
- [X] T010 [P] Create `fixtures/x12/era-2026-09-12.835` and `fixtures/x12/HSP-CLM-100028.837`,
  copied verbatim from Appendix A2 and A3 (one segment per line, LF).
- [X] T011 [P] Write `tests/fixtures/test_json_fixtures.py`. It asserts `fixtures/claim-map.json`
  equals the A4 JSON, `fixtures/policies/NST-IMG-2026-04.json` equals the A7 JSON,
  `fixtures/payer/payer-decision.json` equals the A6 decision JSON, and
  `fixtures/payer/appeal-response.json` equals the A6 201 body. Expected dicts are hand-pasted.
- [X] T012 [P] Create `fixtures/claim-map.json` (A4) and `fixtures/policies/NST-IMG-2026-04.json`
  (A7), verbatim.
- [X] T013 [P] Create `fixtures/payer/payer-decision.json` (A6 decision) and
  `fixtures/payer/appeal-response.json` (A6 201 body), verbatim.
- [X] T014 [P] Write `tests/fixtures/test_fhir_fixtures.py`.
  - Every `fixtures/fhir/*.json` parses with `fhir.resources.R4B` models.
  - Hand-written R4 checks for Observation and DiagnosticReport `subject` = `Patient/patient-0042`.
  - A5 values:
    - Patient MR `MRN-0042`.
    - Coverage `subscriberId` `MEMBER-448820`, plan class "Commercial PPO", group
      `NST-PPO-GRP-01`, payor identifier `NSTHLTH01`.
    - Practitioner NPI `1234567893`; Organization NPI `1245319599`, state WA.
    - Encounter period start `2026-08-10T09:00:00Z`, subject patient-0042.
    - Condition M54.16, recordedDate 2026-05-28.
    - DiagnosticReport and Observation dates; Observation LOINC 72514-3, value 8.
    - ServiceRequest `order-901`: CPT 72148, authoredOn 2026-08-10, `reasonReference`
      Condition/condition-100, non-empty `note[0].text`.
    - Procedure `basedOn` order-901.
    - DocumentReference dates 2026-08-10, 2026-07-14, and 2019-03-02, each with
      `content[0].attachment.url` = `Binary/<same id>`.
  - Each Binary is `text/plain` and base64-decodes.
  - The decoded `treatment-note-022` text contains "6 weeks", "2026-06-02", "2026-07-14", and
    "home exercise program".
  - The decoded `note-progress-031` text contains none of "therapy", "conservative",
    "medication", or "exercise" (A1).
  - No MedicationRequest file exists.
- [X] T015 [P] Create `fixtures/fhir/Patient-patient-0042.json`,
  `fixtures/fhir/Coverage-coverage-0042.json`, and
  `fixtures/fhir/Encounter-encounter-20260810-42.json` with the A5 values.
- [X] T016 [P] Create `fixtures/fhir/Practitioner-practitioner-lee.json`,
  `fixtures/fhir/Organization-mock-hospital.json`, and
  `fixtures/fhir/Condition-condition-100.json` with the A5 values.
- [X] T017 [P] Create `fixtures/fhir/DiagnosticReport-report-xr-555.json`,
  `fixtures/fhir/Observation-obs-pain-7781.json`, and
  `fixtures/fhir/ServiceRequest-order-901.json` with the A5 values. The ServiceRequest note is the
  clinician's rationale for the MRI.
- [X] T018 [P] Create `fixtures/fhir/Procedure-procedure-902.json`,
  `fixtures/fhir/DocumentReference-note-progress-031.json`, and
  `fixtures/fhir/Binary-note-progress-031.json`. The progress note text covers radiating leg pain,
  a positive straight-leg raise, focal weakness, and why an MRI is needed now, with no prior
  treatment. It includes "SYNTHETIC DEMO DATA".
- [X] T019 [P] Create `fixtures/fhir/DocumentReference-treatment-note-022.json` and
  `fixtures/fhir/Binary-treatment-note-022.json`. The text is a PT discharge summary: 6 weeks of
  physical therapy from 2026-06-02 to 2026-07-14 plus a home exercise program, symptoms not
  improved. It includes "SYNTHETIC DEMO DATA".
- [X] T020 [P] Create `fixtures/fhir/DocumentReference-note-ortho-2019-004.json` and
  `fixtures/fhir/Binary-note-ortho-2019-004.json`: an unrelated 2019-03-02 ankle sprain visit.
- [X] T021 [P] Write `tests/fixtures/test_denial_letter.py`.
  - Importing `scripts/make_denial_letter.py` and calling `render()` twice gives identical bytes.
  - Those bytes equal `fixtures/payer/denial-letter.pdf`.
  - The bytes contain `October 19, 2026`, `denial-letter-99281`, `PAYER-CLM-99281`, `CO-50`, and
    `SYNTHETIC DEMO DATA`.
- [X] T022 Create `scripts/make_denial_letter.py`: reportlab with `invariant=1`,
  `pageCompression=0`, and Helvetica only, with a `render() -> bytes` function and a `__main__`
  that writes the file. Then run it to produce `fixtures/payer/denial-letter.pdf`.

### Core modules

- [X] T023 [P] Write `tests/unit/test_config.py`.
  - Defaults match `.env.example` (DEMO_TODAY 2026-09-12, LLM_MODE replay, gpt-5.6-luna, efforts
    medium/low, concurrency 4, the three prices).
  - Environment variables override the defaults.
  - `Settings.public()` returns demoDate, aiMode, model, and baseUrls, and none of
    `OPENAI_API_KEY`, `PAYER_TOKEN`, `HOSPITAL_CLIENT_SECRET`, or `SFTP_PASSWORD`.
- [X] T024 Create `src/reclaim/__init__.py` and `src/reclaim/config.py`: a frozen `Settings`
  dataclass loaded from the environment after `dotenv.load_dotenv()`, plus `Settings.public()`.
- [X] T025 [P] Write `tests/unit/test_tokenizer.py` per `contracts/x12-fixtures.md` §5.
  - Delimiters are read from ISA: a copy with `|` elements and `}` components tokenizes identically.
  - CRLF, LF, and no line breaks give the same segments.
  - Empty elements are preserved (hero CLP05 is `""`).
  - A truncated ISA raises `X12ParseError`.
- [X] T026 Create `src/reclaim/x12/__init__.py` and `src/reclaim/x12/tokenizer.py`:
  `tokenize(text) -> list[Segment]` and `X12ParseError`, following `contracts/x12-fixtures.md` §1.
- [X] T027 [P] Write `tests/unit/test_repo.py` against a temp SQLite file.
  - `init_schema` creates the 8 tables in data-model.md §1.
  - `insert_remit_file` returns False for a duplicate sha256.
  - `upsert_case` enforces a unique `hospital_claim_id`.
  - `save_step_output` overwrites.
  - `reset_all` empties every table.
- [X] T028 Create `src/reclaim/repo.py`: `Repo(path)` with `init_schema`, `insert_remit_file`,
  `upsert_case`, `get_case`, `list_cases`, `update_case`, `save_step_output`, `get_step_output`,
  `reset_all`, and the table DDL from data-model.md §1.
- [X] T029 [P] Write `tests/unit/test_audit.py`.
  - `write_event(repo, case_id, step, summary, detail, ehr_requests, llm_usage)` stores one row.
  - Inbox events allow `case_id=None`.
  - `list_events(case_id)` returns rows in insertion order.
  - `write_event` raises if `summary` or `detail` contains a configured secret value.
- [X] T030 Create `src/reclaim/audit.py` with `write_event` and `list_events` (uses `Repo` and `Settings`).
- [X] T031 Create `src/reclaim/models.py` with the Pydantic v2 models from data-model.md §2:
  Remit, RemitClaim, Adjustment, OriginalClaim, ClaimMapEntry, IdentityCheck, EvidenceItem,
  EvidenceSet, PayerDecision, Policy, PolicySelection, Deadline, Citation, MatrixRow,
  EvidenceMatrix, LetterStatement, Letter, HeaderField, Persona, LlmUsage, plus the `CaseStatus`
  and `Lane` literals.
- [X] T032 Create `src/reclaim/adapters/__init__.py` and `src/reclaim/adapters/protocols.py` with
  the six Protocols, their value models, and their exceptions, exactly as in
  `contracts/adapters.md`.
- [X] T033 [P] Write `tests/unit/test_policy_store.py`.
  - Selecting (NSTHLTH01, "Commercial PPO", WA, 72148, 2026-08-10) returns NST-IMG-2026-04 v2026.04.
  - Each of these returns `policy=None` with the matching `failed_selector`: payer `OTHER01`,
    plan "Commercial HMO", state OR, procedure 72149, and date 2025-12-31.
  - `snapshot_bytes` is stable, sorted-key JSON.
- [X] T034 Create `src/reclaim/adapters/policy.py`: `FilePolicyStore(dir)` implementing
  `PolicyStore` over `fixtures/policies/*.json`. Selectors are checked in the order payerId,
  planType, state, procedureCode, dateOfService.
- [X] T035 Create `tests/conftest.py` (fixtures `settings`, `repo` on tmp_path, `fixtures_dir`)
  and `tests/fakes.py` (`FakeInbox` and `FakeArchive`, dict-backed implementations of
  `RemitInbox` and `ClaimArchive`).

### Mock services, SFTP, and contract tests

- [X] T036 [P] Write `tests/contract/test_mock_hospital.py` per `contracts/mock-hospital-fhir.md`.
  It uses `httpx.AsyncClient(transport=ASGITransport(app))`.
  - `/fhir/R4/.well-known/smart-configuration` returns 200.
  - `/auth/token` returns 200 with a good client and 401 `invalid_client` with a bad one.
  - A FHIR call with no token returns 401 OperationOutcome `login`.
  - Encounter and Patient reads work.
  - Searches for the 8 types return searchset Bundles with correct totals:
    - Coverage 1, Condition 1, ServiceRequest 1, Procedure 1, DiagnosticReport 1, Observation 1
    - DocumentReference 3
    - MedicationRequest 0 with no `entry`
  - Binary returns `contentType` `text/plain`.
  - An unknown id returns 404 `not-found`; `?foo=bar` returns 400 `not-supported`.
  - `PUT /_control/missing-evidence {"enabled":true}` drops DocumentReference to 2 and makes both
    `treatment-note-022` reads 404. `POST /_control/reset` restores them.
  - Every response is `application/fhir+json` with `X-Synthetic-Data: true`.
- [X] T037 Create `mocks/__init__.py`, `mocks/hospital/__init__.py`, and `mocks/hospital/app.py`:
  a FastAPI FHIR R4 mock that loads `fixtures/fhir/`, issues in-memory tokens, supports search by
  `patient` only, returns OperationOutcome errors, and has the `/_control` toggle, state, and reset.
- [X] T038 [P] Write `tests/contract/test_mock_payer.py` per
  `contracts/mock-northstar-payer.openapi.yaml`, using ASGITransport and an injectable clock and
  `DEMO_TODAY`.
  - Decision: 200 body equals `fixtures/payer/payer-decision.json`; 401 `unauthorized`; 404
    `claim_not_found`.
  - `GET /documents/denial-letter-99281` returns `application/pdf`; an unknown id returns 404
    `document_not_found`.
  - `POST /documents`: 201; the same bytes again return 200; different bytes return 409
    `document_conflict`; a bad `documentType` returns 400.
  - `POST /appeals` with the A6 body after uploading the 5 documents: 201 equals
    `appeal-response.json`.
    - Same key and body: 200 with an identical body and `Idempotent-Replayed: true`.
    - Same key, different body: 409 `idempotency_key_reused`.
    - Missing upload: 422 `unknown_attachment`.
    - `DEMO_TODAY=2026-10-20`: 422 `appeal_window_closed`.
    - Unknown payerClaimId: 404 `claim_not_found`.
    - No key: 400 `invalid_request`.
  - `GET /appeals/NST-APL-80126`: `received`; at clock +30 s, `in-review` with `updatedAt`
    `2026-09-12T18:32:30Z`; an unknown id returns 404 `appeal_not_found`.
  - `POST /_control/reset` clears appeals.
- [X] T039 Create `mocks/northstar/__init__.py` and `mocks/northstar/app.py`: a FastAPI mock of
  A6 under `/api/v1`, with a bearer token from `PAYER_TOKEN`, in-memory documents, appeals, and
  idempotency records, the `x-evaluation-order` from the contract, a `DEMO_TODAY` setting, an
  injectable `now()`, and `/_control/reset`.
- [X] T040 [P] Write `tests/contract/test_sftp_container.py`, marked `@pytest.mark.docker` and
  skipped unless `RECLAIM_DOCKER_TESTS=1`. It targets compose `mock-clearinghouse` on
  localhost:2222 with `.local/sftp/known_hosts`.
  - `SftpClaimArchive.get_837("HSP-CLM-100028")` equals the fixture bytes.
  - `get_837("HSP-CLM-000000")` returns None.
  - `SftpRemitInbox.deliver`, then `list_files`, then `download` round-trips.
  - `clear()` empties the inbox.
- [X] T041 Create `src/reclaim/adapters/sftp.py`: `SftpRemitInbox` and `SftpClaimArchive` using
  paramiko 5 (`listdir_attr`, `getfo`, `putfo`, `remove`). Host key checking uses
  `.local/sftp/known_hosts`. Blocking calls run in `asyncio.to_thread`.

### App and web shell

- [X] T042 [P] Write `tests/contract/test_app_api_config.py` against `create_app(settings, adapters)`.
  - `GET /api/health` returns `{"ok": true}`.
  - `GET /api/config` matches the `Config` schema in `contracts/app-api.openapi.yaml`, with
    `demoDate` 2026-09-12 and `aiMode` replay, and its JSON contains no secret values.
  - `GET /api/personas` returns exactly `billing-approver-01`/`authorized-billing-user`/canApprove
    true and `viewer-01`/`viewer`/false.
  - CORS allows `http://localhost:3000`.
- [X] T043 Create `src/reclaim/main.py` and `src/reclaim/api.py`.
  - `main.py`: `create_app(settings, adapters)`, a module-level `app` built from env with real
    adapters, a lifespan that inits the repo, and CORS.
  - `api.py`: an APIRouter with `/api/health`, `/api/config`, and `/api/personas`; the persona
    table is a constant in `api.py`; errors use the `{"error":{code,message}}` envelope.
- [X] T044 Create `web/lib/api.ts` and `web/app/components/Header.tsx`.
  - `api.ts`: typed fetch helpers for the app API. The base is `NEXT_PUBLIC_API_BASE`. Human
    actions send `X-Persona`.
  - `Header.tsx`: a client component showing "SYNTHETIC DEMO DATA",
    "Demo date: 2026-09-12" (from `/api/config`), "AI: live" or "AI: replay", the configured base
    URLs, and a persona picker saved to localStorage inside try/catch.
- [X] T045 Create `web/app/layout.tsx` (renders `Header` on every page) and `web/app/globals.css`.

**Checkpoint**: `uv run pytest` is green. `make demo` serves http://localhost:3000 with the
header, persona picker, and base URLs. Fixtures are validated.

---

## Phase 3: User Story 1 - A denial arrives on its own (Priority: P1) 🎯 MVP

**Goal**: "Simulate incoming remit" delivers the 835 over SFTP, the poller ingests it, and the
queue shows the hero case plus the paid and other-lane summaries.

**Independent Test**: deliver `era-2026-09-12.835` to an empty inbox. The queue shows A9 step 1
text; a repeat delivery creates no cases; zero EHR requests are recorded.

### Tests (write first, must fail)

- [X] T046 [P] [US1] Write `tests/unit/test_remit835.py` per `contracts/x12-fixtures.md` §5.
  - Three claims.
  - Hero claim fields: `HSP-CLM-100028`, CLP02 `4`, 4800, 0, claim filing indicator `12`,
    `PAYER-CLM-99281`, member `MEMBER-448820`, NPI `1234567893`, DOS 2026-08-10, `HC`/`72148`,
    denial code `CO-50`.
  - A copy with the CAS moved to claim level still gives `CO-50`.
  - Lanes are `medical-necessity`, `paid`, and `other-denial`.
  - Payer `NORTHSTAR HEALTH`/`NSTHLTH01`, payee NPI `1245319599`.
  - `RIVERA` does not appear in `model_dump_json()`.
- [X] T047 [P] [US1] Write `tests/unit/test_validate_835.py`.
  - The fixture passes X-01 to X-10 and X-13.
  - In-test string-replaced copies each fail with exactly the expected rule ID:
    - `SE*37`→`SE*36` gives X-04.
    - `CAS*CO*50*4800`→`CAS*CO*50*4700` gives X-06.
    - BPR02 `280`→`290` gives X-08.
    - NPI `1234567893`→`1234567890` gives X-10.
    - GS08 `005010X221A1`→`004010X091A1` gives X-05.
- [X] T048 [P] [US1] Write `tests/integration/test_ingest.py` with `FakeInbox` and a temp repo.
  - Delivering the fixture creates `case-100028` (lane `medical-necessity`, status `new`,
    headline "Northstar Health · CO-50 Medical necessity · $4,800", `payerClaimId`
    `PAYER-CLM-99281`), `case-100031` (`paid`), and `case-100035` (`other-denial`).
  - One remit audit event with `ehr_requests` `[]`.
  - Delivering the same bytes as `era-copy.835` creates no new cases and writes an audit event
    containing "already processed".
  - An unbalanced copy is recorded as `rejected` with `X-06` and creates no cases.
- [X] T049 [P] [US1] Write `tests/contract/test_app_api_queue.py`.
  - After ingest, `GET /api/queue` returns cases `[case-100028]` with the A9 headline.
  - `summary.lines` equals `["1 paid claim, no action", "1 other denial lane: not handled in this demo"]`.
  - `otherLane[0].label` is "Other denial lane: not handled in this demo".
  - `POST /api/demo/simulate-remit` returns 202 `{"delivered": "era-2026-09-12.835"}`, and the
    file is in `FakeInbox`.

### Implementation

- [X] T050 [US1] Create `src/reclaim/x12/remit835.py`: `parse_835(text) -> Remit`, with loops per
  `contracts/x12-fixtures.md` §2, the denial code rule, and the lane table. Names are never read
  into the model.
- [X] T051 [US1] Create `src/reclaim/x12/validate.py`:
  `validate_835(segments, remit) -> list[RuleFailure]` implementing X-01 to X-10 and X-13, with a
  Luhn/80840 NPI helper.
- [X] T052 [US1] Create `src/reclaim/steps/__init__.py` and `src/reclaim/steps/ingest.py`:
  `ingest(repo, name, content) -> IngestResult`.
  - Computes sha256 and dedupes; on a repeat, writes the audit event and returns.
  - Tokenizes, parses, and validates.
  - Upserts one case per CLP; `case_id` is `case-` plus the numeric suffix.
  - Maps CARC 50 to the denial reason "Medical necessity".
  - Writes one audit event (for example "Read era-2026-09-12.835: 3 claims. Created case-100028
    (CO-50, $4,800). 1 paid claim, no action. 1 other denial lane.").
  - Returns the new medical-necessity case IDs.
- [X] T053 [US1] Create `src/reclaim/pipeline.py` and `src/reclaim/poller.py`.
  - `pipeline.py`: `run_case(ctx, case_id)` runs the registered `STEPS` in order under an
    `asyncio.Semaphore(settings.llm_concurrency)`. It sets `running`, saves each step output, and
    stops when a step returns a stop status. A step exception writes that step's audit event with
    the error, sets `last_error`, keeps the status, and stops. `STEPS` starts empty and each later
    phase appends to it.
  - `poller.py`: `run_inbox_poller(ctx)` checks every 1 s. It lists files, downloads unseen
    `(name, size, mtime)` entries, calls `ingest`, and schedules `run_case` for each new case.
- [X] T054 [US1] Update `src/reclaim/demo.py`, `src/reclaim/api.py`, and `src/reclaim/main.py`.
  - `demo.py`: `simulate_remit(ctx)` delivers `fixtures/x12/era-2026-09-12.835` through
    `RemitInbox.deliver`.
  - `api.py`: add `GET /api/queue` and `POST /api/demo/simulate-remit`.
  - `main.py`: wire `SftpRemitInbox` and `SftpClaimArchive`, and start the poller task in the lifespan.
- [X] T055 [US1] Create `web/app/page.tsx` (client component).
  - Presenter bar with a "Simulate incoming remit" button.
  - Polls `/api/queue` every 1 s.
  - Lists case headlines linking to `/cases/[caseId]`, with status badges.
  - Shows `summary.lines`, other-lane labels, and remit files.

**Checkpoint (showable)**: run `make demo` and click **Simulate incoming remit**. Within 5 s the
queue shows "Northstar Health · CO-50 Medical necessity · $4,800", "1 paid claim, no action", and
"1 other denial lane: not handled in this demo".

---

## Phase 4: User Story 2 - It resolves the denial to the exact claim and visit (Priority: P1) 🎯 MVP

**Goal**: fetch the 837 and pass the six identity checks before any EHR request.

**Independent Test**: the hero case shows `HSP-CLM-100028` → 837 claim → `encounter-20260810-42`
with 6 passed checks. Each one-field variant goes to needs-review with zero EHR requests (the UI
for that comes in Phase 9).

### Tests (write first, must fail)

- [X] T056 [P] [US2] Write `tests/unit/test_claim837.py`.
  - Fields equal the A3 "Extracted" line: `HSP-CLM-100028`, `MEMBER-448820`, `NSTHLTH01`, billing
    NPI `1245319599`, state `WA`, rendering `1234567893`, `HC`/`72148`, 1 unit, 4800, DOS
    2026-08-10.
  - Diagnosis `M5416` is normalized to `M54.16`; group `NST-PPO-GRP-01`; frequency code `1`.
  - `RIVERA` does not appear in the model dump.
- [X] T057 [P] [US2] Write `tests/unit/test_validate_837.py`.
  - The fixture passes X-01 to X-05 and X-10 to X-13.
  - `SE*25`→`SE*24` gives X-04; `SV1*HC:72148*4800`→`SV1*HC:72148*4700` gives X-11;
    `HL*2*1*22*0`→`HL*2*3*22*0` gives X-12.
- [X] T058 [P] [US2] Write `tests/unit/test_identity.py` for `run_identity_gate(remit_claim, original_claim)`.
  - The hero case returns 6 passed checks with the spec US2 table values.
  - Six separate tests each change exactly one 837 field (CLM01, NM1*IL NM109, DTP*472, NM1*PR
    NM109, NM1*82 NM109, SV101) and assert failure naming `claimId`, `memberId`, `dateOfService`,
    `payerId`, `renderingNpi`, and `procedureCode` respectively.
  - A remit claim with `member_id=None` fails on `memberId`.
  - CLM05 `11:B:7` fails on `claimFrequency`.
  - `check_post_read`: encounter start `2026-08-11T09:00:00Z` fails `encounterDate`; subject
    `Patient/patient-0099` fails `encounterSubject`; Coverage `subscriberId` `MEMBER-000000`
    fails `coverageSubscriberId`.
- [X] T059 [US2] Write `tests/integration/test_identity_pipeline.py` and add `SpyEhrClient` to
  `tests/fakes.py`. `SpyEhrClient` records calls and raises if one is made.
  - The hero case runs to status `claim-matched`, with an audit event listing 6 passed checks and
    `ehr_requests == []`.
  - For each of the six one-field 837 variants in `FakeArchive`: status `needs-review`,
    `needs_review_field` set to that field, spy call count 0, and every audit event has
    `ehr_requests == []`.
  - A missing 837 gives `needs-review` with `originalClaim`.
- [X] T060 [P] [US2] Write `tests/contract/test_app_api_case_identity.py`.
  - `GET /api/cases/case-100028` after identity returns `identity.chain`
    `["HSP-CLM-100028", "837 HSP-CLM-100028", "encounter-20260810-42"]`, 6 checks all passed, and
    a `timeline` with ingest, fetch_claim, and resolve_identity events.
  - An unknown case returns 404.

### Implementation

- [X] T061 [US2] Create `src/reclaim/x12/claim837.py` (`parse_837(text) -> OriginalClaim`, per
  contract §3) and add `validate_837` (X-01 to X-05, X-10 to X-13) to `src/reclaim/x12/validate.py`.
- [X] T062 [US2] Create `src/reclaim/steps/fetch_claim.py`: `fetch_claim(ctx, case)` calls
  `ClaimArchive.get_837`, then parses and validates. If the 837 is missing or invalid the status
  is `needs-review` with `originalClaim`. Writes one audit event.
- [X] T063 [US2] Create `src/reclaim/steps/resolve_identity.py`.
  - `run_identity_gate` and `check_post_read` as pure functions.
  - `resolve_identity(ctx, case)` loads `fixtures/claim-map.json` and runs the gate. On a pass,
    status is `claim-matched` and the output includes `ClaimMapEntry`. On a fail, status is
    `needs-review` with the field.
  - Writes one audit event naming each check.
- [X] T064 [US2] Register `fetch_claim` and `resolve_identity` in `STEPS` in
  `src/reclaim/pipeline.py`. Add `GET /api/cases/{caseId}` (case, running, statusLine, identity,
  timeline, actions) to `src/reclaim/api.py`.
- [X] T065 [US2] Create `web/app/cases/[caseId]/page.tsx`,
  `web/app/cases/[caseId]/IdentityTab.tsx`, and `web/app/cases/[caseId]/TimelineTab.tsx`.
  - `page.tsx`: tabs for Identity, Evidence, Matrix, Packet, and Timeline; polls every 1 s while
    `running` is set.
  - `IdentityTab.tsx`: the chain and a 6-row check table.
  - `TimelineTab.tsx`: audit events with EHR request lists.

**Checkpoint (showable)**: after step 1, open the case. It shows HSP-CLM-100028 → 837 claim →
encounter-20260810-42 with 6 identity checks passed.

---

## Phase 5: User Story 3 - It gathers only relevant evidence (Priority: P1) 🎯 MVP

**Goal**: read the chart in the A5 order, select the policy after Coverage, apply the lookback,
and fetch Binaries for in-window notes only.

**Independent Test**: the Evidence tab lists 8 items with source and date,
"1 record excluded (outside 6-month lookback)", and "MedicationRequest: 0 found".

### Tests (write first, must fail)

- [X] T066 [P] [US3] Write `tests/unit/test_lookback.py` for `src/reclaim/steps/gather_evidence.py` helpers.
  - `lookback_window(date(2026,8,10), 6)` is `(2026-02-10, 2026-08-10)`.
  - `lookback_window(date(2026,8,31), 6)` starts 2026-02-28.
  - `resource_date` uses the right field per type (data-model.md §3).
  - Inclusive edges are included; 2019-03-02 is excluded with "outside 6-month lookback"; a
    resource with no date is excluded with "no date".
- [X] T067 [P] [US3] Write `tests/contract/test_ehr_client.py`: `HttpEhrClient` against the
  mock-hospital ASGI app.
  - The token is fetched once and reused.
  - Every request sends `Accept: application/fhir+json` and a Bearer token.
  - `requests_made` records the exact paths in order.
  - `search` returns resources from the entries (MedicationRequest `[]`).
  - `read_binary` decodes to bytes.
  - A 404 raises `EhrNotFound`.
- [X] T068 [US3] Write `tests/integration/test_gather_evidence.py` and add a
  `fixture_ehr_client` fixture (HttpEhrClient over ASGITransport) to `tests/conftest.py`.
  - The hero case's `requests_made` equals, exactly:
    - Encounter/encounter-20260810-42
    - Patient/patient-0042
    - Coverage?patient=patient-0042
    - Condition, ServiceRequest, Procedure, DiagnosticReport, Observation, DocumentReference,
      MedicationRequest searches (`?patient=patient-0042`)
    - Binary/note-progress-031 and Binary/treatment-note-022, with no Binary for note-ortho-2019-004
  - 8 included items: coverage-0042, condition-100, order-901, procedure-902, report-xr-555,
    obs-pain-7781, note-progress-031, treatment-note-022.
  - `excluded_count` 1; `search_counts["MedicationRequest"] == 0`; status `evidence-gathered`;
    the policy selected is NST-IMG-2026-04.
  - A Coverage subscriber mismatch gives `needs-review` `coverageSubscriberId`, with requests
    stopping after the Coverage search.
  - An encounter date mismatch gives `needs-review` with only the Encounter request.
  - A policy store with no WA policy gives `needs-review` `state`, with no Condition-onward
    requests.

### Implementation

- [X] T069 [US3] Create `src/reclaim/adapters/fhir.py`: `HttpEhrClient(base_url, token_url,
  client_id, client_secret, transport=None)` implementing `EhrClient` with httpx.AsyncClient and
  `EhrNotFound`.
- [X] T070 [US3] Create `src/reclaim/steps/gather_evidence.py` with `lookback_window`,
  `resource_date`, and `gather_evidence(ctx, case)`, doing the following in order:
  1. Read Encounter; run the post-read date and subject checks.
  2. Read Patient.
  3. Search Coverage; run the subscriber check.
  4. Select the policy with `PolicyStore.select` (plan from Coverage, state from 837 N4).
  5. Run the 7 clinical searches.
  6. Apply the lookback.
  7. Read Binaries for in-window DocumentReferences.
  8. Build the `EvidenceSet`.
  9. Write one audit event with `ehr_requests=client.requests_made` and the included and excluded counts.
- [X] T071 [US3] Update three files:
  - `src/reclaim/pipeline.py`: register `gather_evidence` in `STEPS`.
  - `src/reclaim/api.py`: add the `evidence` section (items, `excludedLine`, `searchCounts`) and
    `policy.label` to the case detail.
  - `src/reclaim/main.py`: wire `HttpEhrClient` and `FilePolicyStore`.
- [X] T072 [US3] Create `web/app/cases/[caseId]/EvidenceTab.tsx`. Each row shows a type label
  (Coverage, Condition, Order, Procedure, X-ray report, Pain score, Note), record id, source, and
  date. Below the rows: the excluded line and "MedicationRequest: 0 found". Mount it in
  `web/app/cases/[caseId]/page.tsx`.

**Checkpoint (showable)**: the Evidence tab matches A9 step 3.

---

## Phase 6: User Story 4 - It tests the evidence against the payer's own rules (Priority: P1) 🎯 MVP

**Goal**: fetch the payer decision and letter, compute the deadline, and build the matrix in one
LLM call. The verifier enforces Constitution IV, with one high-effort retry.

**Independent Test**: the Matrix tab shows "Policy NST-IMG-2026-04 v2026.04" with R1–R3
satisfied by verified excerpts. Forged and paraphrased citations are rejected.

### Tests (write first, must fail)

- [X] T073 [P] [US4] Write `tests/unit/test_verifier.py` for `verify_matrix(proposal, evidence_set, policy)`.
  Excerpts are hand-copied from the fixture note texts.
  - Hero citations verify:
    - R1: condition-100 and note-progress-031
    - R2: treatment-note-022
    - R3: order-901
  - Rejections:
    - A forged `DocumentReference/note-fake-999` is rejected as "not fetched for this case".
    - A paraphrased excerpt is rejected as "excerpt not found verbatim".
    - `DocumentReference/note-ortho-2019-004` is rejected as "outside lookback".
    - `Observation/obs-pain-7781` cited for R1 is rejected as "type not allowed".
    - An 11-character excerpt is rejected as "excerpt too short".
  - Row outcomes:
    - A row whose citations all fail becomes `missing` with a reason starting
      "All proposed citations failed verification:".
    - A proposal omitting R3 still yields a missing R3 row.
    - A duplicate R1 entry raises.
- [X] T074 [P] [US4] Write `tests/unit/test_llm_client.py`.
  - `ReplayLlmClient`:
    - A recorded file returns output that re-validates plus usage.
    - A miss raises `ReplayMissError` naming the step.
    - Malformed output fails `text_format` validation.
    - The replay key changes when model, effort, instructions, or input changes.
  - `OpenAiLlmClient` with an injected fake `responses.parse`:
    - Called with `store=False`, `reasoning={"effort": "medium"}`, `max_output_tokens`,
      `prompt_cache_key`, and `text_format`.
    - Retries once on 429 and on 500, never on 400.
    - An `incomplete` status raises.
    - Usage maps `input_tokens`, `cached_tokens`, `output_tokens`, and `reasoning_tokens`.
    - `cost_usd(usage, settings)` = (input−cached)×0.20/1M + cached×0.02/1M + output×1.20/1M.
    - Recording writes only `{step, key, model, effort, output, usage}`.
- [X] T075 [P] [US4] Write `tests/contract/test_payer_adapter.py`: `NorthstarPayerAdapter` against
  the mock payer ASGI app.
  - `get_decision` returns the A6 values.
  - `get_document` returns PDF bytes.
  - `upload_document` returns True, then False for the same bytes, and raises
    `PayerError(409, "document_conflict")` for different bytes.
  - `create_appeal` gives `appeal_id` NST-APL-80126 with `replayed` False, then True on replay.
  - `get_appeal` returns the appeal.
  - An unknown claim raises `PayerError(404, "claim_not_found")`.
- [X] T076 [P] [US4] Write `tests/unit/test_deadline.py`.
  - `compute_deadline(decision_date=2026-08-20, appeal_deadline=2026-10-19, window_days=60,
    today=2026-09-12)` gives `days_left` 37, `policy_window_date` 2026-10-19, and warning None.
  - With an appeal deadline of 2026-10-15 the warning names both "October 15, 2026" and
    "October 19, 2026", and the deadline of record stays 2026-10-15.
  - `deadline_line` is "Appeal deadline: October 19, 2026 (37 days left)".
- [X] T077 [US4] Write `tests/integration/test_matrix_pipeline.py` and add `FakeLlmClient` to
  `tests/fakes.py`. `FakeLlmClient` returns queued hand-written outputs and records each call's
  step, effort, and input.
  - The hero case reaches `payer_context` output with decision "denied", 2026-08-20, CO-50,
    "Insufficient documentation of medical necessity", deadline 2026-10-19, channels portal and
    fax, and the `denial-letter-99281` bytes stored.
  - `build_matrix` gives 3/3 satisfied with exactly 1 LLM call at effort `medium`. The first
    input message contains the policy JSON and the last contains the evidence, and there is no
    `note-ortho-2019-004` text in the input.
  - A first proposal with a forged citation triggers a second call at `high` whose last input
    message includes the rejection reason; after the retry the row is satisfied.
  - A proposal with R2 missing and the A8 reason gives status `needs-evidence` with exactly 1 call.

### Implementation

- [X] T078 [US4] Create `src/reclaim/verify.py`: `verify_matrix(proposal, evidence_set, policy) ->
  (EvidenceMatrix, list[Rejection])`, implementing the "Citation verified" and "Matrix" rules in
  data-model.md §3.
- [X] T079 [US4] Create `src/reclaim/adapters/llm.py`:
  - `OpenAiLlmClient`: `OpenAI().with_options(timeout=45.0, max_retries=0)`, `responses.parse`,
    `store=False`, one jittered retry on 429/5xx, an optional `record_dir`.
  - `ReplayLlmClient`.
  - `replay_key()` and `cost_usd()`.
- [X] T080 [US4] Create `src/reclaim/adapters/payer.py`: `NorthstarPayerAdapter(base_url, token,
  transport=None)` implementing `PayerAdapter`. It sends multipart uploads and the
  `Idempotency-Key` header, reads `Idempotent-Replayed`, and maps the error envelope to `PayerError`.
- [X] T081 [US4] Create `src/reclaim/steps/payer_context.py` with `compute_deadline` and
  `deadline_line`, plus `payer_context(ctx, case)`.
  - Calls `get_decision` and `get_document`, storing the letter in the `documents` table.
  - Computes the deadline from the decision and `policy.appealWindowDays`.
  - A 404 gives `needs-review` with `payerClaimId`.
  - Writes one audit event.
- [X] T082 [US4] Create `src/reclaim/prompts/__init__.py` and `src/reclaim/prompts/build_matrix.py`.
  - `INSTRUCTIONS` and `OUTPUT_RULES` constants: cite only listed resources, excerpts copied
    verbatim, `missing` with a reason when no evidence exists.
  - The strict `MatrixProposal` Pydantic model.
  - `build_input(policy, evidence_set, rejections=None)`: first message the policy JSON, second
    the trimmed in-window candidates whose type is in any requirement's `evidenceTypes`, and a
    rejections message appended when retrying.
- [X] T083 [US4] Create `src/reclaim/steps/build_matrix.py`: `build_matrix(ctx, case)`.
  - LLM call at `settings.effort_build_matrix` with `max_output_tokens` 6000 and
    `prompt_cache_key=policy_id`.
  - `verify_matrix`; if any citation was rejected, one retry at `high` with 12000 tokens.
  - Status is `needs-evidence` if any row is missing.
  - Writes one audit event with the LLM usage of each call and the rejections.
- [X] T084 [US4] Update three files:
  - `src/reclaim/pipeline.py`: register `payer_context` and `build_matrix`.
  - `src/reclaim/main.py`: wire `NorthstarPayerAdapter` and the LLM client by `LLM_MODE`.
  - `src/reclaim/api.py`: add `payerDecision`, `deadline`, `matrix`, `completenessLine`, and
    `aiCost` (summed from audit usage, line "AI cost for this case (estimate): $…").
- [X] T085 [US4] Create `web/app/cases/[caseId]/MatrixTab.tsx`.
  - Shows the policy label and title.
  - R1–R3 rows turn green one by one via a 400 ms CSS stagger, each with requirement text,
    citations, and excerpts. Missing rows are red with the reason.
  - Shows the payer decision summary and a denial letter link.
  - Mount it in `web/app/cases/[caseId]/page.tsx`.

**Checkpoint (showable)**: `uv run pytest tests/integration/test_matrix_pipeline.py -v` is green.
With `LLM_MODE=live` and a key in `.env`, the Matrix tab shows "Policy NST-IMG-2026-04 v2026.04"
and R1, R2, R3 green. Replay recordings come in T103.

---

## Phase 7: User Story 5 - It generates a cited appeal packet (Priority: P1) 🎯 MVP

**Goal**: an LLM-drafted body whose every statement cites verified rows, a code-rendered header,
attachments, a versioned packet, and a deterministic PDF.

**Independent Test**: the Packet tab shows the four A9 step 5 lines. Clicking a statement
highlights its requirement and excerpt. An uncited statement blocks the packet.

### Tests (write first, must fail)

- [X] T086 [P] [US5] Write `tests/unit/test_letter_verifier.py` for `verify_letter(draft, matrix)`.
  - A hero draft with 3 statements citing R1-C1, R2-C1, and R3-C1 passes.
  - Each of these blocks and names the failing statement text:
    - a statement with `citationIds: []`
    - citation `R9-C1`
    - no statement covering R3
    - `requirementIds` that disagree with the cited row
- [X] T087 [P] [US5] Write `tests/unit/test_packet_render.py`.
  - `build_header(case, claim, claim_map, decision, policy)` yields the hand-written A8 values
    with sources:
    - `HSP-CLM-100028` (remit), `PAYER-CLM-99281` (remit)
    - `MRN-0042` (claimMap), `MEMBER-448820` (claim837)
    - `72148`, `M54.16` (claim837), `1234567893`, 2026-08-10
    - `$4,800` (remit)
    - "CO-50 Insufficient documentation of medical necessity" (payerDecision)
    - `NST-IMG-2026-04` v2026.04 (policy)
  - `attachment_ids(matrix)` = `["note-progress-031", "treatment-note-022", "order-901", "policy-snapshot-NST-IMG-2026-04"]`.
  - `render_pdf(letter)` gives the same bytes twice and contains "SYNTHETIC DEMO DATA",
    "reconsider and reprocess payment", and "v1".
  - The status lines are "Ready for review", "Evidence completeness: 3/3 policy criteria
    satisfied", and "Expected recovery: $4,800".
- [X] T088 [P] [US5] Write `tests/integration/test_packet_pipeline.py` with `FakeLlmClient`.
  - The hero case ends `ready-for-review` with packet v1 `ready-for-review` and exactly 2 LLM
    calls (`build_matrix` medium, `draft_packet` low).
  - The `draft_packet` input contains only verified matrix rows.
  - The documents table holds the 4 attachments plus `appeal-letter-100028`.
  - Re-running with an identical draft keeps v1; a changed draft creates v2.
  - A draft with an uncited statement gives packet `blocked` with `blocked_reason` naming it, and
    the case stays `evidence-gathered`.
- [X] T089 [P] [US5] Write `tests/contract/test_app_api_packet.py`.
  - `GET /api/cases/case-100028` returns `packet.version` 1, `statusLine` "Ready for review",
    `completenessLine`, `deadline.line` "Appeal deadline: October 19, 2026 (37 days left)",
    `recoveryLine` "Expected recovery: $4,800", header fields with `source`, and statements with
    `citationIds`.
  - `GET /api/cases/case-100028/packets/1/pdf` returns `application/pdf`.
  - `GET /api/cases/case-100028/documents/denial-letter-99281` returns PDF bytes.

### Implementation

- [X] T090 [US5] Add `verify_letter(draft, matrix) -> LetterCheck` to `src/reclaim/verify.py`,
  following the "Letter body" rule in data-model.md §3.
- [X] T091 [US5] Create `src/reclaim/prompts/draft_packet.py`: `INSTRUCTIONS` (phrase statements
  only from the given verified rows, cite each), the strict `LetterDraft` model, and
  `build_input(matrix, requirement_texts)`.
- [X] T092 [US5] Create `src/reclaim/pdf.py`:
  - `render_pdf(letter) -> bytes`: reportlab, `invariant=1`, `pageCompression=0`, Helvetica,
    header table, body statements with citation markers, requested action "Please reconsider and
    reprocess payment", attachment list, required approver, version, and a
    "SYNTHETIC DEMO DATA" footer on every page.
  - `render_html(letter) -> str`.
- [X] T093 [US5] Create `src/reclaim/steps/draft_packet.py` with `build_header` and
  `attachment_ids`, plus `draft_packet(ctx, case)`.
  - LLM call at `low` with `max_output_tokens` 3000.
  - `verify_letter`, then assemble the `Letter`.
  - Store the attachment bytes in `documents`: Binary text as `text/plain`, ServiceRequest JSON,
    policy snapshot, letter PDF.
  - Version by `content_sha256`.
  - Set the packet and case status.
  - Write one audit event with usage.
- [X] T094 [US5] Update two files:
  - `src/reclaim/pipeline.py`: register `draft_packet`.
  - `src/reclaim/api.py`: add the `packet` and `recoveryLine` sections, plus
    `GET /api/cases/{caseId}/packets/{version}/pdf` and
    `GET /api/cases/{caseId}/documents/{documentId}`.
- [X] T095 [US5] Create `web/app/cases/[caseId]/PacketTab.tsx`.
  - Shows the four status lines.
  - Clicking a header field shows its source record.
  - Clicking a body statement highlights its requirement and excerpt.
  - Lists attachments, links the PDF, and shows a blocked reason.
  - Mount it in `web/app/cases/[caseId]/page.tsx`.

**Checkpoint (showable)**: with `LLM_MODE=live`, the Packet tab matches A9 step 5, and clicking a
sentence highlights its requirement and excerpt.

---

## Phase 8: User Story 6 - A human approves, the system submits, and tracking begins (Priority: P1) 🎯 MVP

**Goal**: role-checked approval of one version, uploads before the appeal, an idempotency key,
the confirmation, and tracking. Also the replay recording, which completes the replay-mode MVP.

**Independent Test**: approve as `billing-approver-01` and see the confirmation, then "In review".
A repeat submission gives one appeal. `viewer-01` is refused.

### Tests (write first, must fail)

- [X] T096 [P] [US6] Write `tests/integration/test_submit.py`, using the mock payer over
  ASGITransport and a ready hero packet.
  - Approving as `billing-approver-01`:
    - Uploads `appeal-letter-100028`, `note-progress-031`, `treatment-note-022`, `order-901`, and
      `policy-snapshot-NST-IMG-2026-04` before `POST /appeals`.
    - Sends `Idempotency-Key: appeal-case-100028-v1` with the A6 body.
    - Case becomes `submitted` with display "Submitted · Northstar confirmation NST-APL-80126 ·
      expected resolution 14 days".
  - A second call returns the same `NST-APL-80126`, and the mock holds 1 appeal.
  - `viewer-01` gets 403 `wrong_role`, 0 payer calls, and a refusal audit event.
  - An unknown persona gets 403.
  - Version 2 when only v1 exists gets 409.
  - With payer `DEMO_TODAY=2026-10-20`: 422 `payer_refused` naming `appeal_window_closed`, case
    stays `approved`, and no API string contains "Submitted".
- [X] T097 [P] [US6] Write `tests/integration/test_track.py`.
  - A `submitted` case with the payer clock under 30 s stays `submitted` with no new audit event.
  - At +30 s, `track` sets `in-review` and writes exactly one audit event.
  - Polling again writes no further event.

### Implementation

- [X] T098 [US6] Create `src/reclaim/steps/approve_and_submit.py`: `approve_and_submit(ctx,
  case_id, version, persona)`.
  - Checks role, latest version, packet and case `ready-for-review`, and all rows satisfied.
  - Records the approval and sets `approved`.
  - Uploads documents, then calls `create_appeal` with `appeal-<caseId>-v<version>`.
  - On success, submission `confirmed` and case `submitted`. On `PayerError`, submission `refused`
    with the code and message, and the case stays `approved`.
  - Writes one audit event per outcome.
- [X] T099 [US6] Create `src/reclaim/steps/track.py` (`track(ctx, case)` calls `get_appeal`, sets
  `in-review` on change, writes an audit event only on change). Add a 5 s tracking loop to
  `src/reclaim/poller.py` that tracks every `submitted` case.
- [X] T100 [US6] Add `POST /api/cases/{caseId}/packets/{version}/approve-and-submit` (reads
  `X-Persona`) to `src/reclaim/api.py`, plus the `submission` section and `actions.canApprove`
  (false unless the persona role is authorized and the packet is ready).
- [X] T101 [US6] Update `web/app/cases/[caseId]/PacketTab.tsx` and
  `web/app/cases/[caseId]/page.tsx`.
  - "Approve and submit" button, disabled unless `actions.canApprove`.
  - Shows the refusal or payer error message.
  - Shows `submission.display`, then "In review".
  - Keeps polling every 1 s while the status is `submitted`.
  - Never renders "Submitted" without `submission.appealId`.
- [X] T102 [US6] Create `scripts/record_replay.py`. It builds the app context in-process (mock
  hospital and payer via ASGITransport, `FakeInbox`-style in-memory inbox, temp SQLite) with
  `OpenAiLlmClient(record_dir=tmp)`.
  - Runs the hero case to ready-for-review, then the missing-evidence case (hospital
    `/_control/missing-evidence` on).
  - Asserts the Appendix A8 outcomes: 3/3 with R1 → condition-100 + note-progress-031,
    R2 → treatment-note-022, R3 → order-901; missing mode R2 `missing` with the exact A8 reason
    and 2/3.
  - Only if every assertion holds, copies the recordings into `fixtures/llm-replay/`. Otherwise it
    exits non-zero and writes nothing.
- [ ] T103 [US6] Record from a live run.
  - With `OPENAI_API_KEY` set only in local `.env`, run `make record` to produce
    `fixtures/llm-replay/*.json`.
  - Run `uv run pytest tests/test_secrets_guard.py tests/unit/test_llm_client.py`.
  - Commit the recordings.
  - Re-run this task whenever a prompt in `src/reclaim/prompts/` or a fixture note text changes.
- [ ] T104 [US6] MVP verification.
  - Set `LLM_MODE=replay` in `.env`, then `make demo`.
  - Click demo steps 1–6 exactly as in `specs/001-denial-recovery/quickstart.md` §2, including the
    `viewer-01` refusal and the double-submit check.
  - Any mismatch with A9 text becomes a new task.

**Checkpoint (MVP, showable)**: in replay mode with no API key, a presenter completes A9 steps 1–6
in under 3 minutes. The screen shows "Submitted · Northstar confirmation NST-APL-80126 · expected
resolution 14 days", then "In review".

---

## Phase 9: User Story 2 follow-up - Needs-review UI (after MVP)

**Goal**: needs-review paths are visible and proven.

**Independent Test**: every needs-review path names its field, and zero clinical requests are
proven from the audit events.

- [X] T105 [P] [US2] Write `tests/integration/test_needs_review_paths.py`, each case end to end
  with fakes.
  - A remit copy without `NM1*QC` gives `memberId` with no EHR requests.
  - A missing 837 gives `originalClaim` with no EHR requests.
  - A frequency-7 837 gives `claimFrequency`.
  - A policy store with no match gives `state`, with only Encounter, Patient, and Coverage requests.
  - A payer 404 gives `payerClaimId`.
  - `GET /api/cases/{id}` returns `statusLine` "Needs review" and
    `case.needsReviewField` for each.
- [X] T106 [US2] Update three files:
  - `src/reclaim/api.py`: `statusLine` "Needs review" plus `needsReviewLine`
    "Needs review: <field>".
  - `web/app/cases/[caseId]/IdentityTab.tsx`: highlight the failing check and show "No clinical
    records were requested" when the timeline EHR list is empty.
  - `web/app/page.tsx`: a "Needs review" badge in the queue.

**Checkpoint (showable)**: `uv run pytest tests/integration/test_needs_review_paths.py -v` is
green. The Identity tab renders a failing check when the case is loaded from that test's database
(`DATABASE_PATH` pointed at it).

---

## Phase 10: User Story 7 - Missing-evidence mode (Priority: P2)

**Goal**: the toggle hides the PT note. The case names the gap, drafts nothing, blocks approval,
and creates one clinician request. Re-run and task closure work too.

**Independent Test**: A9 step 7: "Needs 1 item", R2 red, no letter, Approve disabled, one
clinician request. Toggle off and re-run returns 3/3.

- [X] T107 [P] [US7] Write `tests/integration/test_missing_evidence.py`, end to end with the mock
  hospital toggle on and `FakeLlmClient` (hand-written proposal with R2 missing and the A8 reason).
  - Status `needs-evidence`, summary 2/3.
  - R2 reason exactly "No DocumentReference or MedicationRequest in the lookback window documents
    a 6-week conservative treatment trial".
  - No packet, `canApprove` false, `needsLine` "Needs 1 item", exactly 1 LLM call.
  - Exactly one task equal to the A8 task JSON (`task-case-100028-R2`,
    `clinical-evidence-request`, `treating-clinician`, the A8 question, `open`).
  - Re-run with the toggle still on leaves still one task.
  - Toggle off and re-run: `ready-for-review` 3/3, and the task is `closed` with `close_note`
    "Requirement R2 is now satisfied by a verified citation."
  - Re-run on a `submitted` case returns 409 `rerun_unavailable` and the submission is unchanged.
- [X] T108 [P] [US7] Write `tests/contract/test_app_api_demo_controls.py`.
  - `PUT /api/demo/missing-evidence {"enabled": true}` returns `{"enabled": true}` and the hospital
    mock state is on.
  - `GET /api/config` shows `missingEvidence` true.
  - `POST /api/cases/case-100028/rerun` returns 202 for `needs-evidence` and 409
    `rerun_unavailable` with "A submitted appeal cannot be re-run. Reset the demo first." for
    `submitted`.
- [X] T109 [US7] Add task create, keep, and close to `src/reclaim/steps/build_matrix.py`, using the
  R2 question map and template from data-model.md §6. Add `upsert_task`, `close_task`, and
  `list_tasks` to `src/reclaim/repo.py`.
- [X] T110 [US7] Update three files:
  - `src/reclaim/demo.py`: `set_missing_evidence(ctx, enabled)`, which calls the hospital
    `/_control`.
  - `src/reclaim/api.py`: `PUT /api/demo/missing-evidence`, `POST /api/cases/{caseId}/rerun`, and
    the `tasks`, `needsLine`, `actions.canRerun`, and `rerunUnavailableReason` fields.
  - `src/reclaim/pipeline.py`: `rerun_case`, which refuses approved, submitted, in-review, paid,
    and other-denial, resets status to `new`, and schedules `run_case`.
- [X] T111 [US7] Update three files:
  - `web/app/page.tsx`: presenter bar "Missing-evidence toggle".
  - `web/app/cases/[caseId]/page.tsx`: the "Needs N item(s)" line, a "Re-run" button (or the
    unavailable explanation), and the clinician request list.
  - `web/app/cases/[caseId]/MatrixTab.tsx`: a red R2 row with the reason.

**Checkpoint (showable)**: in replay mode, start from a fresh state (the Reset button comes in Phase 11):
`docker compose down && rm -f .local/data/reclaim.db .local/sftp/outbound-835/* && make demo`.
Then turn the Missing-evidence toggle on, click Simulate incoming remit, and open the case. It shows "Needs 1 item", R2 red, no letter, Approve disabled, and
one clinician request.

---

## Phase 11: User Story 8 - Demo operations (Priority: P3)

**Goal**: one-action reset; mode and date always visible.

**Independent Test**: after a full demo, reset clears everything and the payer accepts a fresh
submission (201).

- [X] T112 [P] [US8] Write `tests/integration/test_reset.py`, starting from a submitted hero case
  with the toggle on and tasks present.
  - `POST /api/demo/reset` returns 204.
  - Every repo table is empty, the inbox is empty, and the hospital toggle is off.
  - The payer mock has no appeals: a fresh submission returns 201, not a 200 replay.
  - `GET /api/config` still has `aiMode` replay.
- [X] T113 [US8] Update three files:
  - `src/reclaim/demo.py`: `reset_demo(ctx)`, which calls `repo.reset_all`, `RemitInbox.clear`,
    hospital `/_control/reset`, and payer `/_control/reset`, and clears the poller's seen-file set.
  - `src/reclaim/api.py`: `POST /api/demo/reset`.
  - `Makefile`: the `reset` target also runs `rm -f .local/sftp/outbound-835/*` when the app is down.
- [X] T114 [US8] Update two files:
  - `web/app/page.tsx`: presenter bar "Reset demo" button with a confirm.
  - `web/app/components/Header.tsx`: "AI: live"/"AI: replay" always rendered, and base URLs
    refreshed after reset.

**Checkpoint (showable)**: complete the demo, click Reset demo, and the queue is empty. Steps 1–6
run again with a fresh confirmation.

---

## Phase 12: Hardening (after MVP)

- [X] T115 [P] [US4] Write `tests/integration/test_deadline_warning.py`. With the payer mock
  decision `appealDeadline` overridden to 2026-10-15, the case `deadline.warning` names both
  October 15, 2026 and October 19, 2026, and `deadline.line` uses October 15.
- [X] T116 [US4] Render `deadline.warning` as a visible warning in
  `web/app/cases/[caseId]/PacketTab.tsx` and `web/app/cases/[caseId]/MatrixTab.tsx`.
- [X] T117 [P] [US1] Write `tests/integration/test_repeat_claim.py`. A second, different 835
  (fixture text with a new ISA13, GS06, and TRN02, built in-test) that repeats `HSP-CLM-100028`
  creates no second case and adds a "later remittance" audit event to `case-100028`.
- [X] T118 [US1] Make T117 pass in `src/reclaim/steps/ingest.py`: an existing `hospital_claim_id`
  writes a case audit event instead of an upsert.
- [X] T119 [P] [US4] Write `tests/integration/test_llm_failures.py`.
  - A live client raising a 500 twice fails `build_matrix` visibly: status stays
    `evidence-gathered`, `last_error` is set, the audit event shows the error, and no replay is
    used.
  - `ReplayMissError` behaves the same.
  - `GET /api/config` still reports the original mode.
- [X] T120 [US4] Make T119 pass in `src/reclaim/pipeline.py`, including the `last_error` text shown
  on the timeline.
- [X] T121 [P] [US6] Write `tests/unit/test_status_wording.py`. For each status from `new` to
  `approved` and for a `refused` submission, the case detail JSON built by `src/reclaim/api.py`
  contains none of "filed", "Submitted", "submitted" (outside the `status` enum field), or "won".
- [X] T122 [P] Write `tests/unit/test_pipeline_concurrency.py`.
  - With `LLM_CONCURRENCY=4` and 6 cases whose fake step sleeps, at most 4 run at once.
  - Steps inside one case run in order.

---

## Phase 13: Polish & Cross-Cutting Concerns

- [X] T123 Create `web/playwright.config.ts` (baseURL http://localhost:3000, chromium) and
  `web/e2e/demo.spec.ts`. The spec runs in replay mode:
  1. Reset demo.
  2. Simulate incoming remit and assert the A9 step 1 texts.
  3. Open the case and assert 6 passed checks.
  4. Evidence tab: "1 record excluded (outside 6-month lookback)" and
     "MedicationRequest: 0 found".
  5. Matrix tab: "Policy NST-IMG-2026-04 v2026.04".
  6. Packet tab: the four step 5 lines.
  7. Persona billing-approver-01, Approve and submit, then assert
     "Submitted · Northstar confirmation NST-APL-80126 · expected resolution 14 days" and
     "In review" within 45 s.

  Every page asserts "SYNTHETIC DEMO DATA", "Demo date: 2026-09-12", and "AI: replay".
- [X] T124 Update the `Makefile` `test` target to run:
  1. `uv run pytest`
  2. `LLM_MODE=replay docker compose up -d --build --wait`
  3. `RECLAIM_DOCKER_TESTS=1 uv run pytest -m docker`
  4. `npx playwright test` in `web/`
  5. `docker compose down`, always, even on failure

  Confirm the `docker` marker is registered in `pyproject.toml`.
- [X] T125 [P] Write `docs/explain/ingest.md`, `docs/explain/fetch_claim.md`, and
  `docs/explain/resolve_identity.md`. Each is one paragraph: what it reads, what it decides, and
  what production replaces (a real clearinghouse SFTP or API, the hospital's claim archive, the
  enterprise MPI or claim map).
- [X] T126 [P] Write `docs/explain/gather_evidence.md`, `docs/explain/payer_context.md`, and
  `docs/explain/build_matrix.md`, one paragraph each with the same three points. Production
  replacements are SMART Backend Services at the hospital FHIR endpoint, payer-specific
  PayerAdapters, and BAA/zero-data-retention LLM terms.
- [X] T127 [P] Write `docs/explain/draft_packet.md`, `docs/explain/approve_and_submit.md`, and
  `docs/explain/track.md`, one paragraph each with the same three points. Production replacements
  are real SSO roles, payer portal or clearinghouse submission, and the Batch API for backlogs.
- [X] T128 [P] Write `README.md`: what Reclaim is (one paragraph, "SYNTHETIC DEMO DATA"), a
  quickstart (`make setup`, `make test`, `make demo`, the 6 clicks, `make reset`) linking
  `specs/001-denial-recovery/quickstart.md`, the architecture in 5 bullets, and "never put keys
  anywhere but `.env`".
- [X] T129 Run a dead-code sweep over `src/reclaim/`, `mocks/`, `scripts/`, and `web/`.
  - For every function, class, route, and component, `rg` for callers in the demo path or tests.
  - Record the findings in `specs/001-denial-recovery/dead-code-sweep.md`, listing each unused
    symbol with its file.
  - Delete unused code in follow-up tasks of at most 3 files each, added via `/speckit-converge`.
- [ ] T130 Verify a clean clone passes.
  - `git clone` the repo into a fresh temp directory, `cd` into it, and run `make setup` then
    `make test` with no pre-existing `.env` or `.local/`.
  - Record the pass/fail output summary in `specs/001-denial-recovery/quickstart.md` under a
    "Clean clone verified" line with the date.
  - Any failure becomes a new task.

---

## Dependencies & Execution Order

- **Setup (Phase 1)** comes first. T005 depends on T004, T006 depends on T003 and T005, and T007
  follows T006.
- **Foundational (Phase 2)** depends on Setup and blocks every story.
  - Fixture tests come before their fixtures.
  - T024 (config) comes before T026–T043.
  - T028 (repo) comes before T030 (audit).
  - T032 (protocols) comes before T034, T041, and T043.
- **US1 (Phase 3)** → **US2 (4)** → **US3 (5)** → **US4 (6)** → **US5 (7)** → **US6 (8)**. These
  are sequential, because each extends the same pipeline, `api.py`, and case page. Each phase
  ends in a showable checkpoint.
- **T103 (recording)** needs T102 and a working US4 and US5 pipeline. The replay-mode MVP
  checkpoint (T104) needs T103.
- **Post-MVP**: Phase 9 (US2 UI), Phase 10 (US7), Phase 11 (US8), then Phase 12 (hardening).
  Phases 9, 11, and 12 touch shared files (`api.py`, `page.tsx`), so run them in order. Their
  test tasks marked [P] can be written together.
- **Polish (Phase 13)**: T123 needs T103 and T111. T124 needs T123. T129 and T130 run last.

## Parallel Examples

```text
# Phase 2 fixtures (all independent files):
T009, T011, T014, T021 (tests) then T010, T012, T013, T015, T016, T017, T018, T019, T020

# Phase 2 core tests together:
T023, T025, T027, T029, T033, T036, T038, T040, T042

# US1 tests together:
T046, T047, T048, T049

# US4 tests together:
T073, T074, T075, T076   (T077 edits tests/fakes.py, run after)

# US5 tests together:
T086, T087, T088, T089

# Docs:
T125, T126, T127, T128
```

## Implementation Strategy

1. **MVP (Phases 1–8)**:
   - Build the thinnest end-to-end happy path for A9 steps 1–6.
   - Stop at each phase checkpoint and show it.
   - US4 and US5 checkpoints use live mode, or the integration tests if no key is available.
   - T103 records replay, then T104 proves the whole MVP in replay mode with no key.
2. **Post-MVP increments**: needs-review UI (Phase 9) → missing-evidence toggle (Phase 10) →
   reset (Phase 11) → hardening (Phase 12). Each one is demoable on its own.
3. **Finish**: Playwright smoke, explain docs, README, dead-code sweep, clean-clone verification.
4. **Commit** after each phase with `make test` green (Constitution Development Workflow).
