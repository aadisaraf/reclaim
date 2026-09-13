# Dead-code sweep (T129)

## Scope

Swept every top-level `def`/`async def`/`class` and every one-level-indented class method
across `src/reclaim/` (216 top-level symbols, 101 methods), `mocks/hospital/app.py` +
`mocks/northstar/app.py`, and `scripts/make_denial_letter.py` + `scripts/record_replay.py` —
317 symbols total. `web/` (the Next.js frontend named in T129's task text) was **excluded**:
it does not exist in this checkout — it is an empty directory tracked only on the separate
`Pranav` branch, which owns the frontend — so there is nothing under it to sweep here.

**Method**: for every symbol, `rg -n '\b<name>\b'` across `src/`, `mocks/`, `scripts/`,
`tests/`, and `fixtures/`, excluding the symbol's own definition line. A hit elsewhere in
`src/mocks/scripts` counts as demo-path use; a hit only under `tests/` is flagged separately;
zero hits anywhere is a genuine dead-code candidate. This automated pass has two known blind
spots that were corrected by hand below:

- **FastAPI routes/middleware/exception-handlers are framework-invoked, not called by name.**
  A first pass flagged 18 route handlers (11 in `api.py`, 6 in `mocks/hospital/app.py`, 1 in
  `main.py`) as "zero references" purely because nothing in the codebase spells out their
  function name a second time. All 18 are immediately preceded by `@router.get/post/put`,
  `@app.get/post/put`, `@app.middleware`, or `@app.exception_handler` and are genuinely wired —
  they are not findings and are omitted below.
- **Same-named classes in different files collide in a text search.** `PayerDecision`,
  `LlmUsage`, and `PolicySelection` are each defined twice (once in `models.py`, once in
  `adapters/protocols.py`); a naive `rg` for the name finds "uses" that are actually of the
  *other* same-named class. These required reading the imports at each use site to attribute
  correctly — see findings 1-3 below.

`uv run ruff check .` is not configured via `[tool.ruff]` in `pyproject.toml` (no such
section exists), so it runs on ruff's own defaults. Scoped to the swept directories
(`uv run ruff check src/reclaim mocks scripts`) it reports 29 issues, 26 of them import-sorting
(I001), datetime/typing modernization (UP017/UP035), and style nits (B008/B013/C408/RUF023/DTZ007)
that are not dead-code findings and are not repeated here. The remaining 3 (2×F401 unused
import, 1×F841 unused local) are genuine dead-code signals and are listed below rather than
re-derived by hand.

## Findings

### A. Orphaned duplicate Pydantic models in `models.py`

All four are defined in `models.py` but never imported from there; every real use in the
codebase imports the same-named (and, for the first three, field-for-field identical) class
from `reclaim.adapters.protocols` instead, or (for `Persona`) uses a plain `dict` instead of
any model.

1. **`PayerDecision`** — `src/reclaim/models.py:109`. Unused; `adapters/protocols.py:53`
   defines the class actually imported by `steps/payer_context.py`, `steps/draft_packet.py`,
   and the tests. Safe to delete.
2. **`LlmUsage`** — `src/reclaim/models.py:215`. Unused; `adapters/protocols.py:129` defines
   the class actually imported by `api.py` and `adapters/llm.py`. (The `models.py` copy also
   carries an extra `usd: float = 0.0` field the `protocols.py` one lacks — worth checking
   before deleting that nothing depended on that field specifically, but no such caller exists.)
   Safe to delete.
3. **`PolicySelection`** — `src/reclaim/models.py:139`. Unused; `adapters/protocols.py:116`
   defines the class actually imported and constructed by `adapters/policy.py`. Safe to delete.
4. **`Persona`** — `src/reclaim/models.py:210`. Never imported or constructed anywhere;
   `api.py`'s `PERSONAS` list and the `/api/personas` route use plain dicts
   (`{"userId": ..., "role": ..., "canApprove": ...}`), not this model. The only other textual
   hit is the word "Persona" inside a docstring in `steps/approve_and_submit.py:46`, which
   doesn't count as use. Safe to delete, unless persona validation via this model is planned
   for a not-yet-implemented task — needs a human decision.

### B. Step-file helpers superseded by inline logic in `api.py` (used only in tests)

5. **`status_line(blocked)`** — `src/reclaim/steps/draft_packet.py:77`. Only caller anywhere
   is `tests/unit/test_packet_render.py:174`. Not called from `draft_packet()` in the same
   file, nor from `api.py` (which computes its own, differently-scoped `STATUS_LINES` dict
   for the 11 case statuses instead). The comment directly above it
   (`draft_packet.py:73-76`) already documents this as intentional: "kept here so both a
   future api.py and these tests share one implementation... api.py's case-detail assembly
   may already compute completenessLine and recoveryLine independently." Keep — this is a
   documented, deliberate duplication the original author flagged, not an oversight; a human
   should decide whether to finally wire `api.py` to call it or delete it now that "a future
   api.py" is the current one.
6. **`completeness_line(matrix)`** — `src/reclaim/steps/draft_packet.py:81`. Same situation as
   #5: only caller is `tests/unit/test_packet_render.py:175`; `api.py:235-238` independently
   recomputes the identical "Evidence completeness: N/M policy criteria satisfied" line inline
   in `get_case_detail`. Same comment covers this by name. Human decision (see #5).
7. **`recovery_line(case)`** — `src/reclaim/steps/draft_packet.py:85`. Same situation: only
   caller is `tests/unit/test_packet_render.py:176`; `api.py:240` independently recomputes
   "Expected recovery: $N" inline. Same comment covers this by name. Human decision (see #5).
8. **`deadline_line(deadline)`** — `src/reclaim/steps/payer_context.py:28`. Only caller is
   `tests/unit/test_deadline.py:31`. `api.py:228` gets the same string by calling the
   `Deadline.line` property (`models.py:150-152`) directly instead of this function. This
   function was originally spec'd by the task list itself (T081: "Create
   `src/reclaim/steps/payer_context.py` with `compute_deadline` and `deadline_line`"), so it's
   a documented part of the step's interface, not accidental — but a later phase's `api.py`
   was written against the `Deadline.line` property instead of this function. Keep — used by
   tests exercising the documented interface; flagging for awareness rather than deletion.

### C. Dead `Repo` methods

9. **`Repo.get_case_by_hospital_claim_id`** — `src/reclaim/repo.py:168`. Zero references
   anywhere outside its own definition (not in `src/`, `mocks/`, `scripts/`, or `tests/`).
   `steps/ingest.py` looks up existing cases via a deterministically-derived `case_id`
   (`_case_id()` at `ingest.py:20`, called at `ingest.py:63`) and `repo.get_case(case_id)`
   instead — this method appears to have been superseded by that derivation scheme and never
   removed. Safe to delete.
10. **`Repo.mark_document_uploaded`** — `src/reclaim/repo.py:304`. Zero references anywhere.
    The `documents` table has an `uploaded_at` column (`repo.py:104`) that `save_document`
    can set optionally, and this method exists to update it after the fact, but
    `steps/approve_and_submit.py` (the only place that actually uploads documents to the
    payer, at line ~139-145) never calls it once the upload succeeds. This looks like
    unfinished wiring rather than genuinely obsolete code — needs a human decision: either
    wire the call into `approve_and_submit.py` after a successful
    `ctx.payer_adapter.upload_document(...)`, or delete the method and the column's write
    path along with it.

### D. Dead dunder method

11. **`RuleFailure.__eq__`** — `src/reclaim/x12/validate.py:14`. `RuleFailure` is never
    imported by name outside `validate.py`, and neither `tests/unit/test_validate_835.py` nor
    `tests/unit/test_validate_837.py` compares `RuleFailure` instances with `==` — both read
    `.rule` off the returned objects instead
    (`[f.rule for f in validate_835(segments, remit)]`). No `==` comparison of a `RuleFailure`
    exists anywhere in the repo, so this method is never invoked. Safe to delete (or keep as
    a harmless, cheap convenience for future test-writing — low priority either way).

### E. Unused imports / unused local (ruff-flagged, `F401`/`F841`)

12. **`EhrNotFound` import** — `src/reclaim/steps/gather_evidence.py:6`. Imported from
    `reclaim.adapters.protocols` but never referenced in the file (no `except EhrNotFound`
    or similar). Safe to delete (`ruff check --fix` removes it).
13. **`Segment` import** — `src/reclaim/x12/remit835.py:2`. Imported from
    `reclaim.x12.tokenizer` but never referenced (the file uses `X12ParseError` and
    `tokenize` from the same import, not `Segment`). Safe to delete.
14. **Unused local `exc`** — `src/reclaim/adapters/llm.py:84`, in
    `except (RateLimitError,) as exc:` — `exc` is bound but never read in the retry branch.
    Safe to delete (rewrite as `except (RateLimitError,):` — ruff's suggested fix also folds
    in the `B013` single-exception-tuple simplification at the same line).

### F. Test-only mock endpoints/helpers (intentional, not dead)

15. **`reset_now_fn()`** — `mocks/northstar/app.py:87`. Never called from `mocks/northstar/app.py`
    itself or from any production adapter; its 5 callers are all in
    `tests/integration/test_track.py`, `tests/contract/test_payer_adapter.py`, and
    `tests/contract/test_mock_payer.py`. This pairs with `set_now_fn` (used the same way) as
    the module's documented clock-injection seam for tests ("the clock... is deliberately
    injectable so contract tests never need to sleep," per the module docstring). Keep —
    genuine test-only helper, working as designed.
16. **`get_control_state` route** (`GET /_control/state`) — `mocks/hospital/app.py:250`.
    Reachable in production only via `HttpEhrClient.control(method, path)`
    (`adapters/fhir.py:57`), but `demo.py`'s `set_missing_evidence`/`reset_demo` only ever
    call `.control("PUT", "missing-evidence")` and `.control("POST", "reset")` — never
    `.control("GET", "state")`. That call only appears in
    `tests/integration/test_reset.py` (lines 197, 240, 247) and
    `tests/contract/test_mock_hospital.py`. Keep — used by tests to assert reset/toggle
    behavior; not part of the live demo run path.
17. **`smart_configuration` route** (`GET /fhir/R4/.well-known/smart-configuration`) —
    `mocks/hospital/app.py:133`. `HttpEhrClient` never calls this discovery endpoint (its
    `token_url` is built directly from config in `main.py:56`, not discovered). Only caller
    is `tests/contract/test_mock_hospital.py:58`. Keep — this route exists for FHIR/SMART
    contract completeness and is exercised by the contract test suite, not by the demo's own
    runtime path.

## Summary

317 symbols swept (216 top-level functions/classes + 101 methods) across `src/reclaim/`,
`mocks/`, and `scripts/`. 17 findings recorded above: 9 look like genuinely safe deletions
(findings 1, 3, 9, 12, 13, 14, and — with a caveat each — 2, 4, 11), 3 need an explicit human
call rather than a mechanical delete (findings 5-7 as one bundle, and 10), and the remaining 4
+ 1 (8, 15-17) are intentional test-only code that should stay. No other function, class,
route, or component in the swept tree came back with zero references once framework-wired
routes and same-named-class collisions were corrected for by hand.
