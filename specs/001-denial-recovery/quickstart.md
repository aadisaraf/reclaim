# Quickstart: Reclaim demo validation

This runs on one laptop. All data is synthetic.

Details live in other files:
- Contracts: [contracts/](contracts/)
- States and rules: [data-model.md](data-model.md)
- Design choices: [research.md](research.md)

## Prerequisites

- Docker Desktop with compose v2. On Apple Silicon, amd64 emulation must be on for `atmoz/sftp`.
- uv 0.12+ (installs Python 3.12 itself).
- Node 20.9+ and npm.
- make.
- For `make record` only: an OpenAI API key, put **only** in your local `.env` as
  `OPENAI_API_KEY=`. Never paste it into chat, docs, or code.

## 1. Clean clone to green

```bash
git clone <repo-url> reclaim && cd reclaim
```

```bash
make setup
```

`make setup` does four things:
- `uv sync --locked` and `npm ci` in `web/`.
- Creates `.env` from `.env.example` if it is missing, with random mock tokens and
  `LLM_MODE=replay`.
- Generates the SFTP ed25519 host key and known_hosts in `.local/`.
- Installs the Playwright browser.

```bash
make test
```

What `make test` covers:
- **pytest**: fixture validation (X12 X-01 to X-13, FHIR R4B), X12 parsing, the identity gate (one
  failing test per field plus the post-read checks), the verifier (forged resource, excerpt not in
  source, uncited statement), policy selection misses, payer contract (idempotent replay, 409,
  422), 835 dedupe, the missing-evidence path end to end, LLM client (malformed output rejected,
  one high-effort retry, replay miss fails loudly), and the secrets guard.
- **Playwright smoke**: the six steps below, run in replay mode against the compose stack.

Expected result: everything passes. If `fixtures/llm-replay/` is empty (not yet recorded), the
Playwright smoke fails loudly with `ReplayMissError`; run step 5 first.

## 2. Run the demo

```bash
make demo
```

This starts `app` (:8000), `web` (:3000), `mock-clearinghouse`, `mock-hospital`, and
`mock-northstar-health`, then seeds the 837 archive.

Open http://localhost:3000.

Every screen shows **"SYNTHETIC DEMO DATA"**, **"Demo date: 2026-09-12"**, and **"AI: replay"** (or
**"AI: live"**). The presenter bar shows the configured base URLs. Pick persona
**billing-approver-01**.

| # | Click | Screen must show (Appendix A9, exact) |
|---|---|---|
| 1 | **Simulate incoming remit** | New case: "Northstar Health · CO-50 Medical necessity · $4,800". Also "1 paid claim, no action" and "1 other denial lane: not handled in this demo". |
| 2 | Open the case | HSP-CLM-100028 → 837 claim → encounter-20260810-42, with 6 identity checks marked passed |
| 3 | **Evidence** tab | Coverage, Condition, Order, Procedure, X-ray report, pain score, 2 notes, each with source and date; "1 record excluded (outside 6-month lookback)"; "MedicationRequest: 0 found" |
| 4 | **Matrix** tab | Policy NST-IMG-2026-04 v2026.04; R1, R2, R3 turn green one by one |
| 5 | **Packet** tab | "Ready for review", "Evidence completeness: 3/3 policy criteria satisfied", "Appeal deadline: October 19, 2026 (37 days left)", "Expected recovery: $4,800". Clicking a sentence highlights requirement and excerpt. |
| 6 | **Approve and submit** (as billing-approver-01) | "Submitted · Northstar confirmation NST-APL-80126 · expected resolution 14 days", then "In review" (about 30 s later) |

Extra checks:
- Switch the persona to **viewer-01** before step 6. **Approve and submit** is refused and the
  timeline records the refusal.
- Press **Approve and submit** twice. The same `NST-APL-80126` is shown, and the payer holds one
  appeal (`Idempotency-Key: appeal-case-100028-v1`).
- The timeline shows one plain-English entry per step. The `build_matrix` and `draft_packet`
  entries show token counts, and the case shows "AI cost for this case (estimate)".

## 3. Missing-evidence mode (A9 step 7)

| Click | Screen must show |
|---|---|
| **Reset demo**, **Missing-evidence toggle** on, **Simulate incoming remit**, open the case | "Needs 1 item", R2 red, no letter, Approve disabled, one clinician request shown |

Also check:
- The R2 reason reads "No DocumentReference or MedicationRequest in the lookback window documents a
  6-week conservative treatment trial".
- The task is `task-case-100028-R2` with the A8 question and status "open".
- The timeline shows exactly one LLM call.

Then turn the toggle **off** and press **Re-run**:
- The case returns to "Ready for review" with 3/3.
- The R2 request is closed with a note that the requirement is now satisfied.

## 4. Reset

```bash
make reset
```

Reset does the same thing as the **Reset demo** button:
- Clears SQLite and empties the 835 inbox.
- Resets the mock-hospital toggle and the mock payer appeals.
- Keeps `LLM_MODE`.

The queue should be empty, and a fresh submission gets 201 again.

## 5. Refresh AI recordings (team member with a key)

```bash
make record
```

This makes one live run of the happy case and the missing-evidence case. It writes
`fixtures/llm-replay/*.json` only if the outcomes match Appendix A8. Commit the new files after
`make test` passes. The secrets guard scans them.

## 6. Clean clone verified

**2026-09-12** (T130, `001-denial-recovery` @ `f52679b`): cloned the repo fresh into a temp
directory, checked out `001-denial-recovery`, and confirmed a Python backend clean-clone passes
with no pre-existing `.env` or `.local/`:

- `uv sync --locked` — clean install, no errors.
- `.env` built the same way `make setup` builds it (copy `.env.example`, generate
  `SFTP_PASSWORD`/`HOSPITAL_CLIENT_SECRET`/`PAYER_TOKEN` via `secrets.token_urlsafe(24)`), plus
  `mkdir -p .local/sftp/outbound-835 .local/data`.
- `uv run pytest -q` → **281 passed, 3 skipped** (identical to the working tree; the 3 skips are
  the `docker`-marked SFTP contract tests, which need `RECLAIM_DOCKER_TESTS=1` and a running
  compose stack by design).

**Not run**: the full `make setup`/`make test` pipeline (npm install, Playwright, docker compose)
was not executed end-to-end, because `web/` is **not tracked in git on this branch at all**
(`git ls-files web/` returns zero files — the Next.js frontend lives only on the separate
`Pranav` branch). A fresh clone of `001-denial-recovery` alone has no `web/` directory, so
`make setup`'s `cd web && npm install` step cannot succeed here regardless of backend state.
This is the expected branch-split (see `docs/reclaim-speckit-prompts.md` Appendix B and the
backend/frontend ownership split), not a new bug — full clean-clone verification of `make test`
should happen once this branch and `Pranav` are merged.
