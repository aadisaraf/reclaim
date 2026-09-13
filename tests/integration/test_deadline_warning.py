"""T115: integration test that a payer-stated appealDeadline diverging from the policy's
computed window date surfaces as a warning on PayerContextResult.deadline, end to end through
the real `payer_context` step (not just `compute_deadline` directly -- see tests/unit/test_deadline.py
for the pure-function-level test)."""

import json

from reclaim.adapters.protocols import PayerDecision
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


class FakePayerAdapter:
    """Hand-rolled fake matching `PayerAdapter`'s shape (see src/reclaim/adapters/protocols.py).
    `payer_context` only calls `get_decision`/`get_document`; the rest are stubbed since
    nothing in this test path reaches them."""

    def __init__(self, appeal_deadline: str):
        self.appeal_deadline = appeal_deadline

    async def get_decision(self, payer_claim_id: str) -> PayerDecision:
        return PayerDecision(
            payerClaimId=payer_claim_id, claimId="HSP-CLM-100028", decision="denied",
            decisionDate="2026-08-20", reasonCode="CO-50", reasonText="Medical necessity",
            appealDeadline=self.appeal_deadline, allowedSubmissionChannels=["portal"],
            letter={"documentId": "denial-letter-100028"},
        )

    async def get_document(self, document_id: str) -> bytes:
        return b"%PDF-1.4 fake denial letter"

    async def upload_document(self, **kwargs):
        raise NotImplementedError

    async def create_appeal(self, request, idempotency_key):
        raise NotImplementedError

    async def get_appeal(self, appeal_id):
        raise NotImplementedError


def _seed(repo):
    repo.upsert_case(HERO_CASE["case_id"], **{k: v for k, v in HERO_CASE.items() if k != "case_id"})
    repo.save_step_output("case-100028", "gather_evidence", json.dumps({
        "policy_id": "NST-IMG-2026-04", "policy_version": "2026.04", "appeal_window_days": 60,
    }))


def _ctx(repo, settings, payer_adapter):
    return AppContext(
        repo=repo, settings=settings, remit_inbox=None, claim_archive=None, ehr_client=None,
        policy_store=None, payer_adapter=payer_adapter, llm_client=None,
    )


async def test_payer_deadline_mismatch_warns_and_uses_payer_deadline(repo, settings):
    _seed(repo)
    # Policy window date (decisionDate 2026-08-20 + 60-day window) is 2026-10-19, but the
    # payer mock is overridden to state 2026-10-15 instead -- a 4-day mismatch.
    adapter = FakePayerAdapter(appeal_deadline="2026-10-15")
    ctx = _ctx(repo, settings, adapter)

    result = await payer_context(ctx, repo.get_case("case-100028"))

    assert result.deadline is not None
    assert result.deadline.deadline_of_record == "2026-10-15"
    assert result.deadline.policy_window_date == "2026-10-19"
    assert result.deadline.warning is not None
    assert "October 15, 2026" in result.deadline.warning
    assert "October 19, 2026" in result.deadline.warning
    assert "October 15, 2026" in result.deadline.line

    # The denial-letter PDF the fake adapter returned was saved through the real repo, and the
    # policy id/version threaded through from gather_evidence's step-output.
    assert result.policy_id == "NST-IMG-2026-04"
    assert result.policy_version == "2026.04"
    saved_doc = repo.get_document("denial-letter-100028")
    assert saved_doc is not None
    assert saved_doc["case_id"] == "case-100028"
