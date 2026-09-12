from datetime import datetime, timedelta, timezone

from mocks.northstar import app as payer_app
from reclaim.context import AppContext
from reclaim.steps.track import track, track_submitted_cases

APPEAL_ID = "NST-APL-80126"
RECEIVED_AT = datetime(2026, 9, 12, 18, 32, 0, tzinfo=timezone.utc)

HERO_CASE = dict(
    case_id="case-100028", hospital_claim_id="HSP-CLM-100028", lane="medical-necessity",
    status="submitted", payer_claim_id="PAYER-CLM-99281", payer="Northstar Health",
    payer_id="NSTHLTH01", member_id="MEMBER-448820", rendering_npi="1234567893",
    procedure_qualifier="HC", procedure_code="72148", date_of_service="20260810",
    denial_code="CO-50", denial_reason="Medical necessity", billed_amount=4800.0, paid_amount=0.0,
    denied_amount=4800.0,
)


def _seed(repo, case_id="case-100028", status="submitted"):
    repo.upsert_case(case_id, **{**{k: v for k, v in HERO_CASE.items() if k != "case_id"}, "status": status})
    repo.save_packet(
        case_id, 1, status="ready-for-review", content_sha256="a" * 64,
        letter_json="{}", blocked_reason=None, html="<html></html>", pdf=b"%PDF-fake",
        approved_by="billing-approver-01", approved_role="authorized-billing-user",
        approved_at="2026-09-12T18:31:00Z",
    )
    repo.save_submission(
        f"appeal-{case_id}-v1", case_id=case_id, version=1, request_sha256="b" * 64,
        status="confirmed", appeal_id=APPEAL_ID, received_at=RECEIVED_AT.isoformat(),
        expected_resolution_days=14, payer_status="received", error_code=None, error_message=None,
    )


def _ctx(repo, settings, fixture_payer_adapter):
    return AppContext(
        repo=repo, settings=settings, remit_inbox=None, claim_archive=None, ehr_client=None,
        policy_store=None, payer_adapter=fixture_payer_adapter, llm_client=None,
    )


async def test_under_30_seconds_stays_submitted_with_no_new_event(repo, settings, fixture_payer_adapter):
    _seed(repo)
    payer_app.appeals[APPEAL_ID] = {"receivedAt": RECEIVED_AT}
    payer_app.set_now_fn(lambda: RECEIVED_AT + timedelta(seconds=10))
    try:
        ctx = _ctx(repo, settings, fixture_payer_adapter)

        result = await track(ctx, repo.get_case("case-100028"))

        assert result.changed is False
        assert repo.get_case("case-100028")["status"] == "submitted"
        assert repo.list_events("case-100028") == []
    finally:
        payer_app.reset_now_fn()


async def test_at_30_seconds_moves_to_in_review_with_exactly_one_event(repo, settings, fixture_payer_adapter):
    _seed(repo)
    payer_app.appeals[APPEAL_ID] = {"receivedAt": RECEIVED_AT}
    payer_app.set_now_fn(lambda: RECEIVED_AT + timedelta(seconds=30))
    try:
        ctx = _ctx(repo, settings, fixture_payer_adapter)

        result = await track(ctx, repo.get_case("case-100028"))

        assert result.changed is True
        assert result.appeal_id == APPEAL_ID
        assert repo.get_case("case-100028")["status"] == "in-review"
        events = repo.list_events("case-100028")
        assert len(events) == 1
        assert "in-review" in events[0]["summary"]

        # Polling again (as the poller would, with a freshly re-fetched case dict) writes
        # nothing further -- the case is already at the status the payer is reporting.
        result_again = await track(ctx, repo.get_case("case-100028"))
        assert result_again.changed is False
        assert len(repo.list_events("case-100028")) == 1
    finally:
        payer_app.reset_now_fn()


async def test_track_submitted_cases_only_polls_submitted_cases(repo, settings, fixture_payer_adapter):
    _seed(repo, case_id="case-100028", status="submitted")
    repo.upsert_case("case-100031", hospital_claim_id="HSP-CLM-100031", lane="paid", status="paid")
    payer_app.appeals[APPEAL_ID] = {"receivedAt": RECEIVED_AT}
    payer_app.set_now_fn(lambda: RECEIVED_AT + timedelta(seconds=30))
    try:
        ctx = _ctx(repo, settings, fixture_payer_adapter)

        await track_submitted_cases(ctx)

        assert repo.get_case("case-100028")["status"] == "in-review"
        assert repo.get_case("case-100031")["status"] == "paid"
        assert len(repo.list_events("case-100028")) == 1
        assert repo.list_events("case-100031") == []
    finally:
        payer_app.reset_now_fn()
