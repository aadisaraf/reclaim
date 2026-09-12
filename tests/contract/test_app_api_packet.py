"""Contract tests for the packet section of GET /api/cases/{caseId}, plus
GET /api/cases/{caseId}/packets/{version}/pdf and GET /api/cases/{caseId}/documents/{documentId} (T089).

Phase 7's T094 (wiring these into src/reclaim/api.py) is out of scope for this session -- these
tests are written against the documented contract now and are EXPECTED TO FAIL (a missing
"packet" key, or a 404 on the two new routes) until that wiring lands. That's fine and expected
under TDD; this file exists so the wiring has a precise, hand-written target:

  GET /api/cases/{caseId} response gains:
    - packet: null, or {version, status, blockedReason, header: [{label, value, source}],
      statements: [{statementId, text, requirementIds, citationIds}], attachments: [...],
      requestedAction, requiredApprover, footer} (camelCase, mirroring the rest of the API and
      src/reclaim/models.py's Letter/HeaderField/LetterStatement fields)
    - statusLine: derived the same way as every other case status ("ready-for-review" ->
      "Ready for review"), same as tests/contract/test_app_api_case_identity.py already does for
      "claim-matched" -> "Claim matched"
    - completenessLine / recoveryLine: already implemented per
      tests/contract/test_app_api_case_detail_full.py -- unchanged by this test
    - deadline.line: already implemented per test_app_api_case_detail_full.py -- unchanged

  GET /api/cases/{caseId}/packets/{version}/pdf -> 200 application/pdf, body = packets.pdf
  GET /api/cases/{caseId}/documents/{documentId} -> 200 <documents.content_type>, body = documents.bytes

All values are hand-copied from docs/reclaim-speckit-prompts.md Appendix A (A6-A8) and
specs/001-denial-recovery/data-model.md, reusing the hero-case fixture pattern from
tests/contract/test_app_api_case_detail_full.py.
"""

import hashlib
import json

import httpx

from reclaim.context import AppContext
from reclaim.main import create_app
from reclaim.models import HeaderField, Letter, LetterStatement
from reclaim.pdf import render_pdf

HERO_CASE = dict(
    case_id="case-100028", hospital_claim_id="HSP-CLM-100028", lane="medical-necessity",
    status="ready-for-review", payer_claim_id="PAYER-CLM-99281", payer="Northstar Health",
    payer_id="NSTHLTH01", member_id="MEMBER-448820", rendering_npi="1234567893",
    procedure_qualifier="HC", procedure_code="72148", date_of_service="20260810",
    denial_code="CO-50", denial_reason="Medical necessity", billed_amount=4800.0, paid_amount=0.0,
    denied_amount=4800.0, running=0, needs_review_field=None, last_error=None,
)

EVIDENCE_SET = {
    "items": [
        {"resource": "DocumentReference/note-progress-031", "resource_type": "DocumentReference",
         "date": "2026-08-10", "source_url": "DocumentReference/note-progress-031", "included": True,
         "exclusion_reason": None, "summary": "", "document": "Binary/note-progress-031",
         "text": "Assessment: Findings are consistent with lumbar radiculopathy.", "raw": {}},
    ],
    "excluded_count": 1,
    "search_counts": {"MedicationRequest": 0},
    "lookback_start": "2026-02-10", "lookback_end": "2026-08-10", "coverage_plan_type": "Commercial PPO",
}

PAYER_DECISION = {
    "payerClaimId": "PAYER-CLM-99281", "claimId": "HSP-CLM-100028", "decision": "denied",
    "decisionDate": "2026-08-20", "reasonCode": "CO-50",
    "reasonText": "Insufficient documentation of medical necessity",
    "appealDeadline": "2026-10-19", "allowedSubmissionChannels": ["portal", "fax"],
    "letter": {"documentId": "denial-letter-99281", "url": "/api/v1/documents/denial-letter-99281"},
}

DEADLINE = {"deadline_of_record": "2026-10-19", "policy_window_date": "2026-10-19", "days_left": 37, "warning": None}

MATRIX = {
    "case_id": "case-100028", "policy_id": "NST-IMG-2026-04", "policy_version": "2026.04",
    "summary": {"satisfied": 3, "total": 3},
    "requirements": [
        {"requirement_id": "R1", "status": "satisfied", "reason": None, "evidence": [
            {"citation_id": "R1-C1", "resource": "Condition/condition-100", "document": None,
             "date": "2026-05-28", "excerpt": "Lumbar radiculopathy", "verified": True, "rejection_reason": None},
            {"citation_id": "R1-C2", "resource": "DocumentReference/note-progress-031",
             "document": "Binary/note-progress-031", "date": "2026-08-10",
             "excerpt": "consistent with lumbar radiculopathy", "verified": True, "rejection_reason": None},
        ]},
        {"requirement_id": "R2", "status": "satisfied", "reason": None, "evidence": [
            {"citation_id": "R2-C1", "resource": "DocumentReference/treatment-note-022",
             "document": "Binary/treatment-note-022", "date": "2026-07-14",
             "excerpt": "6 weeks of supervised physical therapy", "verified": True, "rejection_reason": None},
        ]},
        {"requirement_id": "R3", "status": "satisfied", "reason": None, "evidence": [
            {"citation_id": "R3-C1", "resource": "ServiceRequest/order-901", "document": None,
             "date": "2026-08-10", "excerpt": "Ordering lumbar MRI without contrast given radiating left leg pain",
             "verified": True, "rejection_reason": None},
        ]},
    ],
}


def _hero_letter() -> Letter:
    header = [
        HeaderField(label="Hospital claim ID", value="HSP-CLM-100028", source="remit"),
        HeaderField(label="Payer claim ID", value="PAYER-CLM-99281", source="remit"),
        HeaderField(label="Patient MRN", value="MRN-0042", source="claimMap"),
        HeaderField(label="Member ID", value="MEMBER-448820", source="claim837"),
        HeaderField(label="Procedure code", value="72148", source="claim837"),
        HeaderField(label="Diagnosis code", value="M54.16", source="claim837"),
        HeaderField(label="Rendering provider NPI", value="1234567893", source="claim837"),
        HeaderField(label="Date of service", value="2026-08-10", source="claim837"),
        HeaderField(label="Billed amount", value="$4,800", source="remit"),
        HeaderField(label="Denial reason", value="CO-50 Insufficient documentation of medical necessity",
                    source="payerDecision"),
        HeaderField(label="Policy", value="NST-IMG-2026-04 v2026.04", source="policy"),
    ]
    body = [
        LetterStatement(statement_id="S1", text="The patient has a documented diagnosis of lumbar radiculopathy.",
                         requirement_ids=["R1"], citation_ids=["R1-C1", "R1-C2"]),
        LetterStatement(statement_id="S2", text="The patient completed 6 weeks of supervised physical therapy.",
                         requirement_ids=["R2"], citation_ids=["R2-C1"]),
        LetterStatement(statement_id="S3", text="The treating clinician documented clinical rationale for the MRI.",
                         requirement_ids=["R3"], citation_ids=["R3-C1"]),
    ]
    return Letter(
        header=header, body=body, requested_action="Please reconsider and reprocess payment",
        attachments=["note-progress-031", "treatment-note-022", "order-901", "policy-snapshot-NST-IMG-2026-04"],
        required_approver="authorized-billing-user", version=1,
    )


def _ctx(repo, settings, fixtures_dir) -> AppContext:
    from reclaim.adapters.policy import FilePolicyStore

    return AppContext(
        repo=repo, settings=settings, remit_inbox=None, claim_archive=None, ehr_client=None,
        policy_store=FilePolicyStore(fixtures_dir / "policies"), payer_adapter=None, llm_client=None,
    )


def _seed(repo, settings):
    repo.upsert_case(HERO_CASE["case_id"], **{k: v for k, v in HERO_CASE.items() if k != "case_id"})
    repo.save_step_output("case-100028", "gather_evidence", json.dumps({
        "evidence_set": EVIDENCE_SET, "policy_id": "NST-IMG-2026-04", "policy_version": "2026.04",
        "appeal_window_days": 60,
    }))
    repo.save_step_output("case-100028", "payer_context", json.dumps({
        "decision": PAYER_DECISION, "deadline": DEADLINE,
        "policy_id": "NST-IMG-2026-04", "policy_version": "2026.04",
    }))
    repo.save_step_output("case-100028", "build_matrix", json.dumps({"matrix": MATRIX}))

    letter = _hero_letter()
    pdf_bytes = render_pdf(letter)
    repo.save_packet(
        "case-100028", 1, status="ready-for-review",
        content_sha256=hashlib.sha256(letter.model_dump_json().encode()).hexdigest(),
        letter_json=letter.model_dump_json(), blocked_reason=None,
        html="<article></article>", pdf=pdf_bytes,
        approved_by=None, approved_role=None, approved_at=None,
    )

    denial_pdf_bytes = b"%PDF-1.4 fake denial letter -- SYNTHETIC DEMO DATA"
    repo.save_document(
        document_id="denial-letter-99281", case_id="case-100028", document_type="denial-letter",
        content_type="application/pdf", content=denial_pdf_bytes,
        sha256=hashlib.sha256(denial_pdf_bytes).hexdigest(),
    )

    return pdf_bytes, denial_pdf_bytes


async def test_case_detail_includes_ready_for_review_packet_section(repo, settings, fixtures_dir):
    _seed(repo, settings)
    app = create_app(settings, _ctx(repo, settings, fixtures_dir))

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/cases/case-100028")

    assert resp.status_code == 200
    body = resp.json()

    assert body["packet"]["version"] == 1
    assert body["statusLine"] == "Ready for review"
    assert body["completenessLine"] == "Evidence completeness: 3/3 policy criteria satisfied"
    assert body["deadline"]["line"] == "Appeal deadline: October 19, 2026 (37 days left)"
    assert body["recoveryLine"] == "Expected recovery: $4,800"

    header_by_label = {field["label"]: field for field in body["packet"]["header"]}
    assert header_by_label["Hospital claim ID"]["value"] == "HSP-CLM-100028"
    assert header_by_label["Hospital claim ID"]["source"] == "remit"
    assert header_by_label["Policy"]["value"] == "NST-IMG-2026-04 v2026.04"
    assert header_by_label["Policy"]["source"] == "policy"

    citation_ids_by_statement = [statement["citationIds"] for statement in body["packet"]["statements"]]
    assert citation_ids_by_statement == [["R1-C1", "R1-C2"], ["R2-C1"], ["R3-C1"]]


async def test_packet_pdf_endpoint_returns_the_stored_pdf(repo, settings, fixtures_dir):
    pdf_bytes, _ = _seed(repo, settings)
    app = create_app(settings, _ctx(repo, settings, fixtures_dir))

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/cases/case-100028/packets/1/pdf")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content == pdf_bytes


async def test_denial_letter_document_endpoint_returns_pdf_bytes(repo, settings, fixtures_dir):
    _, denial_pdf_bytes = _seed(repo, settings)
    app = create_app(settings, _ctx(repo, settings, fixtures_dir))

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/cases/case-100028/documents/denial-letter-99281")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content == denial_pdf_bytes
