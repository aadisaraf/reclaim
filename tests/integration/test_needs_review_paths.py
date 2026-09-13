"""T105: every needs-review path, driven end to end through the real step functions.

Each scenario seeds a case row with `repo.upsert_case`, runs only the step functions needed
to reach the failure point (mirroring `src/reclaim/pipeline.py`'s STEPS order), then asserts
on the persisted case row *and* on `GET /api/cases/{caseId}` (via `httpx.ASGITransport`
against `reclaim.main.create_app`). All I/O boundaries are fakes: `FakeArchive`/`SpyEhrClient`
from `tests/fakes.py`, the `fixture_ehr_client` pytest fixture (a real `HttpEhrClient` wired to
the in-process mock-hospital ASGI app -- no real network), `FilePolicyStore` pointed at a
throwaway policy fixture, and a tiny local fake payer adapter.
"""

import json

import httpx

from reclaim.adapters.policy import FilePolicyStore
from reclaim.adapters.protocols import PayerError
from reclaim.context import AppContext
from reclaim.main import create_app
from reclaim.steps.fetch_claim import fetch_claim
from reclaim.steps.gather_evidence import gather_evidence
from reclaim.steps.payer_context import payer_context
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


def _seed_case(repo, **overrides) -> str:
    fields = {**HERO_CASE, **overrides}
    case_id = fields.pop("case_id")
    repo.upsert_case(case_id, **fields)
    return case_id


def _ctx(repo, settings, *, archive=None, ehr_client=None, policy_store=None, payer_adapter=None) -> AppContext:
    return AppContext(
        repo=repo, settings=settings, remit_inbox=None, claim_archive=archive,
        ehr_client=ehr_client, policy_store=policy_store, payer_adapter=payer_adapter, llm_client=None,
    )


async def _run_step(repo, case_id, step_name, step_fn, ctx):
    """Runs one real pipeline step and persists its output exactly as pipeline.run_case does."""
    case = repo.get_case(case_id)
    result = await step_fn(ctx, case)
    repo.save_step_output(case_id, step_name, result.model_dump_json())
    return result


async def _get_case_detail(repo, settings, case_id: str) -> dict:
    """GET /api/cases/{caseId} against the real FastAPI app -- the HTTP layer only reads
    already-persisted repo state, so adapters the pipeline steps used are irrelevant here."""
    app = create_app(settings, _ctx(repo, settings))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/cases/{case_id}")
    assert resp.status_code == 200
    return resp.json()


async def test_remit_without_nm1_qc_gives_needs_review_member_id(repo, settings, fixtures_dir):
    # remit835.parse_835 sets RemitClaim.member_id to None when the claim's NM1*QC segment is
    # absent (see src/reclaim/x12/remit835.py), and ingest() copies that straight onto the case
    # row -- so a blanked member_id on the case row is the faithful stand-in for that remit.
    case_id = _seed_case(repo, member_id=None)
    archive = FakeArchive()
    archive.claims["HSP-CLM-100028"] = (fixtures_dir / "x12" / "HSP-CLM-100028.837").read_bytes()
    spy = SpyEhrClient()
    ctx = _ctx(repo, settings, archive=archive, ehr_client=spy)

    await _run_step(repo, case_id, "fetch_claim", fetch_claim, ctx)
    await _run_step(repo, case_id, "resolve_identity", resolve_identity, ctx)

    case = repo.get_case(case_id)
    assert case["status"] == "needs-review"
    assert case["needs_review_field"] == "memberId"
    assert spy.requests_made == []

    body = await _get_case_detail(repo, settings, case_id)
    assert body["statusLine"] == "Needs review"
    assert body["case"]["caseId"] == case_id
    assert body["case"]["hospitalClaimId"] == "HSP-CLM-100028"
    assert body["case"]["needsReviewField"] == "memberId"


async def test_missing_837_gives_needs_review_original_claim(repo, settings):
    case_id = _seed_case(repo)
    spy = SpyEhrClient()
    ctx = _ctx(repo, settings, archive=FakeArchive(), ehr_client=spy)

    result = await fetch_claim(ctx, repo.get_case(case_id))
    repo.save_step_output(case_id, "fetch_claim", result.model_dump_json())

    assert result.original_claim is None
    case = repo.get_case(case_id)
    assert case["status"] == "needs-review"
    assert case["needs_review_field"] == "originalClaim"
    assert spy.requests_made == []

    body = await _get_case_detail(repo, settings, case_id)
    assert body["statusLine"] == "Needs review"
    assert body["case"]["needsReviewField"] == "originalClaim"


async def test_frequency_code_7_gives_needs_review_claim_frequency(repo, settings, fixtures_dir):
    case_id = _seed_case(repo)
    original_text = (fixtures_dir / "x12" / "HSP-CLM-100028.837").read_text()
    old, new = "CLM*HSP-CLM-100028*4800***11:B:1*", "CLM*HSP-CLM-100028*4800***11:B:7*"
    assert original_text.count(old) == 1
    archive = FakeArchive()
    archive.claims["HSP-CLM-100028"] = original_text.replace(old, new, 1).encode()
    spy = SpyEhrClient()
    ctx = _ctx(repo, settings, archive=archive, ehr_client=spy)

    await _run_step(repo, case_id, "fetch_claim", fetch_claim, ctx)
    identity_result = await _run_step(repo, case_id, "resolve_identity", resolve_identity, ctx)

    assert len(identity_result.checks) == 7
    case = repo.get_case(case_id)
    assert case["status"] == "needs-review"
    assert case["needs_review_field"] == "claimFrequency"
    assert spy.requests_made == []

    body = await _get_case_detail(repo, settings, case_id)
    assert body["statusLine"] == "Needs review"
    assert body["case"]["needsReviewField"] == "claimFrequency"


async def test_policy_store_no_match_gives_needs_review_state(
    repo, settings, fixtures_dir, fixture_ehr_client, tmp_path,
):
    case_id = _seed_case(repo)
    archive = FakeArchive()
    archive.claims["HSP-CLM-100028"] = (fixtures_dir / "x12" / "HSP-CLM-100028.837").read_bytes()

    # A real policy fixture, but with its states narrowed so the case's billing_state ("WA",
    # parsed off the 837's billing-provider N4) matches nothing -- selection fails on "state".
    policy = json.loads((fixtures_dir / "policies" / "NST-IMG-2026-04.json").read_text())
    policy["states"] = ["OR"]
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()
    (policy_dir / "NST-IMG-2026-04.json").write_text(json.dumps(policy))

    ctx = _ctx(
        repo, settings, archive=archive, ehr_client=fixture_ehr_client,
        policy_store=FilePolicyStore(policy_dir),
    )

    await _run_step(repo, case_id, "fetch_claim", fetch_claim, ctx)
    await _run_step(repo, case_id, "resolve_identity", resolve_identity, ctx)
    assert repo.get_case(case_id)["status"] == "claim-matched"

    await _run_step(repo, case_id, "gather_evidence", gather_evidence, ctx)

    case = repo.get_case(case_id)
    assert case["status"] == "needs-review"
    assert case["needs_review_field"] == "state"
    assert fixture_ehr_client.requests_made == [
        "GET /fhir/R4/Encounter/encounter-20260810-42",
        "GET /fhir/R4/Patient/patient-0042",
        "GET /fhir/R4/Coverage?patient=patient-0042",
    ]

    body = await _get_case_detail(repo, settings, case_id)
    assert body["statusLine"] == "Needs review"
    assert body["case"]["needsReviewField"] == "state"


async def test_payer_404_gives_needs_review_payer_claim_id(repo, settings):
    class FakeNotFoundPayerAdapter:
        """Local stand-in for a PayerAdapter whose claim lookup 404s (see protocols.PayerError)."""

        async def get_decision(self, payer_claim_id: str):
            raise PayerError(404, "claim_not_found", f"No claim {payer_claim_id}")

    case_id = _seed_case(repo, status="evidence-gathered")
    ctx = _ctx(repo, settings, payer_adapter=FakeNotFoundPayerAdapter())

    await _run_step(repo, case_id, "payer_context", payer_context, ctx)

    case = repo.get_case(case_id)
    assert case["status"] == "needs-review"
    assert case["needs_review_field"] == "payerClaimId"

    body = await _get_case_detail(repo, settings, case_id)
    assert body["statusLine"] == "Needs review"
    assert body["case"]["needsReviewField"] == "payerClaimId"
