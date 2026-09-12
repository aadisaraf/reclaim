# Reclaim: Spec-Kit Prompt Pack

Evidence-first denial recovery agent. Everything you need to take a fresh repo from nothing to a working demo with GitHub Spec Kit, in order, as paste-ready prompts.

**Core claim (the pitch line every artifact serves):** "We do not just generate appeal letters. We turn a denial stream into a verified, source-cited appeal case, and we isolate the exact evidence gap before a hospital employee wastes time hunting through charts."

---

## 0. How to use this file

1. Do the terminal setup in section 1.
2. Copy **this whole file** into the new repo as `docs/reclaim-speckit-prompts.md`. Several prompts tell the agent to read Appendix A (the canonical demo data) and Appendix B (mistakes from the last repo), so the file must be in the repo.
3. Open a Claude Code chat **in the new repo**. Paste the priming message (section 2), then paste each prompt below in order. Every prompt is in its own code block.
4. Don't skip the gates. Clarify comes before plan, analyze before implement, converge after implement.
5. Commit after every step (`git add -A && git commit -m "spec-kit: <step>"`). Spec-kit rewrites files, and commits make every step undoable.

### The flow

```text
constitution → specify → clarify → plan → checklist ×3 → resolve checklists
    → tasks → analyze → remediate → implement (phase by phase)
    → converge → implement convergence tasks → converge again (until clean)
    → explain-it drill (not spec-kit; for the "explain every part" rule)
```

### Every command, what it does, and whether you need it

Written against **Spec Kit v1.0.6** (released 2026-09-10). In Claude Code every command is a skill in `.claude/skills/`, invoked with hyphens (`/speckit-plan`). Docs and other agents use dots (`/speckit.plan`); same commands. Claude Code shows no "next step" buttons, so type each command yourself.

Spec Kit calls seven commands "core" and three "optional enhancements". For this project, run everything except taskstoissues.

| Command | Type | Run it when | Reads | Writes | Asks you questions? |
|---|---|---|---|---|---|
| `/speckit-constitution` | Core | Once per project; again only to amend | existing constitution | `.specify/memory/constitution.md` only, with a Sync Impact Report comment and a semver bump. It no longer rewrites other templates. | Only if critical info is missing |
| `/speckit-specify` | Core | Once per feature | constitution, spec template | New `specs/NNN-short-name/spec.md`, `checklists/requirements.md`, `.specify/feature.json` (the "active feature" pointer). With the git extension it also creates a branch. | Up to 3 `[NEEDS CLARIFICATION]` questions, all at once, with option tables |
| `/speckit-clarify` | Optional | After specify, before plan (re-runnable) | spec, constitution | `## Clarifications` session in spec.md, plus edits to the affected sections; re-ticks `requirements.md` | Up to 5, one at a time, each with a recommended answer ("yes" accepts, "done" stops) |
| `/speckit-plan` | Core | After clarify | spec, constitution | `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`. Stops before tasks. | No, but it ERRORs on unjustified constitution violations |
| `/speckit-checklist` | Optional | After plan (it needs plan.md), before tasks | spec, plan, tasks if present | `checklists/<domain>.md` with `CHK###` items (appends if the file exists) | Up to 3 scoping questions, plus 2 follow-ups |
| `/speckit-tasks` | Core | After plan and checklists | plan, spec, data-model, contracts, research, quickstart | `tasks.md` in `- [ ] T001 [P] [US1] description with file path` format. Tests only if you ask. | No |
| `/speckit-analyze` | Optional | After tasks, before implement | spec, plan, tasks, constitution | Nothing (read-only report; constitution conflicts are always CRITICAL) | Offers remediation at the end; never applies it on its own |
| `/speckit-implement` | Core | After analyze is clean | tasks, plan, data-model, contracts, research, quickstart, constitution, checklists | Code, ignore files, `[X]` marks in tasks.md (re-runs resume from the marks) | **Stops if any checklist item is unchecked** and asks yes/no |
| `/speckit-converge` | Core | After every implement pass | spec, plan, tasks, constitution, the code | Appends `## Phase N: Convergence` tasks to tasks.md. Never edits code, spec, or plan. Leaves the file untouched when converged. | No |
| `/speckit-taskstoissues` | Core (situational) | Only if you track work in GitHub Issues | tasks.md, git remote | One GitHub issue per task, `T001: ...` (skips existing ones) | No. Needs a GitHub remote and the GitHub MCP server |
| `/speckit-agent-context-update` | `agent-context` extension | Automatically offered after specify and plan; manually after re-planning | latest `specs/*/plan.md` | The block between `<!-- SPECKIT START -->` and `<!-- SPECKIT END -->` in `CLAUDE.md` | No. Without this extension, nothing ever updates CLAUDE.md |
| `/speckit-git-*` | `git` extension | See section 12 | git state | repo init, feature branches, optional auto-commits | No |

**Checklist marks belong to people.** In v1.0.6 the agent never ticks custom checklist items, and implement never edits them. A `[x]` means a teammate reviewed that requirement and agrees it is well written. That's why section 7 has a human review step.

**Hooks:** extensions register hooks in `.specify/extensions.yml` (for example `after_plan`). Optional hooks show up as a suggestion at the end of a command; mandatory hooks run automatically. Hook names with dots become hyphens: `speckit.git.commit` is `/speckit-git-commit`.

**Active feature:** commands find the current feature through `.specify/feature.json`, not the git branch. `git checkout` alone does not switch features. To work on another one, edit that file or set `SPECIFY_FEATURE_DIRECTORY=specs/002-foo`.

---

## 1. Setup (terminal)

Start a **new repo**. The old `Healtcare-RCM-Denial-Recovery-Agent` repo runs Spec Kit 0.11.3 and carries the architecture we're replacing.

Requirements: Python 3.11+, uv, git, Docker, Node 20+.

Install the pinned CLI:

```bash
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@v1.0.6
```

Check that it's ready:

```bash
specify check
```

Create the project for Claude Code, with the git and agent-context extensions:

```bash
specify init reclaim --integration claude --script sh --extension git --extension agent-context
```

Then:

```bash
cd reclaim && mkdir -p docs
```

Copy this file into `reclaim/docs/reclaim-speckit-prompts.md`, then start Claude Code inside `reclaim/`.

Notes:
- **Old flags are gone.** `--ai claude`, `--ai-skills`, and `--no-git` were removed in v0.10. Tutorials that still use them are out of date.
- **Git is set up for you.** The `git` extension creates the repo when you run `/speckit-constitution` and a feature branch when you run `/speckit-specify`. Auto-commit is off by default, so commit yourself after each step.
- **CLAUDE.md needs `agent-context`.** That extension keeps a pointer to the current plan in `CLAUDE.md`. Without it, CLAUDE.md is never touched.
- **Upgrading later:** `specify self upgrade`, then `specify integration upgrade claude`, then `specify extension update`. Commit before upgrading.

**API key (do this after implement Phase 1, not now):** Phase 1 creates `.gitignore` and `.env.example`. Only then run `cp .env.example .env` and paste your OpenAI key into `.env` in an editor. Confirm git ignores it:

```bash
git check-ignore .env
```

It must print `.env`. Never paste the key into a chat prompt, this file, a fixture, a replay file, or a commit.

---

## 2. Priming message (paste first, in the new repo)

```text
We are building "Reclaim", an evidence-first denial recovery agent, using GitHub Spec Kit. Read docs/reclaim-speckit-prompts.md fully before doing anything: sections 0 to 2, Appendix A (canonical demo data and contracts, the source of truth for every identifier, code, date, amount, and endpoint), and Appendix B (mistakes from our last attempt that we must not repeat).

Ground rules for this whole session:
- Do not write application code until I run /speckit-implement.
- Use Appendix A values verbatim. If anything conflicts with Appendix A, stop and tell me.
- All data is synthetic. Never use or generate real patient data.
- When a spec-kit command asks me a question, always give a recommendation and say why in one sentence.
- Keep the architecture simple enough that each of our 3 to 4 teammates can explain any module in under two minutes. If something needs more infrastructure than the plan allows, stop and ask.
- The AI model is OpenAI gpt-5.6-luna through the Responses API. The key lives only in a gitignored .env. Never ask me to paste a secret into chat, and never write one into any file.

Reply with a 5-line summary of the product and the 6-step demo so I know you have it.
```

---

## 3. Constitution

```text
/speckit-constitution Create the constitution for "Reclaim", an evidence-first denial recovery agent built as a hackathon demo that must also be production-shaped. Read docs/reclaim-speckit-prompts.md Appendix A and Appendix B first. Use exactly 8 core principles. Each has MUST rules and a one-line rationale.

I. Synthetic Data Only (NON-NEGOTIABLE)
- Every patient, member, claim, clinician, payer, policy, letter, and payer response MUST be invented from scratch. No real or "de-identified" records, ever.
- Every screen, generated document, and PDF MUST visibly say "SYNTHETIC DEMO DATA".
- Fixtures in fixtures/ are the only data source. There is no upload path for real data.
Rationale: we show a real hospital workflow without touching PHI, and we say so out loud.

II. Standards-Exact Interfaces
- Where a real standard exists we MUST use it for real: X12 5010 835 (005010X221A1) and 837P (005010X222A1) text with full ISA/GS/ST/SE/GE/IEA envelopes, correct SE segment counts, and 835 balancing (billed minus paid equals adjustments at each level; BPR02 equals total paid); FHIR R4 resources and searchset Bundles with real field names, served as application/fhir+json.
- The X12 parser MUST read its delimiters from the ISA segment, tolerate line breaks between segments, read CAS at claim or service level, and handle REF, DTM, AMT, QTY, and LQ segments after SVC.
- Fixtures MUST pass automated validation tests before any feature code relies on them.
- Where no standard exists (payer portals) we MUST NOT pretend one does. The payer is a clearly labelled mock behind an adapter with a documented contract.
Rationale: judges can check the formats; exact formats are what make "implementable tomorrow" true.

III. Identity Before Evidence (NON-NEGOTIABLE)
- The system MUST NEVER match a patient by name.
- Before any EHR request, the identity gate MUST confirm all of: 835 claim ID equals 837 claim ID; 835 member ID equals 837 member ID; date of service matches; payer ID matches; rendering provider NPI matches; procedure code matches. After the Coverage read, Coverage.subscriberId MUST also equal the member ID.
- Any mismatch or missing identifier MUST set the case to needs-review naming the failing field, and MUST produce zero clinical record requests for that case, provable from the audit log.
Rationale: touching the wrong chart is the one mistake a hospital will not forgive.

IV. Evidence Before Prose (NON-NEGOTIABLE)
- The evidence matrix MUST be built and verified before any appeal text is generated.
- Every citation MUST reference a resource fetched for this case, and every excerpt MUST appear verbatim in that resource or its Binary. A citation that fails verification is discarded and its requirement is marked missing with the reason.
- Every factual statement in the appeal letter MUST cite at least one verified matrix row. Any uncited factual statement blocks the packet.
- If any policy requirement is missing, the system MUST NOT draft an appeal. It MUST create exactly one targeted clinical-evidence-request task per missing requirement.
- The LLM may classify, extract, and phrase. It MUST NOT be the only check on any fact.
Rationale: this is the product. Letters are a commodity; verified evidence is not.

V. Human Approval Before Submission (NON-NEGOTIABLE)
- Nothing reaches a payer until a user with role authorized-billing-user approves a specific packet version that is ready-for-review with every requirement satisfied.
- The UI MUST NOT say "filed" or "submitted" until the payer adapter returns a confirmation ID.
- Every submission MUST send Idempotency-Key appeal-<caseId>-v<packetVersion>, so retries never create duplicate appeals.
Rationale: appeals are legal correspondence; a person signs them.

VI. Adapters at Every Boundary
- Each external system sits behind one small interface: RemitInbox (835 delivery), ClaimArchive (837 lookup), EhrClient (FHIR R4), PayerAdapter (decision, documents, appeals, tracking), PolicyStore (versioned policies selected by payer, plan type, state, procedure, and date of service), LlmClient (live or replay).
- Mocks implement the same interface and contract a production adapter would. Base URLs, tokens, and credentials come from configuration, never code.
- Secrets (the OpenAI API key, mock tokens) live only in a gitignored .env. They MUST NEVER appear in code, fixtures, LLM replay files, logs, audit events, docs, or commits, and a test MUST fail if .env is not ignored.
Rationale: this is the scale story. A new payer or EHR is a new adapter, not a rewrite. And one of our earlier public repos leaked a .env; never again.

VII. Explainable Simplicity
- Every module MUST be explainable by one teammate in under two minutes. Prefer a plain function pipeline over frameworks.
- Forbidden unless plan.md justifies it in Complexity Tracking against a concrete demo need: agent or graph orchestration frameworks, message brokers, task queues, more than one database, Kubernetes, secret vaults, custom auth or password hashing.
- No dead code. Every module is exercised by the demo path or a test. Unused code is deleted, not commented out.
- Every pipeline step writes one human-readable audit event (what it read, what it decided, why) that the UI displays.
Rationale: the judges dock points for any part nobody on the team can explain.

VIII. Honest Verification
- Every dependency MUST be declared in the lockfile. A clean clone MUST pass `make test` and start with `make demo`.
- Tests MUST NOT be circular: never assert a component's output against a snapshot produced by that same component. Expected values come from Appendix A or are written by hand.
- Required negative tests: identity mismatch for each field, forged citation, excerpt not in source, uncited statement, missing requirement, duplicate 835 delivery, duplicate submission, wrong approver role, submission after deadline.
- We never claim accuracy numbers we did not measure. Demo claims are limited to what tests prove.
Rationale: our last repo had missing dependencies and self-confirming tests; we are not repeating that.

Additional sections:
- Security and Privacy Posture: demo scope (synthetic data, local only, persona picker instead of login, mock tokens) versus production requirements we state but do not build (SMART Backend Services auth, a BAA and zero-data-retention terms with the LLM provider, encryption at rest, HIPAA minimum necessary, audit retention). Even in the demo, LLM requests set store=false and send only the lookback-filtered evidence for the case, never the whole chart.
- Scope Boundaries: this release works medical-necessity denials (CARC 50) end to end. Other denials are ingested and labelled with their lane but not worked. Corrected claims (837 frequency code 7) are out of scope.
- Development Workflow: spec-kit flow; commit after each task phase; `make test` green before every commit; docs/explain/ updated whenever a pipeline step changes.
- Governance: semantic versioning; amendments only via /speckit-constitution; /speckit-analyze and /speckit-converge treat any violation as CRITICAL.

Ratification date 2026-09-12. Version 1.0.0.
```

---

## 4. Specify

```text
/speckit-specify Reclaim: evidence-first denial recovery for medical-necessity denials.

Exact demo values (claim IDs, member IDs, codes, dates, amounts, record IDs, on-screen text) are in docs/reclaim-speckit-prompts.md Appendix A. Use them verbatim in acceptance scenarios.

Problem
Hospitals lose money when insurers deny claims. Staff do four slow manual jobs: notice the denial; find the original claim and the correct patient visit; dig through notes, orders, and reports to see whether the insurer was wrong; then write and submit an appeal before the deadline. Existing tools mostly help with the last job. Reclaim automates the investigation: it turns a denial stream into a verified, source-cited appeal case and isolates the exact evidence gap before an employee hunts through charts.

Users
- Billing specialist (authorized billing user): watches the denial queue, reviews packets, approves submission.
- Treating clinician: receives one targeted question, only when evidence is missing.
- Demo presenter: runs the scripted demo and resets it.

User stories (the demo proves them in this order)
1. A denial arrives on its own (P1). A remittance file lands in the clearinghouse inbox when the presenter presses "Simulate incoming remit" (never a manual upload). Within seconds a $4,800 medical-necessity denial appears in the queue. The other claims in the same file are handled correctly: the paid claim creates no work, and the missing-information denial (CARC 16) is labelled "Other denial lane: not handled in this demo" with no chart access.
2. It resolves the denial to the exact claim and visit (P1). The screen shows remittance claim ID, then the original claim, then the patient encounter, with each identity check (claim ID, member ID, date of service, payer, provider, procedure) shown as passed. If any check fails, the case becomes "Needs review", names the failing field, and requests no chart data.
3. It gathers only relevant evidence (P1). Coverage, diagnosis, order, procedure, diagnostic report, observations, and clinical notes appear, each with its source record and date. Records outside the lookback window are excluded, and the screen shows how many were excluded and why.
4. It tests the evidence against the payer's own rules (P1). The payer's decision (reason, deadline, allowed channels, denial letter) and the applicable versioned policy are shown. A requirement-by-requirement evidence matrix fills in, and a row turns green only when a cited, verified excerpt supports it.
5. It generates a cited appeal packet (P1). The case shows "Ready for review", "Evidence completeness: 3/3 policy criteria satisfied", "Appeal deadline: October 19, 2026", and "Expected recovery: $4,800". Selecting any statement in the letter highlights the policy requirement and chart excerpt behind it. The packet contains every item listed in Appendix A.
6. A human approves, the system submits, and tracking begins (P1). Only an authorized billing user can approve. After approval the packet goes to the payer, the confirmation ID and expected resolution time appear, and the case moves to tracking. Submitting twice never creates a second appeal.
7. Missing-evidence mode (P2). A presenter toggle hides the physical therapy note. Re-running the case flips it from "Ready for review" to "Needs 1 item": requirement R2 shows missing, no appeal is drafted, approval and submission are impossible, and exactly one targeted request goes to the treating clinician asking for documentation of prior conservative treatment. Turning the toggle off and re-running restores the ready packet.
8. Demo operations (P3). One action resets the demo to a clean state. The screen always shows whether AI responses are live or replayed from a recorded live run, and shows the fixed demo date.

Cross-cutting requirements
- Every screen and document says "SYNTHETIC DEMO DATA".
- Every pipeline step appears as a timeline entry with what it read, what it decided, and why, in plain English.
- The same remittance file delivered twice creates no duplicate cases.
- Deadlines show days remaining against the fixed demo date. The system warns if the payer's stated deadline disagrees with the policy's appeal window.
- On-screen language never overstates: no "filed" before payer confirmation; no "won" unless the payer says so.

Out of scope
Real patient data, real payer connections, corrected claims, working non-medical-necessity denials beyond labelling, real authentication (a persona picker is enough), payment posting, multi-tenant administration.

Success criteria
- Remit arrival to "Ready for review" in under 60 seconds with live AI, and under 10 seconds with replayed AI.
- 100% of factual statements in the appeal cite at least one verified evidence item.
- 0 clinical record requests for any case that fails an identity check.
- 0 duplicate cases from repeated delivery of the same file, and 0 duplicate appeals from repeated submission.
- Missing-evidence mode produces exactly 1 targeted request naming the unmet requirement, and submission is blocked.
- A presenter completes the 6-step demo in under 3 minutes without typing.
```

When it finishes, check `specs/001-*/checklists/requirements.md`. If it asks up to 3 questions, answer with the letter or "use your recommendation".

---

## 5. Clarify

```text
/speckit-clarify Focus on identity-gate failure behavior, evidence sufficiency, the meaning of "relevant evidence", packet versioning, and demo reset and replay. These decisions are already made. Apply them if they come up and do not ask about them again:
- Lookback window: records dated within 6 months before the date of service, plus the encounter itself. Everything else is excluded and counted.
- Evidence status values are only "satisfied" or "missing". A citation that fails verification counts as missing, and the reason is recorded.
- Any edit to a packet creates a new version (v1, v2, ...). Approval and the idempotency key belong to exactly one version.
- A billing specialist may edit letter wording but may not add a factual statement without a citation.
- Needs-review cases are resolved only by a person choosing the correct claim mapping. The system never auto-retries a mismatched identity.
- Deadline source of truth is the payer decision's appealDeadline. The policy's appeal window is a cross-check that raises a warning when they disagree.
- Tracking polls the payer. The demo payer returns "received", then "in-review" 30 seconds later.
- The demo runs on a fixed date, DEMO_TODAY=2026-09-12, shown on screen, so deadlines and days remaining never drift after the event.
- Replay mode uses responses recorded from a real live run, and the UI always shows which mode is active.
For anything else, recommend the option that keeps the demo simplest to explain.
```

Reply "yes" to accept a recommendation. Stop early with "done" once the remaining questions are low impact.

---

## 6. Plan

```text
/speckit-plan Build Reclaim as one small repo that a 3 to 4 person team can fully explain. Read docs/reclaim-speckit-prompts.md Appendix A (canonical fixtures and contracts) and Appendix B (last attempt's mistakes) first. Use Appendix A values verbatim. If Appendix A and the spec conflict, stop and report it.

Tech stack (keep it unless research.md documents a concrete blocker)
- Backend and pipeline: Python 3.12, FastAPI, Pydantic v2, httpx. Dependencies managed with uv (pyproject.toml plus uv.lock). SQLite through the standard library sqlite3 module behind one small repository module. No ORM.
- X12: a hand-written tokenizer (delimiters from ISA) plus 835 and 837P loop readers. No EDI library.
- SFTP: docker image atmoz/sftp as service "mock-clearinghouse"; paramiko for polling and for the simulate-remit upload. The 837 archive is pre-seeded from fixtures; the 835 inbox starts empty.
- Mock EHR: a separate small FastAPI app, service "mock-hospital", serving FHIR R4 fixtures at /fhir/R4 with read and search (searchset Bundles, application/fhir+json, OperationOutcome errors). It requires a Bearer token from its own /auth/token (client_credentials) and publishes /.well-known/smart-configuration. It supports a presenter-only control endpoint that hides DocumentReference/treatment-note-022 and Binary/treatment-note-022. Fixture validation in tests with fhir.resources R4B models or the HL7 validator; decide in research.md.
- Mock payer: a separate small FastAPI app, service "mock-northstar-health", implementing Appendix A6 exactly under /api/v1.
- AI: OpenAI Python SDK, Responses API, model from env OPENAI_MODEL (default gpt-5.6-luna), key from env OPENAI_API_KEY loaded from a gitignored .env. LLM_MODE=live|replay. Replay reads fixtures/llm-replay/, keyed by a hash of (model, reasoning effort, instructions, input), and fails loudly on a cache miss. Replay files store outputs and token usage only, never headers or keys.
- PDF: reportlab, both for the synthetic denial letter (generated by a script into fixtures/) and for the appeal packet.
- Frontend: Vite, React, TypeScript. Poll the app API once per second while a case is running. No SSR framework.
- Orchestration: one plain async pipeline function that runs named steps in order and persists case state plus an audit event after each step. The ingestion poller is a background asyncio task started with the API. No Celery, Redis, LangGraph, Kubernetes, or vault.
- Local run: docker compose with services app, web, mock-clearinghouse, mock-hospital, mock-northstar-health. All base URLs from env. The UI shows the configured base URLs.
- Make targets: setup, test, demo (compose up and seed), reset (clear SQLite, empty the 835 inbox, reset mock toggles), record (one live run that refreshes llm-replay).

Pipeline steps (each is one function with typed input and output and exactly one audit event)
1. ingest: RemitInbox lists new 835 files (dedupe by SHA-256 of content), downloads, parses, validates envelope and balancing, and classifies each CLP: paid → record as paid and stop; CLP02=4 with CARC 50 → case in lane medical-necessity; any other denial → lane other-denial and stop.
2. fetch_claim: ClaimArchive downloads /claim-archive/837/<hospitalClaimId>.837 and parses it.
3. resolve_identity: loads fixtures/claim-map.json and runs the identity gate from Constitution III. Any failure → needs-review and stop.
4. gather_evidence: EhrClient gets a token, reads Encounter, then searches Patient, Coverage, Condition, ServiceRequest, Procedure, DiagnosticReport, Observation, DocumentReference, MedicationRequest for the patient, applies the lookback window, fetches the Binary behind each DocumentReference, verifies Coverage.subscriberId, and records included and excluded counts.
5. payer_context: PayerAdapter gets the decision and the denial letter. PolicyStore selects the policy by payer ID, plan type (from Coverage), state (from the billing provider address), procedure code, and date of service. Cross-check deadline against decisionDate plus appealWindowDays.
6. build_matrix: for each requirement, candidates are fetched resources whose type is in evidenceTypes. The LLM proposes status, citations, and verbatim excerpts. The verifier enforces Constitution IV. Each unmet requirement → status missing plus one clinical-evidence-request task. Any missing → case needs-evidence and stop.
7. draft_packet: the LLM drafts the letter as a list of statements, each carrying requirement IDs and citation IDs. The verifier rejects uncited factual statements. Render an HTML preview and a PDF. Case → ready-for-review, packet v1.
8. approve_and_submit (human action): check role, packet version, and status; upload the letter, cited documents, and policy snapshot through PayerAdapter.upload_document; create the appeal with Idempotency-Key appeal-<caseId>-v<version>. Case → submitted with appealId.
9. track: poll PayerAdapter.get_appeal. Case → in-review when the payer says so.

LLM request design (efficiency is a requirement, document each choice in research.md)
- Exactly 2 LLM calls per happy-path case (build_matrix and draft_packet) and 1 in missing-evidence mode. Parsing, identity, policy selection, lookback filtering, verification, deadline math, and PDF rendering are deterministic code and never call the LLM.
- build_matrix is ONE call covering all requirements, not one call per requirement. Input is only the lookback-filtered candidate resources and decoded note text, trimmed to the fields that matter, never the whole chart.
- Structured Outputs on every call: client.responses.parse with a Pydantic model (strict JSON schema). No free-text parsing, no "please return JSON" prompts.
- Reasoning effort per step, from env: build_matrix "medium" (it judges things like "at least 6 weeks"), draft_packet "low" (it only phrases statements from already-verified rows). If the verifier rejects any citation, retry build_matrix once at "high", passing the verifier's rejection reasons. After that, the requirement is marked missing. Cheap by default; spend more only when verification fails.
- Prompt caching: put the static prefix first (developer instructions, output rules, then the policy text) and the case-specific evidence last, so repeated cases under the same policy reuse the cached prefix (automatic for 1,024+ token prefixes, 30-minute TTL on GPT-5.6). Set prompt_cache_key to the policyId. Don't use explicit cache breakpoints.
- store=false on every request; max_output_tokens capped per step; 45-second timeout; one retry with jittered backoff on 429 or 5xx only.
- Cases are independent, so the pipeline can run several at once behind an asyncio semaphore (default 4). Steps inside one case stay sequential.
- Log input, cached, output, and reasoning token counts per call into that step's audit event, and show "AI cost for this case" in the UI using prices from config. Cost per denial is a pitch number.
- Production note only (don't build): back-office runs over aged denial backlogs go through the Batch API, which gpt-5.6-luna supports.

Case statuses: new, claim-matched, needs-review, evidence-gathered, needs-evidence, ready-for-review, approved, submitted, in-review, plus paid and other-denial for claims we do not work. Put the allowed transitions table in data-model.md.

Presenter controls (app API plus UI): simulate remit, missing-evidence toggle, re-run case, reset demo, persona picker (billing-approver-01 with role authorized-billing-user; viewer-01 read-only).

contracts/ must contain:
- app-api.openapi.yaml: the app's own REST API used by the UI.
- mock-northstar-payer.openapi.yaml: exactly Appendix A6, including error responses.
- mock-hospital-fhir.md: supported resources, search parameters, auth flow, OperationOutcome errors, presenter toggle.
- x12-fixtures.md: which segments we read in each loop, and the validation rules.
- adapters.md: Python Protocol signatures for RemitInbox, ClaimArchive, EhrClient, PayerAdapter, PolicyStore, LlmClient.

Testing: tests are required and come before the code they cover. pytest for fixtures, X12 parsing and validation, identity gate (one failing test per identifier), verifier (forged resource ID, excerpt not in source, uncited statement), policy selection (wrong state, date, or plan returns no policy), payer contract (idempotent replay returns the same appeal; same key with a different body returns 409; appeal after deadline returns 422), 835 dedupe, the missing-evidence path end to end, LLM client behavior (Structured Outputs schema rejects malformed output, one high-effort retry after a verifier rejection, replay cache miss fails loudly), and a secrets guard (.env is git-ignored; no file under fixtures/ or docs/ matches an API key pattern). One Playwright smoke test clicks through the 6-step demo in replay mode.

quickstart.md: clean clone → make setup → make test → make demo → the 6-step click path with the exact expected screen text from Appendix A9 → missing-evidence toggle → make reset.

Constitution Check: fill it honestly. Two mock services and an SFTP container count as complexity; justify each in Complexity Tracking against a specific demo claim.
```

When the plan finishes, accept the optional `/speckit-agent-context-update` hook so `CLAUDE.md` points at the plan. Then read `research.md` yourself: check library versions, and check that nothing was added that the plan didn't ask for. Spec Kit's own docs warn that the agent can be "over-eager".

---

## 7. Checklists ("unit tests for the requirements")

These check that the **spec and plan are written well**. They don't test code. Run all three. The fourth is optional.

```text
/speckit-checklist identity-and-safety: requirements quality for the identity gate and zero chart access on mismatch, evidence-before-prose, citation and excerpt verification, missing-evidence behavior, human approval and role rules, packet versioning, idempotent submission, audit events, synthetic-data labelling, and honest UI wording. Depth: formal release gate. Audience: reviewer before implementation. Must-have items: each identity field has a defined mismatch behavior; "relevant evidence" and the lookback window are defined; excerpt verification rules are objectively testable; the status transition table forbids submission from any status except approved.
```

```text
/speckit-checklist data-contracts: requirements quality for X12 835 and 837P fidelity (envelopes, SE counts, balancing, claim-level versus service-level adjustments, REF after SVC, delimiter detection), FHIR R4 resource and searchset Bundle shapes, token handling, every Northstar payer endpoint including errors, idempotency semantics and document upload, policy selection keys and versioning, and consistency of every identifier across Appendix A (claim IDs, member ID, NPIs, codes, dates, amounts, record IDs). Depth: formal. Mark any spec or plan value that disagrees with docs/reclaim-speckit-prompts.md Appendix A as [Conflict].
```

```text
/speckit-checklist demo-readiness: requirements quality for the 6-step demo and the missing-evidence moment: exact on-screen text per step (Appendix A9), timing targets, reset behavior, live versus replay disclosure, fixed demo date, behavior if the AI call or a mock service fails mid-demo, visibility of the per-step explanations, and whether every judge-facing claim (scale through adapters, human approval, no unsupported statements, synthetic data) is backed by a stated requirement. Depth: standard. Audience: the presenter.
```

Optional, for the "technical feasibility at scale" rubric line:

```text
/speckit-checklist scale-story: requirements quality for what each mock is replaced by in production (clearinghouse SFTP or API, SMART Backend Services FHIR access at Epic or Oracle Health, one PayerAdapter per payer, policy ingestion from public libraries), dedupe and idempotency under re-delivery, multi-payer and multi-state policy selection, throughput assumptions per case, and where a human stays in the loop. Depth: standard. Audience: pitch reviewer.
```

### Resolve the checklists (plain prompt, then a human pass)

`/speckit-implement` halts while any checklist item is unchecked. In v1.0.6 the agent doesn't tick these boxes; your team does. First have the agent fix the documents:

```text
Open every file in the current feature's checklists/ folder. For each unchecked item:
- If spec.md or plan.md is missing or unclear on that point, fix it (keeping Appendix A values) and note where.
- If the item is intentionally out of scope, add it to the spec's Out of Scope or Assumptions section.
Do not tick any checkbox; checklist marks are for human reviewers. Finish with a table: checklist, item ID, what you changed (file and section), and "ready for human tick" or "needs a team decision" with the question.
```

Then split the checklists across teammates. Each person reads the fix for every item they own and ticks `[x]` only if they agree. This doubles as explain-it practice: every tick is a requirement someone on the team can defend. Commit when every box is ticked.

---

## 8. Tasks

```text
/speckit-tasks Tests are requested (TDD): write failing tests before the implementation they cover, for fixtures, X12 parsing and validation, identity gate, verifier, policy selection, payer contract, dedupe, and the missing-evidence path.

Ordering:
- Phase 1 Setup: repo skeleton, uv project with every dependency declared, docker compose, Makefile, .gitignore, .env.example.
- Phase 2 Foundational: fixtures first, exactly as docs/reclaim-speckit-prompts.md Appendix A (835, 837P, claim-map, FHIR resources and Binaries, payer JSON, policy, denial-letter PDF generator), each with a validation test. Then the X12 tokenizer, SQLite repository, audit event writer, adapter Protocols, and the two mock services plus SFTP container, each with contract tests.
- One phase per user story in spec priority order. Each phase ends with a runnable checkpoint I can show someone.
- MVP is the thinnest end-to-end happy path through demo steps 1 to 6 in replay mode. Needs-review UI, the missing-evidence toggle, and hardening come after the MVP works end to end.
- Final phase: Playwright smoke test of the demo; docs/explain/<step>.md for every pipeline step (one paragraph each: what it reads, what it decides, what production replaces); README quickstart; dead-code sweep.

Task rules: exact file paths in every task; no task touches more than 3 files; no task creates code that nothing calls; mark [P] only for truly independent files. Include one task to record fixtures/llm-replay from a live run, and one to verify a clean clone passes make test.
```

---

## 9. Analyze (read-only), then remediate

```text
/speckit-analyze Pay special attention to: conflicts with Constitution III, IV, V, VII, or VIII (report as CRITICAL); requirements with no task; tasks with no requirement (likely dead code); any identifier or value that differs from docs/reclaim-speckit-prompts.md Appendix A; tasks that add infrastructure the constitution forbids; tests that would be circular; demo steps from Appendix A9 with no task producing their on-screen text.
```

When it asks whether to suggest remediation:

```text
Yes. Suggest concrete edits for every CRITICAL and HIGH finding, and for MEDIUM findings that touch identity, evidence, or submission. Show me a short summary of each edit, then apply them to spec.md, plan.md, and tasks.md. Do not touch the constitution. When done, tell me to re-run /speckit-analyze.
```

Re-run `/speckit-analyze` until it reports zero CRITICAL and zero HIGH.

---

## 10. Implement (phase by phase, never all at once)

First pass:

```text
/speckit-implement Phase 1 and Phase 2 only. Stop at the end of Phase 2. Run make test and paste the real output. Do not start any user story phase.
```

Then repeat this for each user story phase:

```text
/speckit-implement The next incomplete phase only. Before coding, list the task IDs you will do. After finishing: run make test and paste the real output, run that phase's checkpoint from tasks.md, describe exactly what a presenter would see, and commit with a message naming the task IDs. If a task seems to need something the plan or constitution forbids, stop and ask instead of adding it.
```

Final pass:

```text
/speckit-implement The remaining phases. Then run quickstart.md from a clean state (make reset, then make demo) in replay mode and report each of the 6 demo steps plus the missing-evidence toggle as PASS or FAIL, with the on-screen text you observed compared against Appendix A9.
```

If implement stops on incomplete checklists, go back to "Resolve the checklists" in section 7. Don't answer "yes, proceed" just to get past the gate.

If a phase is big or the chat runs long, narrow the run by task range: `/speckit-implement only execute tasks T020-T030, then stop and report progress`. Implement resumes from the `[X]` marks, so starting a fresh chat mid-build is safe.

After Phase 1 finishes, do the API key step from section 1 (`cp .env.example .env`, add the key in an editor, `git check-ignore .env`). Build the MVP phases with `LLM_MODE=live`. As soon as the happy path runs end to end, run `make record` so replay fixtures exist before the polish phase and the Playwright test.

---

## 11. Converge (close the gap between spec and code)

```text
/speckit-converge Treat the constitution as binding. Look hardest at: identity gate coverage for every field, verifier coverage, idempotency, "SYNTHETIC DEMO DATA" on every screen and PDF, audit events for every step, values that drift from Appendix A, and unrequested code (flag it for removal).
```

Then:

```text
/speckit-implement The Convergence phase only. Run make test after, paste the output, and commit.
```

Repeat converge and implement until converge reports "Converged".

---

## 12. Optional commands and extras

**`/speckit-agent-context-update`** refreshes the SPECKIT block in `CLAUDE.md` so every new chat knows the active plan. Run it after re-planning, or accept it when it's offered as an optional hook.

```text
/speckit-agent-context-update
```

**`/speckit-taskstoissues`** turns tasks into GitHub issues so teammates can split work. It needs a GitHub remote and the GitHub MCP server connected. Issues are visible to anyone who can see the repo, so run it only on a private repo or with synthetic-only content (which this is).

```text
/speckit-taskstoissues Only tasks that are still unchecked. Add label "reclaim-demo".
```

**`git` extension** (installed by the init command in section 1). Its hooks run on their own; you rarely type these:

| Command | What it does |
|---|---|
| `/speckit-git-initialize` | Creates the repo (runs automatically before constitution) |
| `/speckit-git-feature` | Creates the feature branch (runs automatically before specify) |
| `/speckit-git-validate` | Checks the branch name follows the convention |
| `/speckit-git-remote` | Detects the remote URL |
| `/speckit-git-commit` | Commits; auto-commit per command can be turned on in `.specify/extensions/git/git-config.yml` |

**`bug` extension** is useful once the demo exists and something breaks. Add it with `specify extension add bug`. It keeps fixes scoped and tested instead of letting the agent wander through the codebase:

```text
/speckit-bug-assess "Missing-evidence toggle re-run still shows 3/3 satisfied" slug=toggle-stale
```

```text
/speckit-bug-fix slug=toggle-stale
```

```text
/speckit-bug-test slug=toggle-stale
```

Assess and test never edit code. Fix only touches files named in the assessment.

**Not recommended for this project:**
- `specify workflow run speckit -i spec="..."` runs specify → plan → tasks → implement with approval gates. It skips clarify, checklists, analyze, and converge, which are where this project gets bulletproofed.
- The `lean` preset swaps in minimal prompts. We want the full templates.
- The `assess` extension (`/speckit-assess-intake` through `/speckit-assess-decide`) vets whether an idea is worth building. You've already decided.

---

## 13. When something changes mid-build

| What changed | Do this |
|---|---|
| A principle (for example, allow a second database) | `/speckit-constitution <the amendment>` then `/speckit-analyze` |
| What the product does (small) | `/speckit-clarify <the change>` (it edits spec.md), then `/speckit-plan`, then commit, then `/speckit-tasks`, then `/speckit-analyze` |
| Tech choice only | `/speckit-plan <the change>`, commit, `/speckit-tasks`, `/speckit-analyze` |
| A demo value (ID, date, amount) | Edit Appendix A in `docs/reclaim-speckit-prompts.md` first, then `/speckit-converge` |
| Code drifted from the spec | `/speckit-converge`, then `/speckit-implement` for the Convergence phase |
| A bug in the working demo | `bug` extension: `/speckit-bug-assess`, `/speckit-bug-fix`, `/speckit-bug-test` (section 12) |
| Swap the AI model | Change `OPENAI_MODEL` in `.env`, run `make record`, then `make test`. Replay keys include the model, so stale recordings fail loudly instead of silently |
| A brand new feature later (for example, the corrected-claim lane) | New `/speckit-specify` creates `specs/002-...`; run the full flow for it |

Note: `/speckit-specify` always creates a **new** feature folder, so don't use it to edit the current spec. Also, `/speckit-tasks` regenerates tasks.md, so commit before re-running it so checked-off progress is recoverable.

---

## 14. After the build: explain-it drill (not spec-kit)

The rubric docks any team that can't explain a part of their project. Run this once per teammate:

```text
Quiz me on this codebase, one pipeline step at a time, using docs/explain/. For each step ask 3 questions a skeptical engineer judge would ask: why this design, what breaks at 10,000 denials a day, and what production replaces the mock with. Wait for my answer each time, then correct me using the actual code with file:line references. Append every question I missed, with the correct answer, to docs/explain/missed.md.
```

---

## Appendix A: Canonical demo data and contracts (source of truth)

Everything here is **synthetic**. It follows your original design, with the corrections in A1 so the data passes its own validation.

### A1. Corrections to the original design and why

| Original | Problem | Fix used below |
|---|---|---|
| 835 `CLP05` = 4800 (patient responsibility) | Group code CO means the provider absorbs it, so patient responsibility must be 0. Balancing also fails. | `CLP05` empty |
| 835 `CLP06` = MC (Medicaid) | Contradicts the "Commercial PPO" plan and policy | `CLP06` = 12 (PPO); 837 `SBR09` = 12 |
| `DTM*232*20260820` | DTM*232 is the claim statement start date. The identity gate would read Aug 20, compare it with the Aug 10 date of service, and send the hero case to needs-review. | `DTM*232` and `DTM*233` = 20260810. Aug 20 moves to `DTM*405` and `BPR16` (decision/payment date) |
| `SE*8` | SE01 counts ST through SE. The simplified file had 6. | Full envelopes, counts computed and tested |
| No payer identity in 835 or 837 | "Payer matches" has nothing to compare | `N1*PR` in 835 and `NM1*PR` in 837, payer ID NSTHLTH01 |
| NPI `1234567890` | Fails the NPI check digit; any real validator rejects it | Rendering NPI `1234567893`, billing NPI `1245319599` (both pass) |
| `DEMO-PROC-01`, `DEMO-DX-01` | Invalid code formats. Validators fail, and health-savvy judges notice. | CPT `72148` (lumbar spine MRI without contrast), ICD-10-CM `M54.16` (lumbar radiculopathy). To keep placeholders instead, replace them everywhere consistently. |
| Policy has no state | Your design selects by payer + plan + state + procedure + date of service | `states: ["WA"]` |
| MedicationRequest allowed as evidence but never fetched | R2 could never use it | Added to the FHIR search list (returns 0 results, shown honestly) |
| Appeal body references document IDs that were never sent | A judge will ask how attachments reach the payer | Added `POST /api/v1/documents` |
| "Tracking begins" with no tracking call | Nothing to poll | Added `GET /api/v1/appeals/{appealId}` |
| Deadline Oct 19 had no stated basis | Can't be cross-checked | `decisionDate` 2026-08-20 + 60-day appeal window = 2026-10-19 |
| Progress note could also describe prior therapy | The missing-evidence toggle wouldn't flip R2 | The progress note does not mention prior treatment, so R2 depends only on the PT note |
| Real "today" in the UI | After Oct 19 the demo payer would reject the appeal as late | Fixed `DEMO_TODAY=2026-09-12` |

The 835 also carries two extra claims so it reads like a real stream: one paid claim (ignored) and one CARC 16 denial (labelled other lane, never worked).

### A2. `fixtures/x12/era-2026-09-12.835`

Delivered to `sftp://mock-clearinghouse/outbound/835/era-2026-09-12.835` by "Simulate incoming remit". SE count (37) and balancing verified: for each claim, billed minus paid equals CAS total, and BPR02 (280) equals total paid. `ISA15 = T` marks it as test data.

```text
ISA*00*          *00*          *ZZ*NORTHSTARHLTH  *ZZ*MOCKHOSPITAL   *260820*1200*^*00501*000000905*0*T*:~
GS*HP*NORTHSTARHLTH*MOCKHOSPITAL*20260820*1200*905*X*005010X221A1~
ST*835*0001~
BPR*C*280*C*CHK************20260820~
TRN*1*NST-CHK-000905*1990000001~
DTM*405*20260820~
N1*PR*NORTHSTAR HEALTH~
N3*100 SYNTHETIC WAY~
N4*SEATTLE*WA*98101~
REF*2U*NSTHLTH01~
PER*BL*PROVIDER SERVICES*TE*5555550100~
N1*PE*MOCK HOSPITAL*XX*1245319599~
LX*1~
CLP*HSP-CLM-100028*4*4800*0**12*PAYER-CLM-99281*11*1~
NM1*QC*1*RIVERA*JORDAN****MI*MEMBER-448820~
NM1*82*1*LEE*SAM****XX*1234567893~
DTM*232*20260810~
DTM*233*20260810~
SVC*HC:72148*4800*0**1~
DTM*472*20260810~
CAS*CO*50*4800~
REF*6R*HSP-CLM-100028-1~
CLP*HSP-CLM-100031*1*350*280**12*PAYER-CLM-99305*11*1~
NM1*QC*1*PATEL*AVERY****MI*MEMBER-448901~
DTM*232*20260812~
DTM*233*20260812~
SVC*HC:99213*350*280**1~
DTM*472*20260812~
CAS*CO*45*70~
REF*6R*HSP-CLM-100031-1~
CLP*HSP-CLM-100035*4*620*0**12*PAYER-CLM-99310*11*1~
NM1*QC*1*NGUYEN*CASEY****MI*MEMBER-449012~
DTM*232*20260813~
DTM*233*20260813~
SVC*HC:73030*620*0**1~
DTM*472*20260813~
CAS*CO*16*620~
REF*6R*HSP-CLM-100035-1~
SE*37*0001~
GE*1*905~
IEA*1*000000905~
```

Normalized case produced from the hero claim:

```json
{
  "caseId": "case-100028",
  "lane": "medical-necessity",
  "hospitalClaimId": "HSP-CLM-100028",
  "payerClaimId": "PAYER-CLM-99281",
  "payer": "Northstar Health",
  "payerId": "NSTHLTH01",
  "memberId": "MEMBER-448820",
  "renderingNpi": "1234567893",
  "procedureCode": "72148",
  "dateOfService": "2026-08-10",
  "denialCode": "CO-50",
  "denialReason": "Medical necessity",
  "billedAmount": 4800,
  "deniedAmount": 4800,
  "remitFile": "era-2026-09-12.835",
  "remitSha256": "<computed>",
  "status": "new"
}
```

Normalization rule: the denial code is `<CAS group>-<CARC>`, read from the service-level CAS when present, otherwise from the claim-level CAS.

### A3. `fixtures/x12/HSP-CLM-100028.837`

Pre-seeded at `sftp://mock-clearinghouse/claim-archive/837/HSP-CLM-100028.837`. It's an 837P with an SE count of 25.

```text
ISA*00*          *00*          *ZZ*MOCKHOSPITAL   *ZZ*MOCKCLEARINGHS *260811*0900*^*00501*000000712*0*T*:~
GS*HC*MOCKHOSPITAL*MOCKCLEARINGHS*20260811*0900*712*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*HSP-BATCH-0712*20260811*0900*CH~
NM1*41*2*MOCK HOSPITAL*****46*MOCKHOSP01~
PER*IC*BILLING OFFICE*TE*5555550199~
NM1*40*2*MOCK CLEARINGHOUSE*****46*MOCKCH01~
HL*1**20*1~
NM1*85*2*MOCK HOSPITAL*****XX*1245319599~
N3*1 SYNTHETIC PLAZA~
N4*SEATTLE*WA*98104~
REF*EI*990000001~
HL*2*1*22*0~
SBR*P*18*NST-PPO-GRP-01******12~
NM1*IL*1*RIVERA*JORDAN****MI*MEMBER-448820~
N3*200 EXAMPLE AVE~
N4*SEATTLE*WA*98105~
DMG*D8*19800214*U~
NM1*PR*2*NORTHSTAR HEALTH*****PI*NSTHLTH01~
CLM*HSP-CLM-100028*4800***11:B:1*Y*A*Y*I~
HI*ABK:M5416~
NM1*82*1*LEE*SAM****XX*1234567893~
LX*1~
SV1*HC:72148*4800*UN*1***1~
DTP*472*D8*20260810~
REF*6R*HSP-CLM-100028-1~
SE*25*0001~
GE*1*712~
IEA*1*000000712~
```

Extracted: claim ID, member ID, payer ID NSTHLTH01, billing NPI and state WA (from N4), rendering NPI, CPT 72148, ICD-10-CM M54.16, date of service 2026-08-10, 1 unit, $4,800.

**Identity gate for the hero case (all must pass):**

| Check | 835 value | 837 / chart value |
|---|---|---|
| Claim ID | CLP01 `HSP-CLM-100028` | CLM01 `HSP-CLM-100028` |
| Member ID | NM1*QC `MEMBER-448820` | NM1*IL `MEMBER-448820`, later Coverage.subscriberId |
| Date of service | DTM*472 / DTM*232 `20260810` | DTP*472 `20260810`, Encounter.period.start date |
| Payer | REF*2U `NSTHLTH01` | NM1*PR `NSTHLTH01` |
| Rendering provider | NM1*82 `1234567893` | NM1*82 `1234567893` |
| Procedure | SVC01 `HC:72148` | SV101 `HC:72148` |

Test fixtures for needs-review (tests only, not the main demo): copies of the 837 with exactly one field changed per test.

### A4. `fixtures/claim-map.json`

```json
{
  "HSP-CLM-100028": {
    "patientId": "patient-0042",
    "mrn": "MRN-0042",
    "encounterId": "encounter-20260810-42",
    "dateOfService": "2026-08-10",
    "procedureCode": "72148",
    "diagnosisCode": "M54.16"
  }
}
```

### A5. FHIR R4 fixtures (`https://mock-hospital.example/fhir/R4`)

Auth: `POST /auth/token` (client_credentials) returns a Bearer token with scopes such as `system/Encounter.rs system/Patient.rs system/Coverage.rs system/Condition.rs system/ServiceRequest.rs system/Procedure.rs system/DiagnosticReport.rs system/Observation.rs system/DocumentReference.rs system/MedicationRequest.rs system/Binary.r`. Every request carries `Authorization: Bearer <token>` and `Accept: application/fhir+json`. Production replaces this with SMART Backend Services (signed JWT client assertion) at the hospital's FHIR endpoint.

Calls, in order:

```text
GET /fhir/R4/Encounter/encounter-20260810-42
GET /fhir/R4/Patient/patient-0042
GET /fhir/R4/Coverage?patient=patient-0042
GET /fhir/R4/Condition?patient=patient-0042
GET /fhir/R4/ServiceRequest?patient=patient-0042
GET /fhir/R4/Procedure?patient=patient-0042
GET /fhir/R4/DiagnosticReport?patient=patient-0042
GET /fhir/R4/Observation?patient=patient-0042
GET /fhir/R4/DocumentReference?patient=patient-0042
GET /fhir/R4/MedicationRequest?patient=patient-0042
GET /fhir/R4/Binary/<id>   (for each DocumentReference inside the lookback window)
```

Lookback: 2026-02-10 to 2026-08-10 (6 months before the date of service, plus the encounter).

| Resource | id | Key content (all synthetic) | Date | Role |
|---|---|---|---|---|
| Patient | patient-0042 | Jordan Rivera, birthDate 1980-02-14, identifier MR `MRN-0042` | | identity display |
| Coverage | coverage-0042 | status active; beneficiary Patient/patient-0042; payor "Northstar Health" (identifier NSTHLTH01); subscriberId `MEMBER-448820`; class plan "Commercial PPO"; class group NST-PPO-GRP-01; period start 2026-01-01 | | member check, plan type for policy |
| Practitioner | practitioner-lee | Sam Lee, NPI `1234567893` | | provider check |
| Organization | mock-hospital | Mock Hospital, NPI `1245319599`, Seattle WA | | state for policy |
| Encounter | encounter-20260810-42 | finished; class AMB; subject patient-0042; participant practitioner-lee; period 2026-08-10T09:00:00Z to 09:45:00Z; serviceProvider mock-hospital | 2026-08-10 | date of service check |
| Condition | condition-100 | ICD-10-CM M54.16, clinicalStatus active, onset 2026-05-20, recorded 2026-05-28 | 2026-05-28 | R1 |
| DiagnosticReport | report-xr-555 | Lumbar spine X-ray, conclusion: degenerative changes, no fracture | 2026-05-28 | supporting |
| Observation | obs-pain-7781 | LOINC 72514-3 pain severity, value 8 | 2026-08-10 | supporting |
| ServiceRequest | order-901 | intent order; status completed; CPT 72148; reasonReference Condition/condition-100; note with the clinician's rationale; authoredOn 2026-08-10 | 2026-08-10 | R3 |
| Procedure | procedure-902 | completed; CPT 72148; basedOn ServiceRequest/order-901; performed 2026-08-10 | 2026-08-10 | procedure check |
| DocumentReference + Binary | note-progress-031 | Progress note: radiating leg pain, positive straight-leg raise, focal weakness, reason MRI is needed now. **Does not mention prior treatment.** | 2026-08-10 | R1, R3 |
| DocumentReference + Binary | treatment-note-022 | PT discharge summary: 6 weeks of physical therapy from 2026-06-02 to 2026-07-14 plus home exercise program, symptoms not improved. **Hidden in missing-evidence mode.** | 2026-07-14 | R2 |
| DocumentReference + Binary | note-ortho-2019-004 | Unrelated 2019 ankle sprain visit | 2019-03-02 | excluded by lookback (shown as "1 record excluded") |
| MedicationRequest | (none) | Search returns an empty Bundle | | shows honest zero |

Binary resources: `contentType` text/plain, `data` base64. Excerpts in the evidence matrix must be exact substrings of the decoded text.

### A6. Mock payer contract: Northstar Health (`https://mock-northstar-health.example/api/v1`)

Clearly labelled mock. No universal payer API exists; production uses one PayerAdapter per payer (API, clearinghouse, or authorized portal connection). All calls need `Authorization: Bearer <mock-payer-token>`. Errors look like `{"error": {"code": "<snake_case>", "message": "<text>"}}`.

**GET `/claims/{payerClaimId}/decision`** returns 200:

```json
{
  "payerClaimId": "PAYER-CLM-99281",
  "claimId": "HSP-CLM-100028",
  "decision": "denied",
  "decisionDate": "2026-08-20",
  "reasonCode": "CO-50",
  "reasonText": "Insufficient documentation of medical necessity",
  "appealDeadline": "2026-10-19",
  "allowedSubmissionChannels": ["portal", "fax"],
  "letter": {
    "documentId": "denial-letter-99281",
    "url": "/api/v1/documents/denial-letter-99281"
  }
}
```

Errors: 401 `unauthorized`; 404 `claim_not_found`.

**GET `/documents/{documentId}`** returns 200 `application/pdf` (the synthetic denial letter, which also states the Oct 19 deadline). 404 `document_not_found`.

**POST `/documents`** (addition) is multipart with fields `documentId`, `documentType` (appeal-letter | clinical-note | order | policy-snapshot), `relatedPayerClaimId`, and `file`. It returns 201 `{"documentId": "..."}`. Re-uploading the same ID with the same bytes returns 200. The same ID with different bytes returns 409 `document_conflict`.

**POST `/appeals`** has headers `Content-Type: application/json` and `Idempotency-Key: appeal-case-100028-v1`:

```json
{
  "payerClaimId": "PAYER-CLM-99281",
  "hospitalClaimId": "HSP-CLM-100028",
  "appealType": "reconsideration",
  "reasonCode": "CO-50",
  "letterDocumentId": "appeal-letter-100028",
  "attachments": [
    "note-progress-031",
    "treatment-note-022",
    "order-901",
    "policy-snapshot-NST-IMG-2026-04"
  ],
  "submittedBy": {
    "userId": "billing-approver-01",
    "role": "authorized-billing-user"
  }
}
```

It returns 201:

```json
{
  "appealId": "NST-APL-80126",
  "status": "received",
  "receivedAt": "2026-09-12T18:32:00Z",
  "expectedResolutionDays": 14
}
```

Idempotency: the same key with the same body returns 200 with the identical response and header `Idempotent-Replayed: true`. The same key with a different body returns 409 `idempotency_key_reused`. Other errors: 422 `unknown_attachment` (document not uploaded), 422 `appeal_window_closed` (after `appealDeadline`, judged against `DEMO_TODAY`), 404 `claim_not_found`.

**GET `/appeals/{appealId}`** (addition) returns 200 `{"appealId": "NST-APL-80126", "status": "received" | "in-review", "updatedAt": "..."}`. The demo moves from received to in-review 30 seconds after submission.

Stored fixtures: `fixtures/payer/payer-decision.json`, `fixtures/payer/denial-letter.pdf` (generated), `fixtures/payer/appeal-response.json`.

### A7. `fixtures/policies/NST-IMG-2026-04.json`

```json
{
  "policyId": "NST-IMG-2026-04",
  "version": "2026.04",
  "title": "Advanced imaging of the lumbar spine (SYNTHETIC)",
  "payer": "Northstar Health",
  "payerId": "NSTHLTH01",
  "planType": "Commercial PPO",
  "states": ["WA"],
  "procedureCodes": ["72148"],
  "effectiveStart": "2026-01-01",
  "effectiveEnd": null,
  "appealWindowDays": 60,
  "lookbackMonths": 6,
  "requirements": [
    {
      "id": "R1",
      "text": "Documented diagnosis that supports lumbar imaging, such as lumbar radiculopathy",
      "evidenceTypes": ["Condition", "DocumentReference"]
    },
    {
      "id": "R2",
      "text": "Documented trial of conservative treatment lasting at least 6 weeks within the 6 months before the date of service",
      "evidenceTypes": ["DocumentReference", "MedicationRequest"]
    },
    {
      "id": "R3",
      "text": "Clinical rationale for the imaging order from the treating clinician",
      "evidenceTypes": ["ServiceRequest", "DocumentReference"]
    }
  ],
  "sourceUrl": "https://example.org/mock-policy/NST-IMG-2026-04",
  "sourceRetrievedAt": "2026-09-12"
}
```

Selection returns no policy when payer, plan type, state, procedure, or date of service doesn't match. A general policy never proves a specific member is covered; Coverage does that.

### A8. Evidence matrix, task, and packet

Evidence matrix (happy path):

```json
{
  "caseId": "case-100028",
  "policyId": "NST-IMG-2026-04",
  "policyVersion": "2026.04",
  "summary": {"satisfied": 3, "total": 3},
  "requirements": [
    {
      "requirementId": "R1",
      "status": "satisfied",
      "evidence": [
        {"resource": "Condition/condition-100", "date": "2026-05-28", "excerpt": "<exact text from resource>", "verified": true},
        {"resource": "DocumentReference/note-progress-031", "document": "Binary/note-progress-031", "date": "2026-08-10", "excerpt": "<exact substring of note>", "verified": true}
      ]
    },
    {
      "requirementId": "R2",
      "status": "satisfied",
      "evidence": [
        {"resource": "DocumentReference/treatment-note-022", "document": "Binary/treatment-note-022", "date": "2026-07-14", "excerpt": "<exact substring of PT note>", "verified": true}
      ]
    },
    {
      "requirementId": "R3",
      "status": "satisfied",
      "evidence": [
        {"resource": "ServiceRequest/order-901", "date": "2026-08-10", "excerpt": "<exact text of order note>", "verified": true}
      ]
    }
  ]
}
```

Missing-evidence mode: R2 becomes `{"status": "missing", "reason": "No DocumentReference or MedicationRequest in the lookback window documents a 6-week conservative treatment trial", "evidence": []}`, summary 2/3, case status `needs-evidence`, and exactly one task:

```json
{
  "taskId": "task-case-100028-R2",
  "taskType": "clinical-evidence-request",
  "caseId": "case-100028",
  "requirementId": "R2",
  "assigneeRole": "treating-clinician",
  "question": "The policy requires documentation of prior conservative treatment. Please identify the relevant note or provide a factual attestation.",
  "status": "open"
}
```

Appeal packet contents: hospital and payer claim IDs; patient and member identifiers; procedure, diagnosis, provider, service date, amount; stated denial reason; payer policy ID and version; requirement-by-requirement citations; requested action ("reconsider and reprocess payment"); attachment list; required human approver; packet version; "SYNTHETIC DEMO DATA" footer.

### A9. Demo script and exact on-screen text

| # | Presenter says | Presenter clicks | Screen must show |
|---|---|---|---|
| 1 | "A denial just arrived." | Simulate incoming remit | New case: "Northstar Health · CO-50 Medical necessity · $4,800". Also "1 paid claim, no action" and "1 other denial lane: not handled in this demo". |
| 2 | "We resolve it to the exact claim and visit." | Open the case | HSP-CLM-100028 → 837 claim → encounter-20260810-42, with 6 identity checks marked passed |
| 3 | "We gather only relevant evidence." | Evidence tab | Coverage, Condition, Order, Procedure, X-ray report, pain score, 2 notes, each with source and date; "1 record excluded (outside 6-month lookback)"; "MedicationRequest: 0 found" |
| 4 | "We test it against the payer's own requirements." | Matrix tab | Policy NST-IMG-2026-04 v2026.04; R1, R2, R3 turn green one by one |
| 5 | "We generate a cited appeal." | Packet tab | "Ready for review", "Evidence completeness: 3/3 policy criteria satisfied", "Appeal deadline: October 19, 2026 (37 days left)", "Expected recovery: $4,800". Clicking a sentence highlights requirement and excerpt. |
| 6 | "A human approves, the system submits, and tracking begins." | Approve and submit (as billing-approver-01) | "Submitted · Northstar confirmation NST-APL-80126 · expected resolution 14 days", then "In review" |
| 7 (optional, 15s) | "Watch what happens when a note is missing." | Reset demo, Missing-evidence toggle on, Simulate incoming remit, open the case | "Needs 1 item", R2 red, no letter, Approve disabled, one clinician request shown |

Always visible: "SYNTHETIC DEMO DATA", "Demo date: 2026-09-12", "AI: live" or "AI: replay".

---

## Appendix B: Mistakes from the last repo (do not repeat)

From the audit of `Healtcare-RCM-Denial-Recovery-Agent`:

1. **Over-built infrastructure.** MongoDB, PostgreSQL, Redis, Celery, LangGraph, and Kubernetes for a demo. Nobody could explain it all, and the pipeline still dead-ended (48 of 50 denials went to the manual queue). This time: one SQLite file, one plain pipeline function.
2. **Undeclared or broken dependencies.** `email-validator` and `fakeredis` were used but not declared; `passlib` broke against newer `bcrypt`. This time: uv lockfile, no password hashing at all (persona picker), and a clean-clone test task.
3. **835 parser broke on REF segments after SVC.** This time the fixture includes `REF*6R` after `SVC` on every claim, with a test.
4. **837 archive not seeded,** so claims had nothing to match against. This time the archive is pre-seeded and a test proves the hero claim resolves.
5. **Circular accuracy tests** that compared output with snapshots generated by the same code. This time expected values come from Appendix A or are written by hand.
6. **Dead code** (unused LangGraph nodes, Vault client). This time a dead-code sweep task, and converge flags unrequested code.
7. **Scope sprawl** (appeals plus corrected claims plus six agents at once). This time: one lane (CARC 50) end to end. Everything else is labelled, not worked.
8. **Leaked secrets** (from another of our public repos, which committed a `.env`). This time: `.env` is ignored from Phase 1, a test guards it, and keys never go into chat prompts or docs.
