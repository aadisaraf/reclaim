# Research: Reclaim Evidence-First Denial Recovery

Phase 0 output for [plan.md](plan.md). Versions were checked on 2026-09-12. Scope is a
**local-only hackathon demo** that runs on one laptop. Anything production-only is noted as such
and not built.

Each entry has three parts: Decision, Rationale, and Alternatives.

---

## 1. Runtime and pinned versions

**Decision**
- Python 3.12 (3.12.14), with uv 0.12.13 managing `pyproject.toml` and `uv.lock`.
- Python packages: FastAPI 0.141.1, Pydantic 2.13.5, httpx 0.28.1, uvicorn 0.52.4, pytest 9.1.1,
  pytest-asyncio 1.4.0, paramiko 5.0.0, reportlab 5.0.1, openai 3.13.0, fhir.resources 8.3.0
  (tests only).
- Web: Next.js 16.3.5 on Node ≥ 20.9, and @playwright/test 1.63.0. Both are locked in
  `web/package-lock.json`.

**Rationale**
- These match the plan input.
- Pinning everything in lockfiles satisfies Constitution VIII and fixes Appendix B #2.

**Alternatives**: Poetry and pip-tools were rejected. uv was named in the plan input, and it is
the fastest option on a clean clone.

## 2. OpenAI SDK transport and retries

**Decision**
- Build the client as `OpenAI(api_key=...).with_options(timeout=45.0, max_retries=0)`.
- Our own wrapper retries **once** with jittered backoff (1–3 s), and only on 429 or 5xx.
- The app's own HTTP clients (EHR, payer) use `httpx`.
- LLM tests inject a fake `LlmClient` (see [contracts/adapters.md](contracts/adapters.md)) rather
  than patching the SDK transport.

**Rationale**
- openai 3.13.0 depends on `httpx2>=2.7,<3`, not `httpx`. The plan's "httpx" therefore covers only
  our own clients, and any explicit timeout object for OpenAI must be an `httpx2.Timeout` (a plain
  float also works).
- By default the SDK retries twice, including on 408, 409, and connection errors. That breaks the
  plan's rule of "one retry on 429/5xx only", so SDK retries are turned off.

**Alternatives**: keeping SDK retries was rejected because it breaks the retry rule.

## 3. LLM request design

These choices are required by the plan input. Each one is implemented in
`src/reclaim/adapters/llm.py` and the two prompt modules.

| # | Decision | Rationale |
|---|---|---|
| 3.1 | **Exactly 2 calls per happy-path case** (`build_matrix` and `draft_packet`) and **1** in missing-evidence mode, because the packet is never drafted. Parsing, identity, policy selection, lookback, verification, deadline math, and PDFs are code. | Keeps cost per denial small and predictable. Everything that can be checked is deterministic. |
| 3.2 | `build_matrix` is **one call for all requirements**. Its input is the lookback-filtered candidates only, trimmed to `resourceType`, `id`, date, and text-bearing fields (`code.text`/`display`, `note[].text`, `conclusion`, `valueQuantity`, decoded Binary text). | One call is 3× cheaper than one per requirement. Trimming follows the minimum-necessary rule, and the whole chart is never sent. |
| 3.3 | **Structured Outputs**: `client.responses.parse(text_format=<Pydantic model>)`. Schemas follow strict-mode rules: every field required, optional fields are `X \| None`, no `allOf`, object root. | No free-text JSON parsing. A malformed output fails validation and the step fails visibly. |
| 3.4 | **Reasoning effort** comes from env: `build_matrix` = `medium`, `draft_packet` = `low`. If the verifier rejects **any** proposed citation, `build_matrix` is retried **once** at `high`, with the rejection reasons appended as the last input message. A requirement that still lacks a verified citation becomes `missing`. | Spend more only when verification fails. gpt-5.6-luna accepts none, low, medium, high, xhigh, and max. |
| 3.5 | **Prompt caching**: input order is (1) instructions, (2) output rules, (3) policy JSON, then (4) case evidence last. `prompt_cache_key` = `policyId`. No explicit breakpoints, and `prompt_cache_options` is not set (the 30-minute TTL is the default and the only value). `prompt_cache_retention` is deprecated and not used. | Repeated cases under one policy share the prefix. **Caching only starts at a prefix of 1,024 tokens or more**, and our static prefix may be shorter, so we claim no caching savings unless `cached_tokens > 0` is actually logged. |
| 3.6 | `store=false` on every request. | Constitution security posture. |
| 3.7 | `max_output_tokens` (this cap includes reasoning tokens): `build_matrix` medium 6,000; `build_matrix` high retry 12,000; `draft_packet` 3,000. An `incomplete` response fails the step. | Caps runaway cost. The high-effort retry gets extra room to reason. |
| 3.8 | 45-second request timeout; one jittered retry on 429/5xx (see 2). | Plan input. |
| 3.9 | An `asyncio.Semaphore(LLM_CONCURRENCY=4)` wraps each case's pipeline run. Steps inside a case stay sequential. | Cases are independent. Keeps a simultaneous burst polite to rate limits. |
| 3.10 | **Token logging and cost**: each LLM step's audit event records `input_tokens`, `input_tokens_details.cached_tokens`, `output_tokens`, and `output_tokens_details.reasoning_tokens`. Cost = (input − cached) × `PRICE_INPUT_PER_M` + cached × `PRICE_CACHED_INPUT_PER_M` + output × `PRICE_OUTPUT_PER_M`, with defaults $0.20, $0.02, and $1.20 per 1M tokens (config, overridable by env). The UI labels the total "AI cost for this case (estimate)". | The pitch uses a number computed from measured usage. The cache-write surcharge (1.25× input) and the pricing tier above 272K input tokens are not modelled; our inputs are far below 272K. |
| 3.11 | **Batch API is a production note only** (gpt-5.6-luna supports it at half price) for aged-backlog runs. Not built. | Plan input. |
| 3.12 | **Letter structure**: code renders the header, opening, requested action ("Please reconsider and reprocess payment"), attachment list, approver line, version, and footer. The LLM writes **body statements only**. Every body statement must cite at least one verified citation; the body has no "non-factual" statement kind. | The citation rule can't be dodged by labelling a sentence non-factual. Header fields are copied data (see the Clarifications in spec.md). |

## 4. Replay mode

**Decision**
- `LLM_MODE=live|replay` comes from env, and the default in `.env.example` is `replay`.
- Replay key = SHA-256 of canonical JSON `{model, effort, instructions, input}`.
- File: `fixtures/llm-replay/<step>-<key16>.json` containing
  `{step, key, model, effort, output, usage}`. Outputs and usage only; no headers, IDs, or keys.
- On a miss, raise `ReplayMissError(step, key)`. The step fails visibly with no fallback and no
  mode switch. Replayed outputs are re-validated against the same Pydantic model.
- `make record` runs `scripts/record_replay.py` with `LLM_MODE=live LLM_RECORD=1`. It runs the
  happy case, then the missing-evidence case. It writes files **only if** the outcomes match
  Appendix A: 3/3 satisfied with R1→condition-100 + note-progress-031, R2→treatment-note-022,
  R3→order-901; missing mode gives R2 missing with the A8 reason text.

**Rationale**
- The demo is repeatable offline (SC-001 under 10 s in replay).
- FR-036: every replayed response is a real recording.
- Changing fixture text or a prompt changes the key, so a stale recording can never be used by
  mistake.

**Alternatives**: VCR-style HTTP cassettes were rejected because they capture headers (a secrets
risk) and break on SDK transport changes.

**Known limit**
- In live mode the model writes the R2 `reason` text, so its wording can differ from A8.
- The recorded replay, which is what the demo uses, is checked to match A8 exactly.
- The "Needs 1 item" count and the task text are code-generated and always exact.

## 5. FHIR fixture validation

**Decision**
- Validate each fixture in `tests/fixtures/test_fhir_fixtures.py` with fhir.resources 8.3.0
  **R4B** models (`from fhir.resources.R4B.<type> import <Type>`).
- Add hand-written R4 checks for the two R4→R4B differences (the allowed reference targets of
  `Observation.subject` and `DiagnosticReport.subject`), plus the Appendix A5 values.

**Rationale**
- fhir.resources has had no R4 subpackage since 7.0.0. R4B equals R4 for the other 13 resource
  types we serve.
- It is pure Python on Pydantic v2, so it fits `make test` with no Java.

**Alternatives**: the HL7 validator_cli 6.10.4 was rejected. It is 201 MB, needs Java 17+, and
downloads packages at runtime, which is too heavy for a laptop demo and breaks offline tests.

## 6. SFTP mock clearinghouse

**Decision**
- Use `atmoz/sftp` as compose service `mock-clearinghouse` with `platform: linux/amd64` and user
  `reclaim` (password from `.env`).
- Mounted dirs: `/home/reclaim/outbound/835` (empty at start) and `/home/reclaim/claim-archive/837`
  (seeded from `fixtures/x12/`).
- `make setup` generates an ed25519 host key into `.local/sftp/` (gitignored) and a matching
  `known_hosts`.
- The app uses paramiko 5.0.0 (`listdir_attr`, `getfo`, `putfo`).

**Rationale**
- A remit arrives on its own over the transport clearinghouses actually use.
- **Concern (not a blocker)**: atmoz/sftp publishes amd64 only and is barely maintained (last
  commit 2024-09). On Apple Silicon, Docker Desktop runs it under emulation, which is fine for a
  two-file demo.
- paramiko 5 removed SHA-1 `ssh-rsa`, so the host key must be ed25519.

**Alternatives**: `drakkan/sftpgo` v2.7.5 is multi-arch and maintained, and is the swap if
emulation fails on a teammate's machine. A plain watched folder was rejected (see Complexity
Tracking in plan.md).

**Inbox rules**
- The poller lists the inbox every 1 s.
- It downloads only files whose `(name, size, mtime)` it hasn't seen in this process.
- It dedupes by SHA-256 in SQLite.
- Files are never moved or deleted by ingest, so repeat-delivery tests are simple.

## 7. X12 parsing

**Decision**: hand-written tokenizer plus 835 and 837P loop readers, as specified in
[contracts/x12-fixtures.md](contracts/x12-fixtures.md). No EDI library.

**Rationale**: about 300 lines cover the segments we need, each rule is testable, and nobody has
to explain a library. It also fixes Appendix B #3.

**Alternatives**: `pyx12` and `badx12` were rejected as heavy or unmaintained, and hard to explain.

## 8. Storage

**Decision**: one SQLite file (`.local/reclaim.db`) through stdlib `sqlite3`, behind
`src/reclaim/repo.py`. No ORM. Tables are in [data-model.md](data-model.md).

**Rationale**: one database (Constitution VII; Appendix B #1). Reset means delete the rows.

**Alternatives**: Postgres and an ORM were rejected as unneeded for a single-user laptop demo.

## 9. PDFs

**Decision**
- reportlab 5.0.1 with `invariant=1` and built-in Helvetica only.
- `scripts/make_denial_letter.py` generates `fixtures/payer/denial-letter.pdf`, which states the
  October 19, 2026 deadline and "SYNTHETIC DEMO DATA".
- `src/reclaim/pdf.py` renders the appeal packet PDF. Every page footer says
  "SYNTHETIC DEMO DATA".

**Rationale**
- `invariant=1` produces byte-identical output, which was confirmed with a built-in font.
- Identical bytes make the payer's "same ID, same bytes → 200" upload rule and packet hashing
  deterministic.

**Alternatives**: WeasyPrint was rejected because it needs system libraries, which are painful in
Docker on macOS.

## 10. Frontend (override of the prompt pack)

**Decision**
- **Next.js 16 App Router**, with the user's typed plan input overriding the prompt pack's
  Vite/React.
- Client components only. Two pages: `/` (queue plus presenter bar) and `/cases/[caseId]` (tabs:
  Identity, Evidence, Matrix, Packet, Timeline).
- `web/Dockerfile` uses `output: 'standalone'`.
- The browser calls the app API at `NEXT_PUBLIC_API_BASE` (default `http://localhost:8000`).
  CORS on the app allows `http://localhost:3000`.
- Polling: the queue refreshes every 1 s; a case page refreshes every 1 s while `running` is true
  or the status is `submitted`.
- R1–R3 "turn green one by one" is a 400 ms CSS stagger on first render. It's cosmetic; the data
  is already final.

**Rationale**
- `NEXT_PUBLIC_*` values are inlined at build time. That's fine for localhost, and the configured
  **mock base URLs are shown from `GET /api/config`** at runtime, not baked into the bundle.
- No server components are needed, so there's no server state to explain.

**Alternatives**: Vite + React (prompt pack) was overridden by the user. FastAPI templates were
not chosen.

## 11. Mock hosts, TLS, and tokens (local shortcuts)

**Decision**
- Compose network aliases `mock-hospital.example` and `mock-northstar-health.example` serve plain
  **http** on port 80. The configured base URLs are
  `http://mock-hospital.example/fhir/R4` and `http://mock-northstar-health.example/api/v1`.
- `make setup` copies `.env.example` to `.env` if it is missing and fills random mock tokens
  (`python -c "import secrets; ..."`). The OpenAI key is left blank for the user to add.

**Rationale**
- Hostnames and paths match A5/A6.
- **Deviation**: the scheme is http, not the https in Appendix A, because TLS certificates add
  setup with no demo value on one laptop. Production uses https.
- No secret is ever committed.

**Alternatives**: self-signed TLS was rejected as extra setup steps for no demo benefit.

## 12. Tests and `make test`

**Decision**
- `make test` runs `uv run pytest`, then the Playwright smoke test.
- The smoke test brings the compose stack up in replay mode (`docker compose up -d --wait`), runs
  `npx playwright test`, and takes the stack down.
- Pytest itself needs no Docker. Mock apps run in-process through `httpx.ASGITransport`, and SFTP
  is replaced by an in-memory `RemitInbox` and `ClaimArchive` in unit and integration tests.
- The paramiko adapters are exercised by the Playwright smoke test through the real container.
- Expected values are written by hand from Appendix A. Nothing is snapshot-generated.
- LLM-dependent integration tests (for example the end-to-end missing-evidence path) use a
  hand-written fake `LlmClient`, so they pass before any recording exists.

**Rationale**: a clean clone passes `make test` (Constitution VIII), and the fast inner loop is
plain `uv run pytest`.

**Alternatives**: a separate `make e2e` target was rejected because the plan input fixes the
list of targets.

## 13. Time and identities

**Decision**
- `DEMO_TODAY=2026-09-12` is in config for the app and the payer mock, and the UI header shows it.
- The payer mock returns A6's fixed `receivedAt` `2026-09-12T18:32:00Z`. It moves an appeal to
  `in-review` when real elapsed time since the POST is 30 s or more; at that point `updatedAt` is
  `2026-09-12T18:32:30Z`.
- The persona comes from the `X-Persona` header, checked server-side against `GET /api/personas`
  (`billing-approver-01` with role `authorized-billing-user`; `viewer-01` read-only). There are no
  passwords.

**Rationale**: deadlines never drift (A1). The persona picker replaces login, as the constitution
requires.

## 14. Items added beyond the plan input (flag for review)

Each item is small and directly needed by a spec requirement or test. Nothing else was added.

1. Mock control endpoints under `/_control/` (hospital toggle and reset, payer reset). These are
   needed for the presenter toggle and `make reset`, and they are labelled "not part of A6".
2. Payer mock `400 invalid_request` (missing Idempotency-Key or bad body) and
   `404 appeal_not_found`. A6 doesn't define them, but the mock needs some response for these
   cases.
3. Identity check: `Encounter.subject` must reference the mapped patient, recorded with the
   Encounter date check. This guards against a claim-map error.
4. An 837 with frequency code 7 goes to `needs-review` with field `claimFrequency`. Corrected
   claims are out of scope and must not be worked.
5. Minimum excerpt length of 12 characters in the verifier, so a trivial excerpt like "pain"
   can't pass as verbatim evidence.
