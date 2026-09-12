import json

from mocks.northstar import app as payer_app
from reclaim.adapters.policy import FilePolicyStore
from reclaim.context import AppContext
from reclaim.models import Citation, EvidenceMatrix, HeaderField, Letter, LetterStatement, MatrixRow
from reclaim.steps.approve_and_submit import (
    NotReadyError,
    StaleVersionError,
    WrongRoleError,
    approve_and_submit,
)

HERO_CASE = dict(
    case_id="case-100028", hospital_claim_id="HSP-CLM-100028", lane="medical-necessity",
    status="ready-for-review", payer_claim_id="PAYER-CLM-99281", payer="Northstar Health",
    payer_id="NSTHLTH01", member_id="MEMBER-448820", rendering_npi="1234567893",
    procedure_qualifier="HC", procedure_code="72148", date_of_service="20260810",
    denial_code="CO-50", denial_reason="Medical necessity", billed_amount=4800.0, paid_amount=0.0,
    denied_amount=4800.0,
)

BILLING_APPROVER = {"userId": "billing-approver-01", "role": "authorized-billing-user"}
VIEWER = {"userId": "viewer-01", "role": "viewer"}

ATTACHMENTS = ["note-progress-031", "treatment-note-022", "order-901", "policy-snapshot-NST-IMG-2026-04"]
EXPECTED_UPLOAD_ORDER = ["appeal-letter-100028", *ATTACHMENTS]


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


def _seed_ready_for_review(repo, fixtures_dir, packet_status="ready-for-review", case_status="ready-for-review"):
    repo.upsert_case(HERO_CASE["case_id"], **{**{k: v for k, v in HERO_CASE.items() if k != "case_id"}, "status": case_status})
    repo.save_step_output("case-100028", "build_matrix", json.dumps({"matrix": json.loads(_matrix().model_dump_json())}))
    repo.save_packet(
        "case-100028", 1, status=packet_status, content_sha256="a" * 64,
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
    import hashlib

    for document_id, (document_type, content_type, content) in documents.items():
        repo.save_document(
            document_id=document_id, case_id="case-100028", document_type=document_type,
            content_type=content_type, content=content, sha256=hashlib.sha256(content).hexdigest(),
        )


class _RecordingPayerAdapter:
    """Wraps a real `NorthstarPayerAdapter` and records call order, so tests can assert the
    exact upload-then-submit sequence without touching `protocols.py`/`payer.py`."""

    def __init__(self, inner):
        self._inner = inner
        self.calls: list[str] = []

    async def get_decision(self, payer_claim_id):
        return await self._inner.get_decision(payer_claim_id)

    async def get_document(self, document_id):
        return await self._inner.get_document(document_id)

    async def upload_document(self, **kwargs):
        self.calls.append(f"upload:{kwargs['document_id']}")
        return await self._inner.upload_document(**kwargs)

    async def create_appeal(self, request, idempotency_key):
        self.calls.append("create_appeal")
        return await self._inner.create_appeal(request, idempotency_key=idempotency_key)

    async def get_appeal(self, appeal_id):
        return await self._inner.get_appeal(appeal_id)


def _ctx(repo, settings, payer_adapter):
    return AppContext(
        repo=repo, settings=settings, remit_inbox=None, claim_archive=None, ehr_client=None,
        policy_store=None, payer_adapter=payer_adapter, llm_client=None,
    )


async def test_billing_approver_uploads_in_order_and_submits(repo, settings, fixtures_dir, fixture_payer_adapter):
    _seed_ready_for_review(repo, fixtures_dir)
    recorder = _RecordingPayerAdapter(fixture_payer_adapter)
    ctx = _ctx(repo, settings, recorder)

    result = await approve_and_submit(ctx, "case-100028", 1, BILLING_APPROVER)

    assert recorder.calls == [*(f"upload:{doc_id}" for doc_id in EXPECTED_UPLOAD_ORDER), "create_appeal"]
    assert result.outcome == "submitted"
    assert result.appeal_id == "NST-APL-80126"
    assert result.expected_resolution_days == 14
    assert result.display == (
        "Submitted · Northstar confirmation NST-APL-80126 · expected resolution 14 days"
    )
    assert repo.get_case("case-100028")["status"] == "submitted"

    submission = repo.get_submission("appeal-case-100028-v1")
    assert submission["status"] == "confirmed"
    assert submission["appeal_id"] == "NST-APL-80126"


async def test_second_identical_call_is_idempotent_at_the_payer(repo, settings, fixtures_dir, fixture_payer_adapter):
    _seed_ready_for_review(repo, fixtures_dir)
    ctx = _ctx(repo, settings, fixture_payer_adapter)

    first = await approve_and_submit(ctx, "case-100028", 1, BILLING_APPROVER)
    second = await approve_and_submit(ctx, "case-100028", 1, BILLING_APPROVER)

    assert first.appeal_id == "NST-APL-80126"
    assert second.appeal_id == "NST-APL-80126"
    assert second.outcome == "submitted"
    assert len(payer_app.appeals) == 1


async def test_viewer_role_is_refused_with_no_payer_calls(repo, settings, fixtures_dir, fixture_payer_adapter):
    _seed_ready_for_review(repo, fixtures_dir)
    ctx = _ctx(repo, settings, fixture_payer_adapter)

    try:
        await approve_and_submit(ctx, "case-100028", 1, VIEWER)
        assert False, "expected WrongRoleError"
    except WrongRoleError:
        pass

    assert payer_app.documents == {}
    assert payer_app.appeals == {}
    assert repo.get_case("case-100028")["status"] == "ready-for-review"
    events = repo.list_events("case-100028")
    assert len(events) == 1
    assert "Refused approval" in events[0]["summary"]


async def test_unknown_persona_is_refused(repo, settings, fixtures_dir, fixture_payer_adapter):
    _seed_ready_for_review(repo, fixtures_dir)
    ctx = _ctx(repo, settings, fixture_payer_adapter)

    try:
        await approve_and_submit(ctx, "case-100028", 1, None)
        assert False, "expected WrongRoleError"
    except WrongRoleError:
        pass

    assert payer_app.documents == {}
    assert payer_app.appeals == {}
    assert repo.get_case("case-100028")["status"] == "ready-for-review"


async def test_stale_version_is_refused(repo, settings, fixtures_dir, fixture_payer_adapter):
    _seed_ready_for_review(repo, fixtures_dir)
    ctx = _ctx(repo, settings, fixture_payer_adapter)

    try:
        await approve_and_submit(ctx, "case-100028", 2, BILLING_APPROVER)
        assert False, "expected StaleVersionError"
    except StaleVersionError:
        pass

    assert payer_app.documents == {}
    assert payer_app.appeals == {}
    assert repo.get_case("case-100028")["status"] == "ready-for-review"
    events = repo.list_events("case-100028")
    assert len(events) == 1
    assert "Refused approval" in events[0]["summary"]


async def test_packet_not_ready_is_refused(repo, settings, fixtures_dir, fixture_payer_adapter):
    _seed_ready_for_review(repo, fixtures_dir, packet_status="blocked")
    ctx = _ctx(repo, settings, fixture_payer_adapter)

    try:
        await approve_and_submit(ctx, "case-100028", 1, BILLING_APPROVER)
        assert False, "expected NotReadyError"
    except NotReadyError:
        pass

    assert payer_app.documents == {}
    assert payer_app.appeals == {}


async def test_payer_window_closed_gives_refused_outcome(repo, settings, fixtures_dir, fixture_payer_adapter):
    _seed_ready_for_review(repo, fixtures_dir)
    payer_app.set_demo_today("2026-10-20")
    try:
        ctx = _ctx(repo, settings, fixture_payer_adapter)

        result = await approve_and_submit(ctx, "case-100028", 1, BILLING_APPROVER)

        assert result.outcome == "refused"
        assert result.payer_error_code == "appeal_window_closed"
        assert result.display is None
        assert repo.get_case("case-100028")["status"] == "approved"

        submission = repo.get_submission("appeal-case-100028-v1")
        assert submission["status"] == "refused"
        assert submission["error_code"] == "appeal_window_closed"

        events = repo.list_events("case-100028")
        assert all("Submitted" not in e["summary"] for e in events)
        assert "Submitted" not in result.model_dump_json()
    finally:
        payer_app.set_demo_today(None)
