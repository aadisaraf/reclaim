import json

import pytest

from reclaim.adapters.policy import FilePolicyStore
from reclaim.context import AppContext
from reclaim.steps.gather_evidence import gather_evidence

HERO_CASE = dict(
    case_id="case-100028", hospital_claim_id="HSP-CLM-100028", lane="medical-necessity",
    status="claim-matched", payer_claim_id="PAYER-CLM-99281", payer="Northstar Health",
    payer_id="NSTHLTH01", member_id="MEMBER-448820", rendering_npi="1234567893",
    procedure_qualifier="HC", procedure_code="72148", date_of_service="20260810",
    denial_code="CO-50", denial_reason="Medical necessity", billed_amount=4800.0, paid_amount=0.0,
    denied_amount=4800.0,
)


def _seed(repo, fixtures_dir, member_id="MEMBER-448820"):
    repo.upsert_case(HERO_CASE["case_id"], **{k: v for k, v in HERO_CASE.items() if k != "case_id"})
    if member_id != "MEMBER-448820":
        repo.update_case(HERO_CASE["case_id"], member_id=member_id)
    repo.save_step_output(
        "case-100028", "fetch_claim",
        json.dumps({"original_claim": {"billing_state": "WA", "hospital_claim_id": "HSP-CLM-100028"}}),
    )
    claim_map = json.loads((fixtures_dir / "claim-map.json").read_text())
    repo.save_step_output(
        "case-100028", "resolve_identity",
        json.dumps({"checks": [], "claim_map_entry": claim_map["HSP-CLM-100028"]}),
    )


def _ctx(repo, settings, fixtures_dir, ehr_client):
    return AppContext(
        repo=repo, settings=settings, remit_inbox=None, claim_archive=None,
        ehr_client=ehr_client, policy_store=FilePolicyStore(fixtures_dir / "policies"),
        payer_adapter=None, llm_client=None,
    )


async def test_hero_case_gathers_expected_evidence(repo, settings, fixtures_dir, fixture_ehr_client):
    _seed(repo, fixtures_dir)
    ctx = _ctx(repo, settings, fixtures_dir, fixture_ehr_client)

    result = await gather_evidence(ctx, repo.get_case("case-100028"))

    assert fixture_ehr_client.requests_made[:3] == [
        "GET /fhir/R4/Encounter/encounter-20260810-42",
        "GET /fhir/R4/Patient/patient-0042",
        "GET /fhir/R4/Coverage?patient=patient-0042",
    ]
    assert fixture_ehr_client.requests_made[3:10] == [
        "GET /fhir/R4/Condition?patient=patient-0042",
        "GET /fhir/R4/ServiceRequest?patient=patient-0042",
        "GET /fhir/R4/Procedure?patient=patient-0042",
        "GET /fhir/R4/DiagnosticReport?patient=patient-0042",
        "GET /fhir/R4/Observation?patient=patient-0042",
        "GET /fhir/R4/DocumentReference?patient=patient-0042",
        "GET /fhir/R4/MedicationRequest?patient=patient-0042",
    ]
    assert fixture_ehr_client.requests_made[10:] == [
        "GET /fhir/R4/Binary/note-progress-031",
        "GET /fhir/R4/Binary/treatment-note-022",
    ]

    evidence = result.evidence_set
    included_ids = {i.resource.split("/")[-1] for i in evidence.items if i.included}
    assert included_ids == {
        "coverage-0042", "condition-100", "order-901", "procedure-902",
        "report-xr-555", "obs-pain-7781", "note-progress-031", "treatment-note-022",
    }
    assert evidence.excluded_count == 1
    assert evidence.search_counts["MedicationRequest"] == 0
    assert repo.get_case("case-100028")["status"] == "evidence-gathered"
    assert result.policy_id == "NST-IMG-2026-04"


async def test_coverage_subscriber_mismatch_stops_after_coverage(repo, settings, fixtures_dir, fixture_ehr_client):
    _seed(repo, fixtures_dir, member_id="MEMBER-000000")
    ctx = _ctx(repo, settings, fixtures_dir, fixture_ehr_client)

    await gather_evidence(ctx, repo.get_case("case-100028"))

    case = repo.get_case("case-100028")
    assert case["status"] == "needs-review"
    assert case["needs_review_field"] == "coverageSubscriberId"
    assert fixture_ehr_client.requests_made == [
        "GET /fhir/R4/Encounter/encounter-20260810-42",
        "GET /fhir/R4/Patient/patient-0042",
        "GET /fhir/R4/Coverage?patient=patient-0042",
    ]


async def test_encounter_date_mismatch_stops_after_encounter(repo, settings, fixtures_dir, fixture_ehr_client):
    repo.upsert_case(HERO_CASE["case_id"], **{k: v for k, v in HERO_CASE.items() if k != "case_id"})
    repo.save_step_output(
        "case-100028", "fetch_claim",
        json.dumps({"original_claim": {"billing_state": "WA", "hospital_claim_id": "HSP-CLM-100028"}}),
    )
    claim_map = json.loads((fixtures_dir / "claim-map.json").read_text())
    bad_entry = {**claim_map["HSP-CLM-100028"], "dateOfService": "2026-08-11"}
    repo.save_step_output(
        "case-100028", "resolve_identity", json.dumps({"checks": [], "claim_map_entry": bad_entry}),
    )
    ctx = _ctx(repo, settings, fixtures_dir, fixture_ehr_client)

    await gather_evidence(ctx, repo.get_case("case-100028"))

    case = repo.get_case("case-100028")
    assert case["status"] == "needs-review"
    assert case["needs_review_field"] == "encounterDate"
    assert fixture_ehr_client.requests_made == ["GET /fhir/R4/Encounter/encounter-20260810-42"]


async def test_no_matching_policy_gives_state_and_stops_before_clinical(repo, settings, fixtures_dir, fixture_ehr_client, tmp_path):
    _seed(repo, fixtures_dir)
    no_wa_policy_dir = tmp_path / "policies"
    no_wa_policy_dir.mkdir()
    policy = json.loads((fixtures_dir / "policies" / "NST-IMG-2026-04.json").read_text())
    policy["states"] = ["OR"]
    (no_wa_policy_dir / "NST-IMG-2026-04.json").write_text(json.dumps(policy))
    ctx = AppContext(
        repo=repo, settings=settings, remit_inbox=None, claim_archive=None,
        ehr_client=fixture_ehr_client, policy_store=FilePolicyStore(no_wa_policy_dir),
        payer_adapter=None, llm_client=None,
    )

    await gather_evidence(ctx, repo.get_case("case-100028"))

    case = repo.get_case("case-100028")
    assert case["status"] == "needs-review"
    assert case["needs_review_field"] == "state"
    assert fixture_ehr_client.requests_made == [
        "GET /fhir/R4/Encounter/encounter-20260810-42",
        "GET /fhir/R4/Patient/patient-0042",
        "GET /fhir/R4/Coverage?patient=patient-0042",
    ]
