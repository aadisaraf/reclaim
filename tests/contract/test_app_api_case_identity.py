"""Contract tests for GET /api/cases/{caseId}: identity chain, checks, and timeline (T060)."""

import json

import httpx

from reclaim.audit import write_event
from reclaim.context import AppContext
from reclaim.main import create_app

HERO_CASE = dict(
    case_id="case-100028", hospital_claim_id="HSP-CLM-100028", lane="medical-necessity",
    status="claim-matched", payer_claim_id="PAYER-CLM-99281", payer="Northstar Health",
    payer_id="NSTHLTH01", member_id="MEMBER-448820", rendering_npi="1234567893",
    procedure_qualifier="HC", procedure_code="72148", date_of_service="20260810",
    denial_code="CO-50", denial_reason="Medical necessity", billed_amount=4800.0, paid_amount=0.0,
    denied_amount=4800.0, running=0, needs_review_field=None, last_error=None,
)

SIX_PASSED_CHECKS = [
    {"field": "claimId", "source_a": "remit", "value_a": "HSP-CLM-100028",
     "source_b": "claim837", "value_b": "HSP-CLM-100028", "passed": True},
    {"field": "memberId", "source_a": "remit", "value_a": "MEMBER-448820",
     "source_b": "claim837", "value_b": "MEMBER-448820", "passed": True},
    {"field": "dateOfService", "source_a": "remit", "value_a": "2026-08-10",
     "source_b": "claim837", "value_b": "2026-08-10", "passed": True},
    {"field": "payerId", "source_a": "remit", "value_a": "NSTHLTH01",
     "source_b": "claim837", "value_b": "NSTHLTH01", "passed": True},
    {"field": "renderingNpi", "source_a": "remit", "value_a": "1234567893",
     "source_b": "claim837", "value_b": "1234567893", "passed": True},
    {"field": "procedureCode", "source_a": "remit", "value_a": "HC:72148",
     "source_b": "claim837", "value_b": "HC:72148", "passed": True},
]

CLAIM_MAP_ENTRY = {
    "patientId": "patient-0042", "mrn": "MRN-0042", "encounterId": "encounter-20260810-42",
    "dateOfService": "2026-08-10", "procedureCode": "72148", "diagnosisCode": "M54.16",
}


def _ctx(repo, settings) -> AppContext:
    return AppContext(
        repo=repo, settings=settings, remit_inbox=None, claim_archive=None,
        ehr_client=None, policy_store=None, payer_adapter=None, llm_client=None,
    )


def _seed(repo, settings) -> None:
    repo.upsert_case(HERO_CASE["case_id"], **{k: v for k, v in HERO_CASE.items() if k != "case_id"})
    repo.save_step_output("case-100028", "fetch_claim", json.dumps({
        "original_claim": {
            "hospital_claim_id": "HSP-CLM-100028", "billed": 4800.0, "frequency_code": "1",
            "member_id": "MEMBER-448820", "group_number": "NST-PPO-GRP-01", "payer_id": "NSTHLTH01",
            "billing_npi": "1245319599", "billing_state": "WA", "rendering_npi": "1234567893",
            "procedure_qualifier": "HC", "procedure_code": "72148", "units": 1.0,
            "diagnosis_code": "M54.16", "date_of_service": "2026-08-10",
        },
    }))
    repo.save_step_output("case-100028", "resolve_identity", json.dumps({
        "checks": SIX_PASSED_CHECKS, "claim_map_entry": CLAIM_MAP_ENTRY,
    }))
    write_event(repo, settings, "case-100028", "ingest", "Read era-2026-09-12.835: created case-100028")
    write_event(repo, settings, "case-100028", "fetch_claim", "Fetched 837 for HSP-CLM-100028")
    write_event(
        repo, settings, "case-100028", "resolve_identity",
        "All 6 identity checks passed", detail={"checks": SIX_PASSED_CHECKS},
    )


async def test_case_detail_shows_identity_chain_checks_and_timeline(repo, settings):
    _seed(repo, settings)
    app = create_app(settings, _ctx(repo, settings))

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/cases/case-100028")

    assert resp.status_code == 200
    body = resp.json()
    assert body["identity"]["chain"] == [
        "HSP-CLM-100028", "837 HSP-CLM-100028", "encounter-20260810-42",
    ]
    assert len(body["identity"]["checks"]) == 6
    assert all(c["passed"] for c in body["identity"]["checks"])
    assert body["statusLine"] == "Claim matched"
    steps = [event["step"] for event in body["timeline"]]
    assert steps == ["ingest", "fetch_claim", "resolve_identity"]


async def test_unknown_case_returns_404_error_envelope(repo, settings):
    app = create_app(settings, _ctx(repo, settings))

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/cases/case-999999")

    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "not_found"
    assert "detail" not in body
