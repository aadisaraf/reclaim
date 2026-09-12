from reclaim.steps.resolve_identity import check_post_read, run_identity_gate
from reclaim.x12.claim837 import parse_837
from reclaim.x12.remit835 import parse_835
from tests.unit.x12_samples import CLAIM_837, REMIT_835

HERO_CASE = {
    "hospital_claim_id": "HSP-CLM-100028",
    "member_id": "MEMBER-448820",
    "date_of_service": "20260810",
    "payer_id": "NSTHLTH01",
    "rendering_npi": "1234567893",
    "procedure_qualifier": "HC",
    "procedure_code": "72148",
}


def _hero_claim837():
    return parse_837(CLAIM_837)


def test_hero_case_passes_all_six_checks():
    checks = run_identity_gate(HERO_CASE, _hero_claim837())
    assert len(checks) == 6
    assert all(c.passed for c in checks)


def test_claim_id_mismatch_fails_claim_id():
    corrected = CLAIM_837.replace("CLM*HSP-CLM-100028*", "CLM*HSP-CLM-999999*", 1)
    claim = parse_837(corrected)
    checks = run_identity_gate(HERO_CASE, claim)
    failed = [c for c in checks if not c.passed]
    assert [c.field for c in failed] == ["claimId"]


def test_member_id_mismatch_fails_member_id():
    corrected = CLAIM_837.replace("NM1*IL*1*RIVERA*JORDAN****MI*MEMBER-448820~", "NM1*IL*1*RIVERA*JORDAN****MI*MEMBER-000000~")
    claim = parse_837(corrected)
    checks = run_identity_gate(HERO_CASE, claim)
    failed = [c for c in checks if not c.passed]
    assert [c.field for c in failed] == ["memberId"]


def test_date_of_service_mismatch_fails_date_of_service():
    corrected = CLAIM_837.replace("DTP*472*D8*20260810~", "DTP*472*D8*20260811~")
    claim = parse_837(corrected)
    checks = run_identity_gate(HERO_CASE, claim)
    failed = [c for c in checks if not c.passed]
    assert [c.field for c in failed] == ["dateOfService"]


def test_payer_id_mismatch_fails_payer_id():
    corrected = CLAIM_837.replace(
        "NM1*PR*2*NORTHSTAR HEALTH*****PI*NSTHLTH01~", "NM1*PR*2*NORTHSTAR HEALTH*****PI*OTHERPAYER~"
    )
    claim = parse_837(corrected)
    checks = run_identity_gate(HERO_CASE, claim)
    failed = [c for c in checks if not c.passed]
    assert [c.field for c in failed] == ["payerId"]


def test_rendering_npi_mismatch_fails_rendering_npi():
    corrected = CLAIM_837.replace(
        "NM1*82*1*LEE*SAM****XX*1234567893~", "NM1*82*1*LEE*SAM****XX*1234567890~"
    )
    claim = parse_837(corrected)
    checks = run_identity_gate(HERO_CASE, claim)
    failed = [c for c in checks if not c.passed]
    assert [c.field for c in failed] == ["renderingNpi"]


def test_procedure_code_mismatch_fails_procedure_code():
    corrected = CLAIM_837.replace("SV1*HC:72148*4800*UN*1***1~", "SV1*HC:99999*4800*UN*1***1~")
    claim = parse_837(corrected)
    checks = run_identity_gate(HERO_CASE, claim)
    failed = [c for c in checks if not c.passed]
    assert [c.field for c in failed] == ["procedureCode"]


def test_missing_member_id_on_remit_fails_member_id():
    case = {**HERO_CASE, "member_id": None}
    checks = run_identity_gate(case, _hero_claim837())
    failed = [c for c in checks if not c.passed]
    assert [c.field for c in failed] == ["memberId"]


def test_frequency_code_7_fails_claim_frequency():
    corrected = CLAIM_837.replace("CLM*HSP-CLM-100028*4800***11:B:1*", "CLM*HSP-CLM-100028*4800***11:B:7*")
    claim = parse_837(corrected)
    checks = run_identity_gate(HERO_CASE, claim)
    assert len(checks) == 7
    failed = [c for c in checks if not c.passed]
    assert [c.field for c in failed] == ["claimFrequency"]


def test_post_read_encounter_date_mismatch():
    checks = check_post_read(
        encounter={"period": {"start": "2026-08-11T09:00:00Z"}, "subject": {"reference": "Patient/patient-0042"}},
        patient_id="patient-0042",
        coverage={"subscriberId": "MEMBER-448820"},
        member_id="MEMBER-448820",
        date_of_service="2026-08-10",
    )
    failed = [c for c in checks if not c.passed]
    assert [c.field for c in failed] == ["encounterDate"]


def test_post_read_subject_mismatch():
    checks = check_post_read(
        encounter={"period": {"start": "2026-08-10T09:00:00Z"}, "subject": {"reference": "Patient/patient-0099"}},
        patient_id="patient-0042",
        coverage={"subscriberId": "MEMBER-448820"},
        member_id="MEMBER-448820",
        date_of_service="2026-08-10",
    )
    failed = [c for c in checks if not c.passed]
    assert [c.field for c in failed] == ["encounterSubject"]


def test_post_read_coverage_subscriber_mismatch():
    checks = check_post_read(
        encounter={"period": {"start": "2026-08-10T09:00:00Z"}, "subject": {"reference": "Patient/patient-0042"}},
        patient_id="patient-0042",
        coverage={"subscriberId": "MEMBER-000000"},
        member_id="MEMBER-448820",
        date_of_service="2026-08-10",
    )
    failed = [c for c in checks if not c.passed]
    assert [c.field for c in failed] == ["coverageSubscriberId"]


def test_post_read_all_pass():
    checks = check_post_read(
        encounter={"period": {"start": "2026-08-10T09:00:00Z"}, "subject": {"reference": "Patient/patient-0042"}},
        patient_id="patient-0042",
        coverage={"subscriberId": "MEMBER-448820"},
        member_id="MEMBER-448820",
        date_of_service="2026-08-10",
    )
    assert all(c.passed for c in checks)
