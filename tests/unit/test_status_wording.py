"""T121: FR-032 wording guard. The case-detail JSON built by `src/reclaim/api.py`'s
`get_case_detail` must never claim a case was "filed"/"Submitted"/"submitted"/"won" unless the
case has genuinely reached that point -- checked here for every status from `new` up through
`approved` (i.e. before an appeal has actually gone anywhere), and for a case whose one
submission attempt came back `refused` by the payer."""

import json

import pytest

from reclaim.api import STATUS_LINES, get_case_detail
from reclaim.context import AppContext
from reclaim.models import HeaderField, Letter, LetterStatement

# STATUS_LINES iteration order is new -> claim-matched -> needs-review -> evidence-gathered ->
# needs-evidence -> ready-for-review -> approved -> submitted -> ... ; take everything up to and
# including "approved" (the statuses that exist before any appeal submission attempt).
_ALL_STATUSES = list(STATUS_LINES.keys())
STATUSES_NEW_TO_APPROVED = _ALL_STATUSES[: _ALL_STATUSES.index("approved") + 1]

FORBIDDEN_SUBSTRINGS = ["filed", "Submitted", "submitted", "won"]

CASE_FIELDS = dict(
    hospital_claim_id="HSP-CLM-100028", lane="medical-necessity",
    payer_claim_id="PAYER-CLM-99281", payer="Northstar Health", payer_id="NSTHLTH01",
    member_id="MEMBER-448820", rendering_npi="1234567893", procedure_qualifier="HC",
    procedure_code="72148", date_of_service="20260810", denial_code="CO-50",
    denial_reason="Medical necessity", billed_amount=4800.0, paid_amount=0.0, denied_amount=4800.0,
)


def _ctx(repo, settings):
    return AppContext(
        repo=repo, settings=settings, remit_inbox=None, claim_archive=None, ehr_client=None,
        policy_store=None, payer_adapter=None, llm_client=None,
    )


def _assert_no_forbidden_wording(body: dict):
    # The `status` field of `case` is allowed to legitimately hold the literal value
    # "submitted" (only relevant outside this new..approved sweep, but guarded here too) --
    # everything else in the payload must be clean.
    scrubbed = json.loads(json.dumps(body))
    scrubbed["case"]["status"] = "<status>"
    dumped = json.dumps(scrubbed)
    for forbidden in FORBIDDEN_SUBSTRINGS:
        assert forbidden not in dumped, f"found forbidden {forbidden!r} in case detail JSON: {dumped}"


@pytest.mark.parametrize("status", STATUSES_NEW_TO_APPROVED)
async def test_status_wording_is_clean_for_each_status(repo, settings, status):
    repo.upsert_case("case-100028", status=status, **CASE_FIELDS)
    ctx = _ctx(repo, settings)

    body = get_case_detail("case-100028", ctx)

    assert body["case"]["status"] == status
    _assert_no_forbidden_wording(body)


async def test_status_wording_is_clean_for_refused_submission(repo, settings):
    # Mirrors tests/integration/test_submit.py's `test_payer_window_closed_gives_refused_outcome`:
    # a refused payer submission leaves the case at `approved` (the packet's own
    # `ready-for-review` status is untouched -- see src/reclaim/steps/approve_and_submit.py).
    repo.upsert_case("case-100028", status="approved", **CASE_FIELDS)
    letter = Letter(
        header=[HeaderField(label="Hospital claim ID", value="HSP-CLM-100028", source="remit")],
        body=[LetterStatement(statement_id="S1", text="The chart documents lumbar radiculopathy.",
                               requirement_ids=["R1"], citation_ids=["R1-C1"])],
        requested_action="Please reconsider and reprocess payment",
        attachments=["note-progress-031"], required_approver="authorized-billing-user", version=1,
    )
    repo.save_packet(
        "case-100028", 1, status="ready-for-review", content_sha256="a" * 64,
        letter_json=letter.model_dump_json(), blocked_reason=None,
        html="<html>packet</html>", pdf=b"%PDF-1.4 fake appeal letter",
        approved_by=None, approved_role=None, approved_at=None,
    )
    repo.save_submission(
        "appeal-case-100028-v1", case_id="case-100028", version=1, request_sha256="b" * 64,
        status="refused", appeal_id=None, received_at=None, expected_resolution_days=None,
        payer_status=None, error_code="appeal_window_closed",
        error_message="Appeal window closed; the payer will not accept a new appeal for this claim.",
    )
    ctx = _ctx(repo, settings)

    body = get_case_detail("case-100028", ctx)

    assert body["submission"]["status"] == "refused"
    assert body["submission"]["display"] is None
    _assert_no_forbidden_wording(body)
