"""Contract test for the fuller GET /api/cases/{caseId} assembly: evidence, policy, payerDecision,
deadline, matrix, completenessLine, recoveryLine, and aiCost, for the hero case (case-100028).

Not assigned a dedicated test file in tasks.md at this phase (that arrives in Phase 7); written
here for real TDD coverage of src/reclaim/api.py's case-detail assembly, reusing the hero-case
fixture pattern from tests/integration/test_matrix_pipeline.py and tests/integration/test_gather_evidence.py.
All values are hand-copied from docs/reclaim-speckit-prompts.md Appendix A (A5-A8) and
specs/001-denial-recovery/data-model.md, not derived by running the pipeline steps.
"""

import json

import httpx

from reclaim.context import AppContext
from reclaim.main import create_app

HERO_CASE = dict(
    case_id="case-100028", hospital_claim_id="HSP-CLM-100028", lane="medical-necessity",
    status="evidence-gathered", payer_claim_id="PAYER-CLM-99281", payer="Northstar Health",
    payer_id="NSTHLTH01", member_id="MEMBER-448820", rendering_npi="1234567893",
    procedure_qualifier="HC", procedure_code="72148", date_of_service="20260810",
    denial_code="CO-50", denial_reason="Medical necessity", billed_amount=4800.0, paid_amount=0.0,
    denied_amount=4800.0, running=0, needs_review_field=None, last_error=None,
)

# Appendix A5: 8 included items (Coverage, Condition, ServiceRequest, Procedure, DiagnosticReport,
# Observation, and 2 in-window DocumentReferences) plus 1 excluded (outside the 6-month lookback).
EVIDENCE_SET = {
    "items": [
        {"resource": "Coverage/coverage-0042", "resource_type": "Coverage", "date": None,
         "source_url": "Coverage/coverage-0042", "included": True, "exclusion_reason": None,
         "summary": "Commercial PPO", "document": None, "text": None, "raw": {}},
        {"resource": "Condition/condition-100", "resource_type": "Condition", "date": "2026-05-28",
         "source_url": "Condition/condition-100", "included": True, "exclusion_reason": None,
         "summary": "", "document": None, "text": None, "raw": {}},
        {"resource": "ServiceRequest/order-901", "resource_type": "ServiceRequest", "date": "2026-08-10",
         "source_url": "ServiceRequest/order-901", "included": True, "exclusion_reason": None,
         "summary": "", "document": None, "text": None, "raw": {}},
        {"resource": "Procedure/procedure-902", "resource_type": "Procedure", "date": "2026-08-10",
         "source_url": "Procedure/procedure-902", "included": True, "exclusion_reason": None,
         "summary": "", "document": None, "text": None, "raw": {}},
        {"resource": "DiagnosticReport/report-xr-555", "resource_type": "DiagnosticReport", "date": "2026-05-28",
         "source_url": "DiagnosticReport/report-xr-555", "included": True, "exclusion_reason": None,
         "summary": "", "document": None, "text": None, "raw": {}},
        {"resource": "Observation/obs-pain-7781", "resource_type": "Observation", "date": "2026-08-10",
         "source_url": "Observation/obs-pain-7781", "included": True, "exclusion_reason": None,
         "summary": "", "document": None, "text": None, "raw": {}},
        {"resource": "DocumentReference/note-progress-031", "resource_type": "DocumentReference",
         "date": "2026-08-10", "source_url": "DocumentReference/note-progress-031", "included": True,
         "exclusion_reason": None, "summary": "", "document": "Binary/note-progress-031",
         "text": "Assessment: Findings are consistent with lumbar radiculopathy.", "raw": {}},
        {"resource": "DocumentReference/treatment-note-022", "resource_type": "DocumentReference",
         "date": "2026-07-14", "source_url": "DocumentReference/treatment-note-022", "included": True,
         "exclusion_reason": None, "summary": "", "document": "Binary/treatment-note-022",
         "text": "Patient completed 6 weeks of supervised physical therapy for low back pain.", "raw": {}},
        {"resource": "DocumentReference/note-ortho-2019-004", "resource_type": "DocumentReference",
         "date": "2019-03-02", "source_url": "DocumentReference/note-ortho-2019-004", "included": False,
         "exclusion_reason": "outside 6-month lookback", "summary": "",
         "document": "Binary/note-ortho-2019-004",
         "text": "SYNTHETIC DEMO DATA - unrelated 2019 ankle sprain visit note.", "raw": {}},
    ],
    "excluded_count": 1,
    "search_counts": {
        "Coverage": 1, "Condition": 1, "ServiceRequest": 1, "Procedure": 1,
        "DiagnosticReport": 1, "Observation": 1, "DocumentReference": 3, "MedicationRequest": 0,
    },
    "lookback_start": "2026-02-10", "lookback_end": "2026-08-10", "coverage_plan_type": "Commercial PPO",
}

# Appendix A6 decision JSON, verbatim.
PAYER_DECISION = {
    "payerClaimId": "PAYER-CLM-99281", "claimId": "HSP-CLM-100028", "decision": "denied",
    "decisionDate": "2026-08-20", "reasonCode": "CO-50",
    "reasonText": "Insufficient documentation of medical necessity",
    "appealDeadline": "2026-10-19", "allowedSubmissionChannels": ["portal", "fax"],
    "letter": {"documentId": "denial-letter-99281", "url": "/api/v1/documents/denial-letter-99281"},
}

# data-model.md §4: decisionDate 2026-08-20 + 60-day window = 2026-10-19 = the payer deadline, so
# no warning; DEMO_TODAY 2026-09-12 to 2026-10-19 is 37 days.
DEADLINE = {"deadline_of_record": "2026-10-19", "policy_window_date": "2026-10-19", "days_left": 37, "warning": None}

# Appendix A8 happy-path matrix, hand-copied (citation ids assigned per requirement).
MATRIX = {
    "case_id": "case-100028", "policy_id": "NST-IMG-2026-04", "policy_version": "2026.04",
    "summary": {"satisfied": 3, "total": 3},
    "requirements": [
        {
            "requirement_id": "R1", "status": "satisfied", "reason": None,
            "evidence": [
                {"citation_id": "R1-C1", "resource": "Condition/condition-100", "document": None,
                 "date": "2026-05-28", "excerpt": "Lumbar radiculopathy", "verified": True,
                 "rejection_reason": None},
                {"citation_id": "R1-C2", "resource": "DocumentReference/note-progress-031",
                 "document": "Binary/note-progress-031", "date": "2026-08-10",
                 "excerpt": "consistent with lumbar radiculopathy", "verified": True,
                 "rejection_reason": None},
            ],
        },
        {
            "requirement_id": "R2", "status": "satisfied", "reason": None,
            "evidence": [
                {"citation_id": "R2-C1", "resource": "DocumentReference/treatment-note-022",
                 "document": "Binary/treatment-note-022", "date": "2026-07-14",
                 "excerpt": "6 weeks of supervised physical therapy", "verified": True,
                 "rejection_reason": None},
            ],
        },
        {
            "requirement_id": "R3", "status": "satisfied", "reason": None,
            "evidence": [
                {"citation_id": "R3-C1", "resource": "ServiceRequest/order-901", "document": None,
                 "date": "2026-08-10",
                 "excerpt": "Ordering lumbar MRI without contrast given radiating left leg pain",
                 "verified": True, "rejection_reason": None},
            ],
        },
    ],
}

# Hand-picked usage numbers; expected cost is computed by hand below using the documented formula
# (input-cached)*price_input + cached*price_cached + output*price_output, per-million tokens.
LLM_USAGE_CALL = {"input_tokens": 1000, "cached_tokens": 200, "output_tokens": 300, "reasoning_tokens": 50}


def _ctx(repo, settings, fixtures_dir) -> AppContext:
    from reclaim.adapters.policy import FilePolicyStore

    return AppContext(
        repo=repo, settings=settings, remit_inbox=None, claim_archive=None, ehr_client=None,
        policy_store=FilePolicyStore(fixtures_dir / "policies"), payer_adapter=None, llm_client=None,
    )


def _seed(repo, settings) -> None:
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
    repo.insert_audit_event(
        "case-100028", "build_matrix", "Evidence matrix: 3/3 satisfied", None, [],
        {"calls": [LLM_USAGE_CALL]},
    )


async def test_case_detail_full_assembly_for_hero_case(repo, settings, fixtures_dir):
    _seed(repo, settings)
    app = create_app(settings, _ctx(repo, settings, fixtures_dir))

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/cases/case-100028")

    assert resp.status_code == 200
    body = resp.json()

    assert body["statusLine"] == "Evidence gathered"

    assert len(body["evidence"]["items"]) == 9
    assert body["evidence"]["excludedLine"] == "1 record excluded (outside 6-month lookback)"
    assert body["evidence"]["searchCounts"]["MedicationRequest"] == 0

    assert body["policy"]["label"] == "Policy NST-IMG-2026-04 v2026.04"
    assert body["policy"]["title"] == "Advanced imaging of the lumbar spine (SYNTHETIC)"

    assert body["payerDecision"]["decision"] == "denied"
    assert body["payerDecision"]["reasonCode"] == "CO-50"
    assert body["payerDecision"]["appealDeadline"] == "2026-10-19"

    assert body["deadline"]["line"] == "Appeal deadline: October 19, 2026 (37 days left)"
    assert body["deadline"]["warning"] is None

    assert body["matrix"]["summary"] == {"satisfied": 3, "total": 3}
    assert body["completenessLine"] == "Evidence completeness: 3/3 policy criteria satisfied"

    assert body["recoveryLine"] == "Expected recovery: $4,800"

    assert body["aiCost"]["inputTokens"] == 1000
    assert body["aiCost"]["cachedTokens"] == 200
    assert body["aiCost"]["outputTokens"] == 300
    assert body["aiCost"]["reasoningTokens"] == 50
    # (1000-200)*0.20/1e6 + 200*0.02/1e6 + 300*1.20/1e6 = 0.00016 + 0.000004 + 0.00036 = 0.000524
    assert body["aiCost"]["usd"] == 0.0005
    assert body["aiCost"]["line"] == "AI cost for this case (estimate): $0.0005"

    assert body["needsLine"] is None
    assert body["tasks"] == []
    assert body["packet"] is None
    assert body["submission"] is None
    assert body["actions"]["canApprove"] is False
