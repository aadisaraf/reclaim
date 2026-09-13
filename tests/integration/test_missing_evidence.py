"""T107: end-to-end missing-evidence mode (US7), mirroring tests/integration/test_matrix_pipeline.py's
HERO_CASE/_evidence_set/_seed/_ctx helpers and its `test_r2_missing_gives_needs_evidence_with_one_call`
proposal, extended to cover task creation, the GET /api/cases/{caseId} view, re-run keep/close
semantics, and the 409 rerun-unavailable path for a submitted case (data-model.md §6, A9 step 7).
"""

import json

import httpx

from reclaim.adapters.policy import FilePolicyStore
from reclaim.context import AppContext
from reclaim.main import create_app
from reclaim.models import CitationProposal, EvidenceItem, EvidenceSet, MatrixProposal, RequirementProposal
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

R2_MISSING_REASON = (
    "No DocumentReference or MedicationRequest in the lookback window documents a "
    "6-week conservative treatment trial"
)
R2_QUESTION = (
    "The policy requires documentation of prior conservative treatment. "
    "Please identify the relevant note or provide a factual attestation."
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


def _ctx(repo, settings, fixtures_dir, llm_client) -> AppContext:
    return AppContext(
        repo=repo, settings=settings, remit_inbox=None, claim_archive=None, ehr_client=None,
        policy_store=FilePolicyStore(fixtures_dir / "policies"), payer_adapter=None, llm_client=llm_client,
    )


def _missing_r2_proposal() -> MatrixProposal:
    return MatrixProposal(requirements=[
        RequirementProposal(requirementId="R1", status="satisfied", citations=[
            CitationProposal(resource="Condition/condition-100", excerpt="Lumbar radiculopathy"),
        ]),
        RequirementProposal(requirementId="R2", status="missing", reason=R2_MISSING_REASON),
        RequirementProposal(requirementId="R3", status="satisfied", citations=[
            CitationProposal(resource="ServiceRequest/order-901",
                              excerpt="Ordering lumbar MRI without contrast given radiating left leg pain"),
        ]),
    ])


def _satisfied_proposal() -> MatrixProposal:
    return MatrixProposal(requirements=[
        RequirementProposal(requirementId="R1", status="satisfied", citations=[
            CitationProposal(resource="Condition/condition-100", excerpt="Lumbar radiculopathy"),
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


async def test_r2_missing_creates_one_task_blocks_approval_and_shows_needs_line(repo, settings, fixtures_dir):
    _seed(repo)
    llm = FakeLlmClient()
    llm.queue_result(_missing_r2_proposal())
    ctx = _ctx(repo, settings, fixtures_dir, llm)

    result = await build_matrix(ctx, repo.get_case("case-100028"))

    assert len(llm.calls) == 1
    assert result.matrix.summary == {"satisfied": 2, "total": 3}
    assert repo.get_case("case-100028")["status"] == "needs-evidence"

    r2_row = next(r for r in result.matrix.requirements if r.requirement_id == "R2")
    assert r2_row.status == "missing"
    assert r2_row.reason == R2_MISSING_REASON

    tasks = repo.list_tasks("case-100028")
    assert len(tasks) == 1
    task = tasks[0]
    assert task["task_id"] == "task-case-100028-R2"
    assert task["task_type"] == "clinical-evidence-request"
    assert task["assignee_role"] == "treating-clinician"
    assert task["question"] == R2_QUESTION
    assert task["status"] == "open"

    app = create_app(settings, ctx)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/cases/case-100028")

    assert resp.status_code == 200
    body = resp.json()
    assert body["packet"] is None
    assert body["actions"]["canApprove"] is False
    assert body["needsLine"] == "Needs 1 item"
    assert len(body["tasks"]) == 1
    api_task = body["tasks"][0]
    assert api_task["taskId"] == "task-case-100028-R2"
    assert api_task["taskType"] == "clinical-evidence-request"
    assert api_task["requirementId"] == "R2"
    assert api_task["assigneeRole"] == "treating-clinician"
    assert api_task["question"] == R2_QUESTION
    assert api_task["status"] == "open"
    assert api_task["closeNote"] is None


async def test_rerun_with_toggle_still_on_keeps_a_single_open_task(repo, settings, fixtures_dir):
    _seed(repo)
    llm1 = FakeLlmClient()
    llm1.queue_result(_missing_r2_proposal())
    ctx1 = _ctx(repo, settings, fixtures_dir, llm1)
    await build_matrix(ctx1, repo.get_case("case-100028"))

    first_task = repo.list_tasks("case-100028")[0]

    llm2 = FakeLlmClient()
    llm2.queue_result(_missing_r2_proposal())
    ctx2 = _ctx(repo, settings, fixtures_dir, llm2)
    await build_matrix(ctx2, repo.get_case("case-100028"))

    tasks = repo.list_tasks("case-100028")
    assert len(tasks) == 1
    assert tasks[0]["task_id"] == "task-case-100028-R2"
    assert tasks[0]["status"] == "open"
    assert tasks[0]["created_at"] == first_task["created_at"]


async def test_toggle_off_and_rerun_closes_the_task(repo, settings, fixtures_dir):
    _seed(repo)
    llm1 = FakeLlmClient()
    llm1.queue_result(_missing_r2_proposal())
    ctx1 = _ctx(repo, settings, fixtures_dir, llm1)
    await build_matrix(ctx1, repo.get_case("case-100028"))

    llm2 = FakeLlmClient()
    llm2.queue_result(_satisfied_proposal())
    ctx2 = _ctx(repo, settings, fixtures_dir, llm2)
    result = await build_matrix(ctx2, repo.get_case("case-100028"))

    assert result.matrix.summary == {"satisfied": 3, "total": 3}

    tasks = repo.list_tasks("case-100028")
    assert len(tasks) == 1
    assert tasks[0]["status"] == "closed"
    assert tasks[0]["close_note"] == "Requirement R2 is now satisfied by a verified citation."

    # NOTE: build_matrix only ever *sets* status to "needs-evidence" on a missing row; it never
    # clears it back once requirements are fully satisfied again -- that final "ready-for-review"
    # transition happens in draft_packet as part of the full run_case/rerun_case pipeline (which
    # this test does not exercise, since it drives build_matrix directly per the task brief). So
    # the case status observed here after a direct re-run is still "needs-evidence", even though
    # the task itself is correctly closed.
    assert repo.get_case("case-100028")["status"] == "needs-evidence"


async def test_rerun_on_submitted_case_returns_409_and_leaves_submission_unchanged(repo, settings, fixtures_dir):
    _seed(repo)
    repo.update_case("case-100028", status="submitted")
    repo.save_submission(
        "appeal-case-100028-v1", case_id="case-100028", version=1, request_sha256="a" * 64,
        status="confirmed", appeal_id="APL-9001", received_at="2026-09-01T00:00:00Z",
        expected_resolution_days=14, payer_status="received", error_code=None, error_message=None,
    )
    submission_before = repo.get_submission("appeal-case-100028-v1")

    ctx = _ctx(repo, settings, fixtures_dir, FakeLlmClient())
    app = create_app(settings, ctx)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/cases/case-100028/rerun")

    assert resp.status_code == 409
    assert resp.json() == {
        "error": {
            "code": "rerun_unavailable",
            "message": "A submitted appeal cannot be re-run. Reset the demo first.",
        }
    }
    assert repo.get_case("case-100028")["status"] == "submitted"
    assert repo.get_submission("appeal-case-100028-v1") == submission_before
