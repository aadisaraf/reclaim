"""Integration tests chaining build_matrix -> draft_packet for the hero case (T088).

pipeline.py is out of scope for this session (another agent/the orchestrator owns its wiring),
so this test chains the two step functions directly -- the same way
tests/integration/test_matrix_pipeline.py exercises build_matrix alone. After build_matrix runs,
its result is saved as the "build_matrix" step output exactly the way pipeline.run_case does
(`repo.save_step_output(case_id, "build_matrix", result.model_dump_json())`), which nests the
matrix under a "matrix" key -- draft_packet reads it back the same way.

The hero fixture values (case-100028, HSP-CLM-100028, PAYER-CLM-99281, NSTHLTH01,
MEMBER-448820, 1234567893, HC/72148, 20260810, CO-50, $4800) match
tests/integration/test_matrix_pipeline.py and tests/integration/test_gather_evidence.py so this
test composes with them.
"""

import json

from reclaim.adapters.policy import FilePolicyStore
from reclaim.adapters.protocols import PayerDecision
from reclaim.context import AppContext
from reclaim.models import (
    Citation, CitationProposal, ClaimMapEntry, EvidenceItem, EvidenceMatrix, EvidenceSet,
    LetterDraft, MatrixProposal, MatrixRow, OriginalClaim, RequirementProposal, StatementProposal,
)
from reclaim.prompts.draft_packet import build_input
from reclaim.steps.build_matrix import build_matrix
from reclaim.steps.draft_packet import draft_packet
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

HERO_CLAIM = OriginalClaim(
    hospital_claim_id="HSP-CLM-100028", billed=4800.0, frequency_code="1",
    member_id="MEMBER-448820", group_number="NST-PPO-GRP-01", payer_id="NSTHLTH01",
    billing_npi="1245319599", billing_state="WA", rendering_npi="1234567893",
    procedure_qualifier="HC", procedure_code="72148", units=1, diagnosis_code="M54.16",
    date_of_service="20260810",
)

HERO_CLAIM_MAP = ClaimMapEntry(
    patientId="patient-0042", mrn="MRN-0042", encounterId="encounter-20260810-42",
    dateOfService="2026-08-10", procedureCode="72148", diagnosisCode="M54.16",
)

HERO_DECISION = PayerDecision(
    payerClaimId="PAYER-CLM-99281", claimId="HSP-CLM-100028", decision="denied",
    decisionDate="2026-08-20", reasonCode="CO-50",
    reasonText="Insufficient documentation of medical necessity",
    appealDeadline="2026-10-19", allowedSubmissionChannels=["portal", "fax"],
    letter={"documentId": "denial-letter-99281", "url": "/api/v1/documents/denial-letter-99281"},
)


def _evidence_set() -> dict:
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
    ]
    return EvidenceSet(items=items, excluded_count=1, search_counts={}, lookback_start="2026-02-10",
                        lookback_end="2026-08-10", coverage_plan_type="Commercial PPO").model_dump()


def _seed(repo) -> None:
    repo.upsert_case(HERO_CASE["case_id"], **{k: v for k, v in HERO_CASE.items() if k != "case_id"})
    repo.save_step_output(HERO_CASE["case_id"], "gather_evidence", json.dumps({
        "evidence_set": _evidence_set(), "policy_id": "NST-IMG-2026-04", "policy_version": "2026.04",
        "appeal_window_days": 60,
    }))
    repo.save_step_output(HERO_CASE["case_id"], "fetch_claim", json.dumps({
        "original_claim": HERO_CLAIM.model_dump(),
    }))
    repo.save_step_output(HERO_CASE["case_id"], "resolve_identity", json.dumps({
        "checks": [], "claim_map_entry": HERO_CLAIM_MAP.model_dump(),
    }))
    repo.save_step_output(HERO_CASE["case_id"], "payer_context", json.dumps({
        "decision": HERO_DECISION.model_dump(), "deadline": None,
        "policy_id": "NST-IMG-2026-04", "policy_version": "2026.04",
    }))


def _ctx(repo, settings, fixtures_dir, llm_client) -> AppContext:
    return AppContext(
        repo=repo, settings=settings, remit_inbox=None, claim_archive=None, ehr_client=None,
        policy_store=FilePolicyStore(fixtures_dir / "policies"), payer_adapter=None, llm_client=llm_client,
    )


def _satisfied_matrix_proposal() -> MatrixProposal:
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


def _hero_letter_draft() -> LetterDraft:
    return LetterDraft(statements=[
        StatementProposal(
            text="The patient has a documented diagnosis of lumbar radiculopathy consistent with the imaging request.",
            requirementIds=["R1"], citationIds=["R1-C1", "R1-C2"],
        ),
        StatementProposal(
            text="The patient completed 6 weeks of supervised physical therapy without improvement.",
            requirementIds=["R2"], citationIds=["R2-C1"],
        ),
        StatementProposal(
            text="The treating clinician documented clinical rationale for ordering the MRI.",
            requirementIds=["R3"], citationIds=["R3-C1"],
        ),
    ])


async def _run_matrix_then_draft(repo, ctx, case_id: str, matrix_proposal: MatrixProposal, letter_draft: LetterDraft):
    ctx.llm_client.queue_result(matrix_proposal)
    ctx.llm_client.queue_result(letter_draft)

    matrix_result = await build_matrix(ctx, repo.get_case(case_id))
    repo.save_step_output(case_id, "build_matrix", matrix_result.model_dump_json())

    return await draft_packet(ctx, repo.get_case(case_id))


async def test_hero_case_gives_ready_for_review_packet_v1_with_two_llm_calls(repo, settings, fixtures_dir):
    _seed(repo)
    llm = FakeLlmClient()
    ctx = _ctx(repo, settings, fixtures_dir, llm)

    result = await _run_matrix_then_draft(
        repo, ctx, "case-100028", _satisfied_matrix_proposal(), _hero_letter_draft(),
    )

    assert result.blocked is False
    assert result.packet_version == 1

    assert len(llm.calls) == 2
    assert llm.calls[0]["step"] == "build_matrix"
    assert llm.calls[0]["effort"] == "medium"
    assert llm.calls[1]["step"] == "draft_packet"
    assert llm.calls[1]["effort"] == "low"

    assert repo.get_case("case-100028")["status"] == "ready-for-review"

    packet = repo.get_packet("case-100028", 1)
    assert packet["status"] == "ready-for-review"
    assert packet["pdf"] is not None

    for document_id in [
        "note-progress-031", "treatment-note-022", "order-901",
        "policy-snapshot-NST-IMG-2026-04", "appeal-letter-100028",
    ]:
        assert repo.get_document(document_id) is not None, document_id


def test_draft_packet_input_contains_only_satisfied_requirements():
    matrix = EvidenceMatrix(
        case_id="case-100028", policy_id="NST-IMG-2026-04", policy_version="2026.04",
        summary={"satisfied": 2, "total": 3},
        requirements=[
            MatrixRow(requirement_id="R1", status="satisfied", evidence=[
                Citation(citation_id="R1-C1", resource="Condition/condition-100",
                         excerpt="Lumbar radiculopathy", verified=True),
            ]),
            MatrixRow(requirement_id="R2", status="missing", reason="No evidence proposed for this requirement."),
            MatrixRow(requirement_id="R3", status="satisfied", evidence=[
                Citation(citation_id="R3-C1", resource="ServiceRequest/order-901",
                         excerpt="Ordering lumbar MRI without contrast", verified=True),
            ]),
        ],
    )

    messages = build_input(matrix, {"R1": "diagnosis text", "R2": "conservative treatment text", "R3": "rationale text"})
    content = messages[0]["content"]

    assert '"requirementId": "R1"' in content
    assert '"requirementId": "R3"' in content
    assert '"requirementId": "R2"' not in content
    assert "conservative treatment text" not in content


async def test_rerun_with_identical_draft_keeps_v1(repo, settings, fixtures_dir):
    _seed(repo)
    first_ctx = _ctx(repo, settings, fixtures_dir, FakeLlmClient())
    await _run_matrix_then_draft(repo, first_ctx, "case-100028", _satisfied_matrix_proposal(), _hero_letter_draft())

    second_ctx = _ctx(repo, settings, fixtures_dir, FakeLlmClient())
    result = await _run_matrix_then_draft(
        repo, second_ctx, "case-100028", _satisfied_matrix_proposal(), _hero_letter_draft(),
    )

    assert result.packet_version == 1
    assert result.blocked is False


async def test_rerun_with_changed_draft_creates_v2(repo, settings, fixtures_dir):
    _seed(repo)
    first_ctx = _ctx(repo, settings, fixtures_dir, FakeLlmClient())
    await _run_matrix_then_draft(repo, first_ctx, "case-100028", _satisfied_matrix_proposal(), _hero_letter_draft())

    changed_draft = LetterDraft(statements=[
        StatementProposal(
            text="A materially different statement about the lumbar radiculopathy diagnosis.",
            requirementIds=["R1"], citationIds=["R1-C1", "R1-C2"],
        ),
        StatementProposal(
            text="The patient completed 6 weeks of supervised physical therapy without improvement.",
            requirementIds=["R2"], citationIds=["R2-C1"],
        ),
        StatementProposal(
            text="The treating clinician documented clinical rationale for ordering the MRI.",
            requirementIds=["R3"], citationIds=["R3-C1"],
        ),
    ])
    second_ctx = _ctx(repo, settings, fixtures_dir, FakeLlmClient())

    result = await _run_matrix_then_draft(
        repo, second_ctx, "case-100028", _satisfied_matrix_proposal(), changed_draft,
    )

    assert result.packet_version == 2
    assert result.blocked is False
    assert repo.get_case("case-100028")["status"] == "ready-for-review"


async def test_uncited_statement_blocks_packet_and_case_stays_evidence_gathered(repo, settings, fixtures_dir):
    _seed(repo)
    ctx = _ctx(repo, settings, fixtures_dir, FakeLlmClient())

    bad_draft = LetterDraft(statements=[
        StatementProposal(text="An uncited claim about the patient's diagnosis.", requirementIds=["R1"], citationIds=[]),
        StatementProposal(
            text="The patient completed 6 weeks of supervised physical therapy without improvement.",
            requirementIds=["R2"], citationIds=["R2-C1"],
        ),
        StatementProposal(
            text="The treating clinician documented clinical rationale for ordering the MRI.",
            requirementIds=["R3"], citationIds=["R3-C1"],
        ),
    ])

    result = await _run_matrix_then_draft(repo, ctx, "case-100028", _satisfied_matrix_proposal(), bad_draft)

    assert result.blocked is True
    packet = repo.get_packet("case-100028", result.packet_version)
    assert packet["status"] == "blocked"
    assert "An uncited claim about the patient's diagnosis." in packet["blocked_reason"]
    assert repo.get_case("case-100028")["status"] == "evidence-gathered"
