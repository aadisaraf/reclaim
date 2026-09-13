"""T108: contract tests for the demo-controls wiring (US7) -- PUT /api/demo/missing-evidence,
GET /api/config reflecting the toggle, and POST /api/cases/{caseId}/rerun's 202/409 paths
(data-model.md §6, specs/001-denial-recovery/tasks.md T108). These routes and reclaim.demo's
set_missing_evidence already exist (T110); this file only verifies the wiring end to end against
the mock hospital via `fixture_ehr_client` (tests/conftest.py) and a real ASGI app.
"""

import httpx

from reclaim.adapters.policy import FilePolicyStore
from reclaim.context import AppContext
from reclaim.main import create_app

CASE = dict(
    case_id="case-100028", hospital_claim_id="HSP-CLM-100028", lane="medical-necessity",
    status="needs-evidence", payer_claim_id="PAYER-CLM-99281", payer="Northstar Health",
    payer_id="NSTHLTH01", member_id="MEMBER-448820", rendering_npi="1234567893",
    procedure_qualifier="HC", procedure_code="72148", date_of_service="20260810",
    denial_code="CO-50", denial_reason="Medical necessity", billed_amount=4800.0, paid_amount=0.0,
    denied_amount=4800.0,
)


def _ctx(repo, settings, fixtures_dir, fixture_ehr_client) -> AppContext:
    return AppContext(
        repo=repo, settings=settings, remit_inbox=None, claim_archive=None,
        ehr_client=fixture_ehr_client, policy_store=FilePolicyStore(fixtures_dir / "policies"),
        payer_adapter=None, llm_client=None,
    )


async def test_put_missing_evidence_enables_it_on_the_hospital_mock(repo, settings, fixtures_dir, fixture_ehr_client):
    ctx = _ctx(repo, settings, fixtures_dir, fixture_ehr_client)
    app = create_app(settings, ctx)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.put("/api/demo/missing-evidence", json={"enabled": True})

    assert resp.status_code == 200
    assert resp.json() == {"enabled": True}

    from mocks.hospital import app as hospital_app

    assert hospital_app.missing_evidence is True

    token = await fixture_ehr_client._get_token()
    state = await fixture_ehr_client._client.get(
        "http://mock-hospital.example/_control/state", headers={"Authorization": f"Bearer {token}"}
    )
    assert state.json() == {"missingEvidence": True}


async def test_get_config_reflects_the_toggle_after_it_is_enabled(repo, settings, fixtures_dir, fixture_ehr_client):
    ctx = _ctx(repo, settings, fixtures_dir, fixture_ehr_client)
    app = create_app(settings, ctx)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        put_resp = await client.put("/api/demo/missing-evidence", json={"enabled": True})
        assert put_resp.status_code == 200

        config_resp = await client.get("/api/config")

    assert config_resp.status_code == 200
    assert config_resp.json()["missingEvidence"] is True


async def test_rerun_returns_202_for_needs_evidence_case(repo, settings, fixtures_dir, fixture_ehr_client):
    repo.upsert_case(CASE["case_id"], **{k: v for k, v in CASE.items() if k != "case_id"})
    ctx = _ctx(repo, settings, fixtures_dir, fixture_ehr_client)
    app = create_app(settings, ctx)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/cases/case-100028/rerun")

    assert resp.status_code == 202
    assert resp.json() == {"caseId": "case-100028", "running": True}


async def test_rerun_returns_409_rerun_unavailable_for_submitted_case(repo, settings, fixtures_dir, fixture_ehr_client):
    submitted_case = {**CASE, "status": "submitted"}
    repo.upsert_case(submitted_case["case_id"], **{k: v for k, v in submitted_case.items() if k != "case_id"})
    ctx = _ctx(repo, settings, fixtures_dir, fixture_ehr_client)
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
