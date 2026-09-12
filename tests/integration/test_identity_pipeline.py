import pytest

from reclaim.context import AppContext
from reclaim.steps.fetch_claim import fetch_claim
from reclaim.steps.resolve_identity import resolve_identity
from tests.fakes import FakeArchive, SpyEhrClient

HERO_CASE = dict(
    case_id="case-100028", hospital_claim_id="HSP-CLM-100028", lane="medical-necessity",
    status="new", payer_claim_id="PAYER-CLM-99281", payer="Northstar Health",
    payer_id="NSTHLTH01", member_id="MEMBER-448820", rendering_npi="1234567893",
    procedure_qualifier="HC", procedure_code="72148", date_of_service="20260810",
    denial_code="CO-50", denial_reason="Medical necessity", billed_amount=4800.0, paid_amount=0.0,
    denied_amount=4800.0,
)

VARIANTS = [
    ("claimId", "CLM*HSP-CLM-100028*", "CLM*HSP-CLM-999999*"),
    ("memberId", "MI*MEMBER-448820~", "MI*MEMBER-000000~"),
    ("dateOfService", "DTP*472*D8*20260810~", "DTP*472*D8*20260811~"),
    ("payerId", "PI*NSTHLTH01~", "PI*NSTHLTH99~"),
    ("renderingNpi", "NM1*82*1*LEE*SAM****XX*1234567893~", "NM1*82*1*LEE*SAM****XX*1245319599~"),
    ("procedureCode", "SV1*HC:72148*", "SV1*HC:72149*"),
]


def _seed_case(repo):
    repo.upsert_case(HERO_CASE["case_id"], **{k: v for k, v in HERO_CASE.items() if k != "case_id"})


def _ctx(repo, settings, archive, ehr_client):
    return AppContext(
        repo=repo, settings=settings, remit_inbox=None, claim_archive=archive,
        ehr_client=ehr_client, policy_store=None, payer_adapter=None, llm_client=None,
    )


async def _run_identity(ctx, case_id):
    case = ctx.repo.get_case(case_id)
    fetch_result = await fetch_claim(ctx, case)
    ctx.repo.save_step_output(case_id, "fetch_claim", fetch_result.model_dump_json())
    case = ctx.repo.get_case(case_id)
    return await resolve_identity(ctx, case)


def _mutate(text: str, old: str, new: str) -> bytes:
    assert text.count(old) == 1, old
    return text.replace(old, new, 1).encode()


async def test_hero_case_passes_all_six_checks(repo, settings, fixtures_dir):
    _seed_case(repo)
    archive = FakeArchive()
    archive.claims["HSP-CLM-100028"] = (fixtures_dir / "x12" / "HSP-CLM-100028.837").read_bytes()
    spy = SpyEhrClient()
    ctx = _ctx(repo, settings, archive, spy)

    result = await _run_identity(ctx, "case-100028")

    assert len(result.checks) == 6
    assert all(c.passed for c in result.checks)
    assert repo.get_case("case-100028")["status"] == "claim-matched"
    assert spy.requests_made == []

    identity_events = [e for e in repo.list_events("case-100028") if e["step"] == "resolve_identity"]
    assert len(identity_events) == 1
    assert identity_events[0]["ehr_requests_json"] == "[]"


async def test_missing_837_gives_needs_review_original_claim(repo, settings):
    _seed_case(repo)
    ctx = _ctx(repo, settings, FakeArchive(), SpyEhrClient())

    result = await fetch_claim(ctx, repo.get_case("case-100028"))

    assert result.original_claim is None
    case = repo.get_case("case-100028")
    assert case["status"] == "needs-review"
    assert case["needs_review_field"] == "originalClaim"


@pytest.mark.parametrize("field,old,new", VARIANTS)
async def test_one_field_mismatch_gives_needs_review(repo, settings, fixtures_dir, field, old, new):
    _seed_case(repo)
    original_text = (fixtures_dir / "x12" / "HSP-CLM-100028.837").read_text()
    archive = FakeArchive()
    archive.claims["HSP-CLM-100028"] = _mutate(original_text, old, new)
    spy = SpyEhrClient()
    ctx = _ctx(repo, settings, archive, spy)

    await _run_identity(ctx, "case-100028")

    case = repo.get_case("case-100028")
    assert case["status"] == "needs-review"
    assert case["needs_review_field"] == field
    assert spy.requests_made == []
    for event in repo.list_events("case-100028"):
        assert event["ehr_requests_json"] == "[]"
