import json

from reclaim.context import AppContext
from reclaim.steps.payer_context import payer_context

HERO_CASE = dict(
    case_id="case-100028", hospital_claim_id="HSP-CLM-100028", lane="medical-necessity",
    status="evidence-gathered", payer_claim_id="PAYER-CLM-99281", payer="Northstar Health",
    payer_id="NSTHLTH01", member_id="MEMBER-448820", rendering_npi="1234567893",
    procedure_qualifier="HC", procedure_code="72148", date_of_service="20260810",
    denial_code="CO-50", denial_reason="Medical necessity", billed_amount=4800.0, paid_amount=0.0,
    denied_amount=4800.0,
)


def _ctx(repo, settings, fixture_payer_adapter):
    return AppContext(
        repo=repo, settings=settings, remit_inbox=None, claim_archive=None,
        ehr_client=None, policy_store=None, payer_adapter=fixture_payer_adapter, llm_client=None,
    )


async def test_hero_case_gets_decision_and_deadline(repo, settings, fixture_payer_adapter):
    repo.upsert_case(HERO_CASE["case_id"], **{k: v for k, v in HERO_CASE.items() if k != "case_id"})
    repo.save_step_output(
        "case-100028", "gather_evidence",
        json.dumps({"policy_id": "NST-IMG-2026-04", "policy_version": "2026.04", "appeal_window_days": 60}),
    )
    ctx = _ctx(repo, settings, fixture_payer_adapter)

    result = await payer_context(ctx, repo.get_case("case-100028"))

    assert result.decision.decision == "denied"
    assert result.decision.decisionDate == "2026-08-20"
    assert result.decision.reasonCode == "CO-50"
    assert result.decision.reasonText == "Insufficient documentation of medical necessity"
    assert result.decision.allowedSubmissionChannels == ["portal", "fax"]
    assert result.deadline.deadline_of_record == "2026-10-19"
    assert result.deadline.warning is None
    assert result.policy_id == "NST-IMG-2026-04"

    doc = repo.get_document("denial-letter-99281")
    assert doc is not None
    assert doc["document_type"] == "denial-letter"
    assert repo.get_case("case-100028")["status"] == "evidence-gathered"


async def test_unknown_payer_claim_id_needs_review(repo, settings, fixture_payer_adapter):
    repo.upsert_case(
        "case-100028",
        **{**{k: v for k, v in HERO_CASE.items() if k != "case_id"}, "payer_claim_id": "PAYER-CLM-UNKNOWN"},
    )
    repo.save_step_output(
        "case-100028", "gather_evidence",
        json.dumps({"policy_id": "NST-IMG-2026-04", "policy_version": "2026.04", "appeal_window_days": 60}),
    )
    ctx = _ctx(repo, settings, fixture_payer_adapter)

    await payer_context(ctx, repo.get_case("case-100028"))

    case = repo.get_case("case-100028")
    assert case["status"] == "needs-review"
    assert case["needs_review_field"] == "payerClaimId"
