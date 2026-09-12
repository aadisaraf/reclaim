"""Contract tests for GET /api/queue and POST /api/demo/simulate-remit (T049)."""

import httpx

from reclaim.context import AppContext
from reclaim.main import create_app
from reclaim.steps.ingest import ingest
from tests.fakes import FakeInbox


def _ctx(repo, settings, remit_inbox=None) -> AppContext:
    return AppContext(
        repo=repo, settings=settings, remit_inbox=remit_inbox, claim_archive=None,
        ehr_client=None, policy_store=None, payer_adapter=None, llm_client=None,
    )


async def test_queue_after_ingest_shows_hero_case_with_a9_headline(repo, settings, fixtures_dir):
    content = (fixtures_dir / "x12" / "era-2026-09-12.835").read_bytes()
    ingest(repo, settings, "era-2026-09-12.835", content)
    app = create_app(settings, _ctx(repo, settings))

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/queue")

    assert resp.status_code == 200
    body = resp.json()
    assert [c["caseId"] for c in body["cases"]] == ["case-100028"]
    # ingest.py stores case["payer"] verbatim from the 835 N1*PR segment (see test_remit835.py),
    # which is uppercase "NORTHSTAR HEALTH" -- not the title-cased prose in docs Appendix A9.
    assert body["cases"][0]["headline"] == "Northstar Health · CO-50 Medical necessity · $4,800"
    assert body["cases"][0]["status"] == "new"
    assert body["cases"][0]["running"] is False


async def test_queue_summary_lines_match_a9_exactly(repo, settings, fixtures_dir):
    content = (fixtures_dir / "x12" / "era-2026-09-12.835").read_bytes()
    ingest(repo, settings, "era-2026-09-12.835", content)
    app = create_app(settings, _ctx(repo, settings))

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/queue")

    body = resp.json()
    assert body["summary"]["lines"] == [
        "1 paid claim, no action",
        "1 other denial lane: not handled in this demo",
    ]
    assert body["summary"]["paidClaims"] == 1
    assert body["summary"]["otherDenials"] == 1


async def test_queue_other_lane_label_and_remit_files(repo, settings, fixtures_dir):
    content = (fixtures_dir / "x12" / "era-2026-09-12.835").read_bytes()
    ingest(repo, settings, "era-2026-09-12.835", content)
    app = create_app(settings, _ctx(repo, settings))

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/queue")

    body = resp.json()
    assert body["otherLane"][0]["label"] == "Other denial lane: not handled in this demo"
    assert body["otherLane"][0]["caseId"] == "case-100035"
    assert body["otherLane"][0]["hospitalClaimId"] == "HSP-CLM-100035"
    assert body["otherLane"][0]["denialCode"] == "CO-16"
    assert body["remitFiles"] == [
        {"fileName": "era-2026-09-12.835", "status": "processed", "claimCount": 3},
    ]


async def test_simulate_remit_delivers_fixture_returns_202(repo, settings):
    inbox = FakeInbox()
    app = create_app(settings, _ctx(repo, settings, remit_inbox=inbox))

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/demo/simulate-remit")

    assert resp.status_code == 202
    assert resp.json() == {"delivered": "era-2026-09-12.835"}
    assert "era-2026-09-12.835" in inbox.files
