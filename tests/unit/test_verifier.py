import json

import pytest

from reclaim.models import CitationProposal, EvidenceItem, EvidenceSet, MatrixProposal, Policy, RequirementProposal
from reclaim.verify import verify_matrix

CONDITION_100 = {
    "resourceType": "Condition", "id": "condition-100",
    "code": {"text": "Lumbar radiculopathy"}, "onsetDateTime": "2026-05-20", "recordedDate": "2026-05-28",
}
ORDER_901 = {
    "resourceType": "ServiceRequest", "id": "order-901",
    "note": [{"text": "Ordering lumbar MRI without contrast given radiating left leg pain"}],
}
OBS_PAIN = {"resourceType": "Observation", "id": "obs-pain-7781", "valueQuantity": {"value": 8}}

PROGRESS_NOTE_TEXT = (
    "Assessment: Findings are consistent with lumbar radiculopathy, most likely related to nerve root compression."
)
TREATMENT_NOTE_TEXT = "Patient completed 6 weeks of supervised physical therapy for low back pain."
ORTHO_NOTE_TEXT = "Chief complaint: Right ankle pain after a twisting injury during recreational activity."


@pytest.fixture
def policy(fixtures_dir):
    return Policy.model_validate_json((fixtures_dir / "policies" / "NST-IMG-2026-04.json").read_text())


@pytest.fixture
def evidence_set():
    items = [
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
        EvidenceItem(resource="Observation/obs-pain-7781", resource_type="Observation", date="2026-08-10",
                     source_url="Observation/obs-pain-7781", included=True, raw=OBS_PAIN),
        EvidenceItem(resource="DocumentReference/note-ortho-2019-004", resource_type="DocumentReference",
                     date="2019-03-02", source_url="DocumentReference/note-ortho-2019-004", included=False,
                     exclusion_reason="outside 6-month lookback", document="Binary/note-ortho-2019-004",
                     text=ORTHO_NOTE_TEXT),
    ]
    return EvidenceSet(items=items, excluded_count=1, search_counts={}, lookback_start="2026-02-10",
                        lookback_end="2026-08-10", coverage_plan_type="Commercial PPO")


def _proposal(*entries: RequirementProposal) -> MatrixProposal:
    return MatrixProposal(requirements=list(entries))


def test_hero_citations_verify(evidence_set, policy):
    proposal = _proposal(
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
    )

    matrix, rejections = verify_matrix(proposal, evidence_set, policy)

    assert matrix.summary == {"satisfied": 3, "total": 3}
    assert rejections == []
    assert [r.status for r in matrix.requirements] == ["satisfied", "satisfied", "satisfied"]
    r1 = next(r for r in matrix.requirements if r.requirement_id == "R1")
    assert [c.citation_id for c in r1.evidence] == ["R1-C1", "R1-C2"]
    assert all(c.verified for c in r1.evidence)


def test_forged_resource_rejected_and_row_missing(evidence_set, policy):
    proposal = _proposal(RequirementProposal(requirementId="R1", status="satisfied", citations=[
        CitationProposal(resource="DocumentReference/note-fake-999", excerpt="fabricated evidence text"),
    ]))

    matrix, rejections = verify_matrix(proposal, evidence_set, policy)

    assert [r.model_dump() for r in rejections] == [
        {"requirement_id": "R1", "resource": "DocumentReference/note-fake-999",
         "excerpt": "fabricated evidence text", "reason": "not fetched for this case"}
    ]
    r1 = next(r for r in matrix.requirements if r.requirement_id == "R1")
    assert r1.status == "missing"
    assert r1.reason.startswith("All proposed citations failed verification:")
    assert "not fetched for this case" in r1.reason


def test_paraphrased_excerpt_rejected(evidence_set, policy):
    proposal = _proposal(RequirementProposal(requirementId="R1", status="satisfied", citations=[
        CitationProposal(resource="Condition/condition-100", excerpt="Lumbar nerve root issue"),
    ]))

    _, rejections = verify_matrix(proposal, evidence_set, policy)

    assert rejections[0].reason == "excerpt not found verbatim"


def test_outside_lookback_rejected(evidence_set, policy):
    proposal = _proposal(RequirementProposal(requirementId="R1", status="satisfied", citations=[
        CitationProposal(resource="DocumentReference/note-ortho-2019-004", excerpt="Right ankle pain after"),
    ]))

    _, rejections = verify_matrix(proposal, evidence_set, policy)

    assert rejections[0].reason == "outside lookback"


def test_wrong_type_rejected(evidence_set, policy):
    proposal = _proposal(RequirementProposal(requirementId="R1", status="satisfied", citations=[
        CitationProposal(resource="Observation/obs-pain-7781", excerpt="irrelevant pain score value"),
    ]))

    _, rejections = verify_matrix(proposal, evidence_set, policy)

    assert rejections[0].reason == "type not allowed"


def test_short_excerpt_rejected(evidence_set, policy):
    proposal = _proposal(RequirementProposal(requirementId="R1", status="satisfied", citations=[
        CitationProposal(resource="Condition/condition-100", excerpt="Lumbar radi"),
    ]))

    _, rejections = verify_matrix(proposal, evidence_set, policy)

    assert rejections[0].reason == "excerpt too short"


def test_proposal_omitting_requirement_yields_missing_row(evidence_set, policy):
    proposal = _proposal(
        RequirementProposal(requirementId="R1", status="satisfied", citations=[
            CitationProposal(resource="Condition/condition-100", excerpt="Lumbar radiculopathy"),
        ]),
        RequirementProposal(requirementId="R2", status="satisfied", citations=[
            CitationProposal(resource="DocumentReference/treatment-note-022",
                              excerpt="6 weeks of supervised physical therapy"),
        ]),
    )

    matrix, _ = verify_matrix(proposal, evidence_set, policy)

    r3 = next(r for r in matrix.requirements if r.requirement_id == "R3")
    assert r3.status == "missing"
    assert matrix.summary == {"satisfied": 2, "total": 3}


def test_duplicate_requirement_raises(evidence_set, policy):
    proposal = _proposal(
        RequirementProposal(requirementId="R1", status="satisfied", citations=[]),
        RequirementProposal(requirementId="R1", status="missing", reason="dup"),
    )

    with pytest.raises(ValueError):
        verify_matrix(proposal, evidence_set, policy)
