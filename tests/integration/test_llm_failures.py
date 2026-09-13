"""T119: a failing LLM client must fail `build_matrix` *visibly* through the real pipeline
orchestrator (`run_case` in src/reclaim/pipeline.py), not silently: the case status must not
advance past `evidence-gathered`, `last_error` must be set, and the audit timeline must show the
error. This drives the hero case through the real `fetch_claim` -> `resolve_identity` ->
`gather_evidence` -> `payer_context` steps (same fixtures/mocks as
tests/integration/test_identity_pipeline.py + tests/integration/test_gather_evidence.py) so that
`run_case` -- which always starts its STEPS list from `fetch_claim`, regardless of the case's
current status -- actually reaches `build_matrix` before the fake LLM client blows up."""

import httpx

from reclaim.adapters.policy import FilePolicyStore
from reclaim.adapters.protocols import ReplayMissError  # re-exported by reclaim.adapters.llm too
from reclaim.context import AppContext
from reclaim.main import create_app
from reclaim.pipeline import run_case
from tests.fakes import FakeArchive

HERO_CASE = dict(
    case_id="case-100028", hospital_claim_id="HSP-CLM-100028", lane="medical-necessity",
    status="new", payer_claim_id="PAYER-CLM-99281", payer="Northstar Health",
    payer_id="NSTHLTH01", member_id="MEMBER-448820", rendering_npi="1234567893",
    procedure_qualifier="HC", procedure_code="72148", date_of_service="20260810",
    denial_code="CO-50", denial_reason="Medical necessity", billed_amount=4800.0, paid_amount=0.0,
    denied_amount=4800.0,
)


class FakeFailingLlmClient:
    """Stands in for a live client whose `.parse(...)` blows up -- e.g. two straight 500s, or
    (in the second test below) a replay-fixture miss. `build_matrix` calls `.parse` once before
    ever considering a retry, so one raise is all it takes to prove the pipeline surfaces it."""

    def __init__(self, make_exception):
        self._make_exception = make_exception
        self.calls = 0

    async def parse(self, *, step, instructions, input, text_format, effort,
                     max_output_tokens, prompt_cache_key):
        self.calls += 1
        raise self._make_exception()


def _seed(repo):
    repo.upsert_case(HERO_CASE["case_id"], **{k: v for k, v in HERO_CASE.items() if k != "case_id"})


def _ctx(repo, settings, fixtures_dir, ehr_client, payer_adapter, llm_client):
    archive = FakeArchive()
    archive.claims["HSP-CLM-100028"] = (fixtures_dir / "x12" / "HSP-CLM-100028.837").read_bytes()
    return AppContext(
        repo=repo, settings=settings, remit_inbox=None, claim_archive=archive, ehr_client=ehr_client,
        policy_store=FilePolicyStore(fixtures_dir / "policies"), payer_adapter=payer_adapter,
        llm_client=llm_client,
    )


async def _assert_visible_failure(repo, ctx, llm):
    await run_case(ctx, "case-100028")

    case = repo.get_case("case-100028")
    assert case["status"] == "evidence-gathered"  # never advanced into/through build_matrix
    assert case["last_error"], "expected last_error to be set"
    assert case["running"] == 0

    events = repo.list_events("case-100028")
    error_events = [e for e in events if e["summary"].startswith("Error in build_matrix")]
    assert len(error_events) == 1
    assert case["last_error"] in error_events[0]["summary"]

    # No replay/fallback result was ever produced for build_matrix -- the step never saved output.
    assert repo.get_step_output("case-100028", "build_matrix") is None
    assert llm.calls >= 1


async def test_repeated_500s_fail_build_matrix_visibly(
    repo, settings, fixtures_dir, fixture_ehr_client, fixture_payer_adapter,
):
    _seed(repo)

    class FiveHundred(Exception):
        pass

    llm = FakeFailingLlmClient(lambda: FiveHundred("500 Internal Server Error (simulated, twice)"))
    ctx = _ctx(repo, settings, fixtures_dir, fixture_ehr_client, fixture_payer_adapter, llm)

    await _assert_visible_failure(repo, ctx, llm)

    # A second attempt (e.g. a rerun) fails exactly the same way -- the client keeps raising.
    repo.update_case("case-100028", status="evidence-gathered", last_error=None)
    await run_case(ctx, "case-100028")
    case = repo.get_case("case-100028")
    assert case["status"] == "evidence-gathered"
    assert case["last_error"]
    assert llm.calls >= 2

    app = create_app(settings, ctx)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/config")
    assert resp.status_code == 200
    assert resp.json()["aiMode"] == settings.llm_mode


async def test_replay_miss_fails_build_matrix_visibly(
    repo, settings, fixtures_dir, fixture_ehr_client, fixture_payer_adapter,
):
    _seed(repo)
    llm = FakeFailingLlmClient(lambda: ReplayMissError("build_matrix", "deadbeefcafe0102"))
    ctx = _ctx(repo, settings, fixtures_dir, fixture_ehr_client, fixture_payer_adapter, llm)

    await _assert_visible_failure(repo, ctx, llm)

    app = create_app(settings, ctx)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/config")
    assert resp.status_code == 200
    assert resp.json()["aiMode"] == settings.llm_mode
