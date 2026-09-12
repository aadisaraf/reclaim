# Reclaim

Reclaim is a hackathon demo of an evidence-first denial-recovery agent for medical-necessity
insurance denials. It reads a real-shaped X12 835 remittance and 837P claim, resolves the denial
to the exact patient and encounter through a six-check identity gate, gathers only the clinical
evidence that falls inside a policy-defined lookback window from a FHIR EHR, builds a
policy-requirement evidence matrix where every citation is verified against real excerpts rather
than trusted from an LLM, drafts a fully cited appeal letter, and submits it to the payer only
after a human approves. **All data in this repository is SYNTHETIC DEMO DATA** — there is no real
patient, claim, or payer information anywhere in this repo, and every screen and generated
document says so.

## Quickstart

```bash
make setup
make test
make demo
```

Then open the web app and click through the demo in six steps:

1. **Simulate incoming remit** — a denial arrives on its own, no upload.
2. **Open the case** — see the identity checks pass, tying the remit to the original claim and
   encounter.
3. **Evidence tab** — see the clinical evidence gathered from the mock FHIR hospital, in scope and
   out of scope.
4. **Matrix tab** — see the evidence matrix, one row per policy requirement, backed by verified
   citations.
5. **Packet tab** — see the drafted, cited appeal packet, ready for review.
6. **Approve and submit** — a human approves, the appeal is submitted, and tracking begins.

```bash
make reset
```

`make reset` clears the case queue and mock state so you can run the demo again from a clean
slate. For the detailed walkthrough, including exact on-screen text, the missing-evidence toggle,
and negative-path checks, see
[`specs/001-denial-recovery/quickstart.md`](specs/001-denial-recovery/quickstart.md).

## Architecture

- **A nine-step pipeline, not a framework.** One plain async function runs named steps in order
  (`ingest`, `fetch_claim`, `resolve_identity`, `gather_evidence`, `payer_context`,
  `build_matrix`, `draft_packet`, `approve_and_submit`, `track`), persisting a typed output and
  exactly one human-readable audit event after each step.
- **Two mock services stand in for real hospital and payer systems.** `mock-hospital` is a FHIR
  R4 server in front of fixture data, and `mock-northstar-health` is a payer REST API — both are
  clearly labelled mocks behind the same adapter interfaces a production integration would use.
- **A hand-written X12 parser.** The 835 remittance and 837P claim are read with a tokenizer and
  loop readers built for this project, reading delimiters from the ISA segment and validating
  envelope structure and balancing — no third-party EDI library.
- **LLM-propose, code-verify, never trust blindly.** The LLM proposes evidence citations and
  letter phrasing, but a separate deterministic verifier checks every citation is real, in scope,
  and an exact substring of the source before it is ever accepted — an LLM's claim about the
  evidence is never the last word.
- **Local storage, one API.** Case state, audit events, and step outputs live in a single SQLite
  file behind a small repository module, served by a FastAPI app that the web UI polls.

## Secrets

API keys and other secrets belong **only** in a local, gitignored `.env` file — never in code,
fixtures, documentation, or commits.
