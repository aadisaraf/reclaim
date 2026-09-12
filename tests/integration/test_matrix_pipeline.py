import json

from reclaim.adapters.policy import FilePolicyStore
from reclaim.context import AppContext
from reclaim.models import CitationProposal, MatrixProposal, RequirementProposal
from reclaim.steps.build_matrix import build_matrix
from tests.fakes import FakeLlmClient

HERO_CASE = dict(
    case_id="case-100028", hospital_claim_id="HSP-CLM-100028", lane="medical-necessity",
    status="evidence-gathered", payer_claim_id="PAYER-CLM-99281", payer="Northstar Health",
    payer_id="NSTHLTH01", member_id="MEMBER-448820", rendering_npi="1234567893",
    procedure_qualifier="HC", procedure_code="72148", date_of_service="20260810",
    denial_code="CO-50", denial_reason="Medical necessity", billed_amount=4800.0, paid_amount=0.0,
    denied_amount=4800.0,
)

CONDITION_100 = {"resourceType": "Condition", "id": "condition-100", "code": {"text": "Lumbar radiculopathy"}}
ORDER_901 = {
    "resourceType": "ServiceRequest", "id": "order-901",
    "note": [{"text": "Ordering lumbar MRI without contrast given radiating left leg pain"}],
}
PROGRESS_NOTE_TEXT = (
    "Assessment: Findings are consistent with lumbar radiculopathy, most likely related to nerve root compression."
)
TREATMENT_NOTE_TEXT = "Patient completed 6 weeks of supervised physical therapy for low back pain."
ORTHO_NOTE_TEXT = "SYNTHETIC DEMO DATA - unrelated 2019 ankle sprain visit note."


def _evidence_set() -> dict:
    from reclaim.models import EvidenceItem, EvidenceSet

    items = [
        EvidenceItem(resource="Coverage/coverage-0042", resource_type="Coverage", date=None,
                     source_url="Coverage/coverage-0042", included=True, summary="Commercial PPO"),
        EvidenceItem(resource="Condition/condition-100", resource_type="Condition", date="2026-05-28",
                     source_url="Condition/condition-100", included=True, raw=CONDITION_100),
        EvidenceItem(resource="DocumentReference/note-progress-031", resource_type="DocumentReference",
                     date="2026-08-10", source_url="DocumentReference/note-progress-031", included=True,
                     document="Binary/note-progress-031", text=PROGRESS_NOTE_TEXT),
        EvidenceItem(resource="DocumentReference/treatment-note-022", resource_type="DocumentReference",
                     date="2026-07-14", source_url="DocumentReference/treatment-note-022", included=True,
                     document="Binary/treatment-note-022", text=TREATMENT_NOTE_TEXT),
        EvidenceItem(resource="ServiceRequest/order-901", resource_type="ServiceRequest", date="2026-08-10",
                     source_url="ServiceRequest/order-901", included=True, raw=ORDER_901),
        EvidenceItem(resource="DocumentReference/note-ortho-2019-004", resource_type="DocumentReference",
                     date="2019-03-02", source_url="DocumentReference/note-ortho-2019-004", included=False,
                     exclusion_reason="outside 6-month lookback", document="Binary/note-ortho-2019-004",
                     text=ORTHO_NOTE_TEXT),
    ]
    return EvidenceSet(items=items, excluded_count=1, search_counts={}, lookback_start="2026-02-10",
                        lookback_end="2026-08-10", coverage_plan_type="Commercial PPO").model_dump()


def _seed(repo):
    repo.upsert_case(HERO_CASE["case_id"], **{k: v for k, v in HERO_CASE.items() if k != "case_id"})
    repo.save_step_output("case-100028", "gather_evidence", json.dumps({
        "evidence_set": _evidence_set(), "policy_id": "NST-IMG-2026-04", "policy_version": "2026.04",
        "appeal_window_days": 60,
    }))


def _ctx(repo, settings, fixtures_dir, llm_client):
    return AppContext(
        repo=repo, settings=settings, remit_inbox=None, claim_archive=None, ehr_client=None,
        policy_store=FilePolicyStore(fixtures_dir / "policies"), payer_adapter=None, llm_client=llm_client,
    )


def _satisfied_proposal() -> MatrixProposal:
    return MatrixProposal(requirements=[
        RequirementProposal(requirementId="R1", status="satisfied", citations=[
            CitationProposal(resource="Condition/condition-100", excerpt="Lumbar radiculopathy"),
            CitationProposal(resource="DocumentReference/note-progress-031",
                              excerpt="consistent with lumbar radiculopathy"),
        ]),
        RequirementProposal(requirementId="R2", status="satisfied", citations=[
            CitationProposal(resource="DocumentReference/treatment-note-022",
                              excerpt="6 weeks of supervised physical therapy"),
        ]),
        RequirementProposal(requirementId="R3", status="satisfied", citations=[
            CitationProposal(resource="ServiceRequest/order-901",
                              excerpt="Ordering lumbar MRI without contrast given radiating left leg pain"),
        ]),
    ])


async def test_hero_case_gives_3_of_3_with_one_call(repo, settings, fixtures_dir):
    _seed(repo)
    llm = FakeLlmClient()
    llm.queue_result(_satisfied_proposal())
    ctx = _ctx(repo, settings, fixtures_dir, llm)

    result = await build_matrix(ctx, repo.get_case("case-100028"))

    assert result.matrix.summary == {"satisfied": 3, "total": 3}
    assert len(llm.calls) == 1
    assert llm.calls[0]["effort"] == settings.effort_build_matrix
    first_call_input = llm.calls[0]["input"]
    assert "NST-IMG-2026-04" in first_call_input[0]["content"]
    assert "note-progress-031" in first_call_input[-1]["content"]
    assert "note-ortho-2019-004" not in json.dumps(first_call_input)
    assert repo.get_case("case-100028")["status"] == "evidence-gathered"


async def test_forged_citation_triggers_retry_at_high_effort(repo, settings, fixtures_dir):
    _seed(repo)
    llm = FakeLlmClient()
    forged_proposal = MatrixProposal(requirements=[
        RequirementProposal(requirementId="R1", status="satisfied", citations=[
            CitationProposal(resource="DocumentReference/note-fake-999", excerpt="fabricated evidence text"),
        ]),
        RequirementProposal(requirementId="R2", status="satisfied", citations=[
            CitationProposal(resource="DocumentReference/treatment-note-022",
                              excerpt="6 weeks of supervised physical therapy"),
        ]),
        RequirementProposal(requirementId="R3", status="satisfied", citations=[
            CitationProposal(resource="ServiceRequest/order-901",
                              excerpt="Ordering lumbar MRI without contrast given radiating left leg pain"),
        ]),
    ])
    llm.queue_result(forged_proposal)
    llm.queue_result(_satisfied_proposal())
    ctx = _ctx(repo, settings, fixtures_dir, llm)

    result = await build_matrix(ctx, repo.get_case("case-100028"))

    assert len(llm.calls) == 2
    assert llm.calls[1]["effort"] == "high"
    assert "not fetched for this case" in llm.calls[1]["input"][-1]["content"]
    assert result.matrix.summary == {"satisfied": 3, "total": 3}


async def test_r2_missing_gives_needs_evidence_with_one_call(repo, settings, fixtures_dir):
    _seed(repo)
    llm = FakeLlmClient()
    proposal = MatrixProposal(requirements=[
        RequirementProposal(requirementId="R1", status="satisfied", citations=[
            CitationProposal(resource="Condition/condition-100", excerpt="Lumbar radiculopathy"),
        ]),
        RequirementProposal(
            requirementId="R2", status="missing",
            reason="No DocumentReference or MedicationRequest in the lookback window documents a "
                    "6-week conservative treatment trial",
        ),
        RequirementProposal(requirementId="R3", status="satisfied", citations=[
            CitationProposal(resource="ServiceRequest/order-901",
                              excerpt="Ordering lumbar MRI without contrast given radiating left leg pain"),
        ]),
    ])
    llm.queue_result(proposal)
    ctx = _ctx(repo, settings, fixtures_dir, llm)

    result = await build_matrix(ctx, repo.get_case("case-100028"))

    assert len(llm.calls) == 1
    assert result.matrix.summary == {"satisfied": 2, "total": 3}
    assert repo.get_case("case-100028")["status"] == "needs-evidence"
