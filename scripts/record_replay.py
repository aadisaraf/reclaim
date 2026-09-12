"""T102: records real OpenAI Responses API outputs for the hero case and the missing-evidence
variant, then checks the result against Appendix A8 (hand-written, never read back from the
model's own output -- Constitution VIII) before trusting it as a replay fixture.

Deliberately NOT run automatically. It spends real OpenAI API credits, so it is a deliberate,
human-triggered action (`make record`, which sets `LLM_MODE=live` and needs `OPENAI_API_KEY`
in the local, gitignored `.env` -- never read or printed by this script beyond handing it to
the OpenAI client) -- see T103. Running it is someone else's call, not this task's.

What it does:
  1. Builds an in-process app context: the hospital and payer mocks over `httpx.ASGITransport`
     (no network), an in-memory remit inbox and claim archive, a temp SQLite `Repo`, and a real
     `OpenAiLlmClient` recording to a temp directory.
  2. Delivers `fixtures/x12/era-2026-09-12.835` and runs the hero case through the pipeline
     (`reclaim.pipeline.run_case`) to `ready-for-review`.
  3. Asserts the Appendix A8 happy-path outcomes: 3/3 satisfied, R1 -> condition-100 +
     note-progress-031, R2 -> treatment-note-022, R3 -> order-901.
  4. Repeats with a fresh case and the hospital mock's `/_control/missing-evidence` toggle on,
     asserting 2/3 with R2 `missing` and the exact A8 reason text.
  5. Only if every assertion in both scenarios holds, copies the recorded JSON files into
     `fixtures/llm-replay/`. Any assertion failure, or an empty recording directory, means
     nothing is copied and the process exits non-zero -- a bad run can never silently replace
     good recordings.

`fixtures/llm-replay/` is otherwise produced only by a human running `make record` and
committing the result (T103); this script is the thing `make record` runs.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import httpx

from reclaim.adapters.fhir import HttpEhrClient
from reclaim.adapters.llm import OpenAiLlmClient
from reclaim.adapters.payer import NorthstarPayerAdapter
from reclaim.adapters.policy import FilePolicyStore
from reclaim.adapters.protocols import RemitFileRef
from reclaim.config import Settings
from reclaim.context import AppContext
from reclaim.pipeline import run_case
from reclaim.repo import Repo
from reclaim.steps.ingest import ingest

REPO_ROOT = Path(__file__).resolve().parents[1]
REMIT_FIXTURE = REPO_ROOT / "fixtures" / "x12" / "era-2026-09-12.835"
CLAIM_837_FIXTURE = REPO_ROOT / "fixtures" / "x12" / "HSP-CLM-100028.837"
POLICIES_DIR = REPO_ROOT / "fixtures" / "policies"
HOSPITAL_BASE = "http://mock-hospital.example"
PAYER_BASE = "http://mock-northstar-health.example/api/v1"
CASE_ID = "case-100028"
LIVE_RECORD_DIR = REPO_ROOT / "fixtures" / "llm-replay"

MISSING_EVIDENCE_R2_REASON = (
    "No DocumentReference or MedicationRequest in the lookback window documents a "
    "6-week conservative treatment trial"
)


# --- tiny in-memory fakes ---------------------------------------------------------------
#
# Duplicated from `tests/fakes.py::FakeInbox`/`FakeArchive` (a test-only module) rather than
# imported, so this dev script -- which `make record` runs outside pytest -- has no import
# dependency on `tests/`. They are intentionally identical in shape to their test twins.


class _InProcessInbox:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    async def list_files(self) -> list[RemitFileRef]:
        return [RemitFileRef(name=n, size=len(c), mtime=0) for n, c in self.files.items()]

    async def download(self, name: str) -> bytes:
        return self.files[name]

    async def deliver(self, name: str, content: bytes) -> None:
        self.files[name] = content

    async def clear(self) -> None:
        self.files.clear()


class _InProcessArchive:
    def __init__(self) -> None:
        self.claims: dict[str, bytes] = {}

    async def get_837(self, hospital_claim_id: str) -> bytes | None:
        return self.claims.get(hospital_claim_id)


# --- context assembly -------------------------------------------------------------------


def _build_context(settings: Settings, repo: Repo, record_dir: Path) -> AppContext:
    from mocks.hospital import app as hospital_app
    from mocks.northstar import app as payer_app

    hospital_app.reset_state()
    payer_app.reset_state()

    archive = _InProcessArchive()
    archive.claims["HSP-CLM-100028"] = CLAIM_837_FIXTURE.read_bytes()

    ehr_client = HttpEhrClient(
        base_url=f"{HOSPITAL_BASE}/fhir/R4", token_url=f"{HOSPITAL_BASE}/auth/token",
        client_id=settings.hospital_client_id, client_secret=settings.hospital_client_secret,
        transport=httpx.ASGITransport(app=hospital_app.app),
    )
    payer_adapter = NorthstarPayerAdapter(
        base_url=PAYER_BASE, token=settings.payer_token,
        transport=httpx.ASGITransport(app=payer_app.app),
    )
    llm_client = OpenAiLlmClient(
        api_key=settings.openai_api_key, model=settings.openai_model, record_dir=record_dir,
    )

    return AppContext(
        repo=repo, settings=settings, remit_inbox=_InProcessInbox(), claim_archive=archive,
        ehr_client=ehr_client, policy_store=FilePolicyStore(POLICIES_DIR),
        payer_adapter=payer_adapter, llm_client=llm_client,
    )


async def _set_hospital_missing_evidence(enabled: bool, settings: Settings) -> None:
    """Flips the hospital mock's demo-only toggle via its real HTTP control endpoint
    (`PUT /_control/missing-evidence`, gated by the same bearer token as the FHIR routes --
    see `mocks/hospital/app.py`), not by poking its module globals directly."""
    from mocks.hospital import app as hospital_app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=hospital_app.app)) as client:
        token_resp = await client.post(
            f"{HOSPITAL_BASE}/auth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": settings.hospital_client_id,
                "client_secret": settings.hospital_client_secret,
            },
        )
        token_resp.raise_for_status()
        token = token_resp.json()["access_token"]
        resp = await client.put(
            f"{HOSPITAL_BASE}/_control/missing-evidence",
            json={"enabled": enabled},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()


async def _run_hero_case(ctx: AppContext) -> None:
    content = REMIT_FIXTURE.read_bytes()
    await ctx.remit_inbox.deliver(REMIT_FIXTURE.name, content)
    result = ingest(ctx.repo, ctx.settings, REMIT_FIXTURE.name, content)
    if CASE_ID not in result.new_case_ids:
        raise AssertionError(f"expected ingest to create {CASE_ID}, got {result.new_case_ids}")
    await run_case(ctx, CASE_ID)


def _matrix_rows(repo: Repo) -> dict[str, dict]:
    matrix_output = repo.get_step_output(CASE_ID, "build_matrix") or {}
    matrix = matrix_output.get("matrix") or {}
    return {row["requirement_id"]: row for row in matrix.get("requirements", [])}


def _assert_happy_path(repo: Repo) -> None:
    case = repo.get_case(CASE_ID)
    if case is None:
        raise AssertionError(f"{CASE_ID} was not created")
    if case["status"] != "ready-for-review":
        raise AssertionError(f"expected status ready-for-review, got {case['status']!r} "
                              f"(last_error={case.get('last_error')!r})")

    matrix_output = repo.get_step_output(CASE_ID, "build_matrix") or {}
    summary = (matrix_output.get("matrix") or {}).get("summary")
    if summary != {"satisfied": 3, "total": 3}:
        raise AssertionError(f"expected summary 3/3, got {summary!r}")

    rows = _matrix_rows(repo)
    checks = {
        "R1": {"Condition/condition-100", "DocumentReference/note-progress-031"},
        "R2": {"DocumentReference/treatment-note-022"},
        "R3": {"ServiceRequest/order-901"},
    }
    for requirement_id, expected_resources in checks.items():
        actual_resources = {c["resource"] for c in rows[requirement_id]["evidence"]}
        if actual_resources != expected_resources:
            raise AssertionError(
                f"{requirement_id}: expected citations {expected_resources}, got {actual_resources}"
            )

    packet = repo.latest_packet(CASE_ID)
    if packet is None or packet["status"] != "ready-for-review":
        raise AssertionError(f"expected a ready-for-review packet, got {packet!r}")


def _assert_missing_evidence(repo: Repo) -> None:
    case = repo.get_case(CASE_ID)
    if case is None:
        raise AssertionError(f"{CASE_ID} was not created")
    if case["status"] != "needs-evidence":
        raise AssertionError(f"expected status needs-evidence, got {case['status']!r} "
                              f"(last_error={case.get('last_error')!r})")

    matrix_output = repo.get_step_output(CASE_ID, "build_matrix") or {}
    summary = (matrix_output.get("matrix") or {}).get("summary")
    if summary != {"satisfied": 2, "total": 3}:
        raise AssertionError(f"expected summary 2/3, got {summary!r}")

    rows = _matrix_rows(repo)
    if rows["R2"]["status"] != "missing":
        raise AssertionError(f"expected R2 missing, got {rows['R2']!r}")
    if rows["R2"].get("reason") != MISSING_EVIDENCE_R2_REASON:
        raise AssertionError(f"R2 reason mismatch: {rows['R2'].get('reason')!r}")


def _copy_recordings(record_dir: Path) -> bool:
    if not record_dir.exists() or not any(record_dir.rglob("*.json")):
        return False
    LIVE_RECORD_DIR.mkdir(parents=True, exist_ok=True)
    for step_dir in sorted(p for p in record_dir.iterdir() if p.is_dir()):
        dest_dir = LIVE_RECORD_DIR / step_dir.name
        dest_dir.mkdir(parents=True, exist_ok=True)
        for recording in sorted(step_dir.glob("*.json")):
            shutil.copy2(recording, dest_dir / recording.name)
    return True


async def _record() -> int:
    settings = Settings.from_env()
    if not settings.openai_api_key:
        print(
            "OPENAI_API_KEY is not set (only in the local, gitignored .env) -- refusing to "
            "record, since this would just fail against the live API.",
            file=sys.stderr,
        )
        return 1

    with tempfile.TemporaryDirectory(prefix="reclaim-record-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        record_dir = tmp_path / "llm-replay"

        # Scenario 1: happy path -> ready-for-review, 3/3 (Appendix A8).
        repo_happy = Repo(str(tmp_path / "happy.db"))
        repo_happy.init_schema()
        ctx_happy = _build_context(settings, repo_happy, record_dir)
        try:
            await _run_hero_case(ctx_happy)
            _assert_happy_path(repo_happy)
        except AssertionError as exc:
            print(f"Happy-path recording did not match Appendix A8: {exc}", file=sys.stderr)
            return 1

        # Scenario 2: missing-evidence mode -> needs-evidence, 2/3 (Appendix A8).
        repo_missing = Repo(str(tmp_path / "missing.db"))
        repo_missing.init_schema()
        ctx_missing = _build_context(settings, repo_missing, record_dir)
        await _set_hospital_missing_evidence(True, settings)
        try:
            await _run_hero_case(ctx_missing)
            _assert_missing_evidence(repo_missing)
        except AssertionError as exc:
            print(f"Missing-evidence recording did not match Appendix A8: {exc}", file=sys.stderr)
            return 1
        finally:
            await _set_hospital_missing_evidence(False, settings)

        if not _copy_recordings(record_dir):
            print("No recordings were written by the live client; nothing to copy.", file=sys.stderr)
            return 1

    print(f"Both scenarios matched Appendix A8. Recordings copied into {LIVE_RECORD_DIR}.")
    return 0


def main() -> int:
    import asyncio

    return asyncio.run(_record())


if __name__ == "__main__":
    raise SystemExit(main())
