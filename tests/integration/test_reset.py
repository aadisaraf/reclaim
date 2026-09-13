"""T112: `tests/integration/test_reset.py`.

Starts from a submitted hero case (`case-100028`) with the missing-evidence toggle
genuinely on at the hospital mock, a real appeal recorded at the payer mock, a task in
the `tasks` table, and a file sitting in the remit inbox. Then drives `POST
/api/demo/reset` through a real ASGI app and asserts every corner of demo state comes
back clean -- including that a freshly seeded case afterward gets a genuinely new
appeal (fresh 201) rather than an idempotent replay of the pre-reset submission (which
would mean the payer mock's idempotency-key bookkeeping survived the reset).

Uses `fixture_ehr_client`/`fixture_payer_adapter` (real `HttpEhrClient`/
`NorthstarPayerAdapter` against in-process ASGI transports of the mock hospital/payer
apps) so the toggle and appeal state exercised here are real mock state, not fakes.
"""

import hashlib

import httpx

from mocks.northstar import app as payer_app
from reclaim import demo
from reclaim.adapters.policy import FilePolicyStore
from reclaim.context import AppContext
from reclaim.main import create_app
from reclaim.models import Citation, EvidenceMatrix, HeaderField, Letter, LetterStatement, MatrixRow
from reclaim.steps.approve_and_submit import approve_and_submit
from tests.fakes import FakeInbox

HERO_CASE = dict(
    case_id="case-100028", hospital_claim_id="HSP-CLM-100028", lane="medical-necessity",
    status="ready-for-review", payer_claim_id="PAYER-CLM-99281", payer="Northstar Health",
    payer_id="NSTHLTH01", member_id="MEMBER-448820", rendering_npi="1234567893",
    procedure_qualifier="HC", procedure_code="72148", date_of_service="20260810",
    denial_code="CO-50", denial_reason="Medical necessity", billed_amount=4800.0, paid_amount=0.0,
    denied_amount=4800.0,
)

BILLING_APPROVER = {"userId": "billing-approver-01", "role": "authorized-billing-user"}
ATTACHMENTS = ["note-progress-031", "treatment-note-022", "order-901", "policy-snapshot-NST-IMG-2026-04"]

RESET_TABLES = (
    "remit_files", "cases", "step_outputs", "audit_events", "tasks", "packets", "submissions", "documents",
)


def _matrix() -> EvidenceMatrix:
    return EvidenceMatrix(
        case_id="case-100028", policy_id="NST-IMG-2026-04", policy_version="2026.04",
        summary={"satisfied": 3, "total": 3},
        requirements=[
            MatrixRow(requirement_id="R1", status="satisfied", evidence=[
                Citation(citation_id="R1-C1", resource="Condition/condition-100",
                         date="2026-05-28", excerpt="Lumbar radiculopathy", verified=True),
                Citation(citation_id="R1-C2", resource="DocumentReference/note-progress-031",
                         document="Binary/note-progress-031", date="2026-08-10",
                         excerpt="consistent with lumbar radiculopathy", verified=True),
            ]),
            MatrixRow(requirement_id="R2", status="satisfied", evidence=[
                Citation(citation_id="R2-C1", resource="DocumentReference/treatment-note-022",
                         document="Binary/treatment-note-022", date="2026-07-14",
                         excerpt="6 weeks of supervised physical therapy", verified=True),
            ]),
            MatrixRow(requirement_id="R3", status="satisfied", evidence=[
                Citation(citation_id="R3-C1", resource="ServiceRequest/order-901", date="2026-08-10",
                         excerpt="Ordering lumbar MRI without contrast given radiating left leg pain",
                         verified=True),
            ]),
        ],
    )


def _letter() -> Letter:
    return Letter(
        header=[
            HeaderField(label="Hospital claim ID", value="HSP-CLM-100028", source="remit"),
            HeaderField(label="Payer claim ID", value="PAYER-CLM-99281", source="remit"),
        ],
        body=[
            LetterStatement(statement_id="S1", text="The chart documents lumbar radiculopathy.",
                             requirement_ids=["R1"], citation_ids=["R1-C1", "R1-C2"]),
            LetterStatement(statement_id="S2", text="6 weeks of conservative treatment was tried first.",
                             requirement_ids=["R2"], citation_ids=["R2-C1"]),
            LetterStatement(statement_id="S3", text="The treating clinician documented the rationale for imaging.",
                             requirement_ids=["R3"], citation_ids=["R3-C1"]),
        ],
        requested_action="Please reconsider and reprocess payment",
        attachments=list(ATTACHMENTS),
        required_approver="authorized-billing-user",
        version=1,
    )


def _seed_ready_for_review(repo, fixtures_dir) -> None:
    """Seeds a fresh `case-100028` at `ready-for-review` with a satisfied matrix, a
    ready packet, and every document `approve_and_submit` needs to upload -- enough for
    a real `approve_and_submit(...)` call to reach the payer mock's `POST /appeals`.
    Test-local copy of `tests/integration/test_submit.py`'s `_seed_ready_for_review`
    (kept self-contained here rather than importing across test modules)."""
    repo.upsert_case(HERO_CASE["case_id"], **{k: v for k, v in HERO_CASE.items() if k != "case_id"})
    repo.save_step_output(
        "case-100028", "build_matrix",
        f'{{"matrix": {_matrix().model_dump_json()}}}',
    )
    repo.save_packet(
        "case-100028", 1, status="ready-for-review", content_sha256="a" * 64,
        letter_json=_letter().model_dump_json(), blocked_reason=None,
        html="<html>packet</html>", pdf=b"%PDF-1.4 fake appeal letter",
        approved_by=None, approved_role=None, approved_at=None,
    )

    policy_snapshot = FilePolicyStore(fixtures_dir / "policies").snapshot_bytes("NST-IMG-2026-04", "2026.04")
    documents = {
        "appeal-letter-100028": ("appeal-letter", "application/pdf", b"%PDF-1.4 fake appeal letter"),
        "note-progress-031": ("clinical-note", "text/plain", b"progress note text"),
        "treatment-note-022": ("clinical-note", "text/plain", b"treatment note text"),
        "order-901": ("order", "application/json", b'{"resourceType": "ServiceRequest"}'),
        "policy-snapshot-NST-IMG-2026-04": ("policy-snapshot", "application/json", policy_snapshot),
    }
    for document_id, (document_type, content_type, content) in documents.items():
        repo.save_document(
            document_id=document_id, case_id="case-100028", document_type=document_type,
            content_type=content_type, content=content, sha256=hashlib.sha256(content).hexdigest(),
        )


class _RecordingPayerAdapter:
    """Wraps a real `NorthstarPayerAdapter` and records every `create_appeal` receipt,
    so the test can check `replayed` directly -- the one signal that distinguishes a
    genuine 201 from an idempotent-replay 200 at the payer mock."""

    def __init__(self, inner):
        self._inner = inner
        self.receipts: list = []

    async def get_decision(self, payer_claim_id):
        return await self._inner.get_decision(payer_claim_id)

    async def get_document(self, document_id):
        return await self._inner.get_document(document_id)

    async def upload_document(self, **kwargs):
        return await self._inner.upload_document(**kwargs)

    async def create_appeal(self, request, idempotency_key):
        receipt = await self._inner.create_appeal(request, idempotency_key=idempotency_key)
        self.receipts.append(receipt)
        return receipt

    async def get_appeal(self, appeal_id):
        return await self._inner.get_appeal(appeal_id)

    async def control_reset(self):
        await self._inner.control_reset()


async def test_reset_clears_every_table_and_lets_a_fresh_case_submit_again(
    repo, settings, fixtures_dir, fixture_ehr_client, fixture_payer_adapter
):
    remit_inbox = FakeInbox()
    recorder = _RecordingPayerAdapter(fixture_payer_adapter)
    ctx = AppContext(
        repo=repo, settings=settings, remit_inbox=remit_inbox, claim_archive=None,
        ehr_client=fixture_ehr_client, policy_store=FilePolicyStore(fixtures_dir / "policies"),
        payer_adapter=recorder, llm_client=None,
    )
    # A leftover poller "seen" entry, so we can prove `reset_demo` actually clears it.
    ctx.poller_seen.add("era-2026-09-12.835")

    app = create_app(settings, ctx)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            # --- arrange: a submitted hero case with a real payer appeal -----------------
            _seed_ready_for_review(repo, fixtures_dir)
            result = await approve_and_submit(ctx, "case-100028", 1, BILLING_APPROVER)
            assert result.outcome == "submitted"
            assert repo.get_case("case-100028")["status"] == "submitted"
            assert len(payer_app.appeals) == 1
            assert len(payer_app.idempotency_records) == 1
            assert recorder.receipts[-1].replayed is False, "first submission should never be a replay"

            # --- arrange: a task present in the tasks table ------------------------------
            repo.upsert_task(
                "task-case-100028-R2", case_id="case-100028", task_type="clinician-request",
                requirement_id="R2", assignee_role="clinician",
                question="Please confirm 6 weeks of supervised physical therapy.",
                status="open", close_note=None,
            )
            assert len(repo.list_tasks("case-100028")) == 1

            # --- arrange: missing-evidence toggle genuinely on at the hospital mock ------
            toggle_resp = await client.put("/api/demo/missing-evidence", json={"enabled": True})
            assert toggle_resp.status_code == 200
            assert toggle_resp.json() == {"enabled": True}
            assert (await ctx.ehr_client.control("GET", "state"))["missingEvidence"] is True
            assert (await client.get("/api/config")).json()["missingEvidence"] is True

            # --- arrange: a file sitting in the remit inbox -------------------------------
            sim_resp = await client.post("/api/demo/simulate-remit")
            assert sim_resp.status_code == 202
            assert len(await remit_inbox.list_files()) == 1

            # --- act: reset ---------------------------------------------------------------
            reset_resp = await client.post("/api/demo/reset")
            assert reset_resp.status_code == 204
            assert reset_resp.content == b""

            # --- assert: every repo table the reset owns is empty -------------------------
            assert repo.get_case("case-100028") is None
            assert repo.list_cases() == []
            for table in RESET_TABLES:
                count = repo.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                assert count == 0, f"table {table!r} still has rows after reset"

            # --- assert: inbox empty -------------------------------------------------------
            assert await remit_inbox.list_files() == []

            # --- assert: poller's seen-file set cleared -------------------------------------
            assert ctx.poller_seen == set()

            # --- assert: hospital mock's real state is off, and so is the app's flag -------
            #
            # `reset_demo` calls `ctx.ehr_client.control("POST", "reset")`, which hits the
            # hospital mock's `POST /_control/reset` -- and that clears the mock's
            # `issued_tokens` set, invalidating the very token `ctx.ehr_client` just used
            # to make that call. `HttpEhrClient` handles this by retrying once with a
            # freshly-fetched token whenever a request 401s (see `_get`/`control` in
            # `src/reclaim/adapters/fhir.py`), and `control("POST", "reset")` also proactively
            # drops its cached token so the *next* call always re-authenticates. So the same
            # long-lived `ctx.ehr_client` the app already holds keeps working after reset,
            # with no process restart required.
            assert (await ctx.ehr_client.control("GET", "state"))["missingEvidence"] is False
            config_after = (await client.get("/api/config")).json()
            assert config_after["missingEvidence"] is False
            assert demo.get_missing_evidence() is False

            # --- assert: aiMode is untouched by reset (Settings itself isn't reset) --------
            assert config_after["aiMode"] == "replay"

            # --- assert: payer mock holds no appeals/documents/idempotency state -----------
            assert payer_app.appeals == {}
            assert payer_app.documents == {}
            assert payer_app.idempotency_records == {}

            # --- act: a freshly seeded case must get a genuine 201, not a 200 replay -------
            _seed_ready_for_review(repo, fixtures_dir)
            second_result = await approve_and_submit(ctx, "case-100028", 1, BILLING_APPROVER)

            assert second_result.outcome == "submitted"
            assert len(payer_app.appeals) == 1
            assert recorder.receipts[-1].replayed is False, (
                "post-reset submission replayed the pre-reset appeal -- "
                "idempotency-key state survived the reset"
            )
    finally:
        # Defensive cleanup: `demo._missing_evidence_enabled` is module-level state, so
        # guarantee it is reset even if an assertion above failed mid-test. Set the
        # private flag directly (not via `demo.reset_demo`/`set_missing_evidence`,
        # which would round-trip through `ctx.ehr_client` and could hit the stale-token
        # bug documented above if this cleanup runs before the real reset succeeded).
        demo._missing_evidence_enabled = False
