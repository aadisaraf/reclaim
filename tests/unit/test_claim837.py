from reclaim.x12.claim837 import parse_837
from tests.unit.x12_samples import CLAIM_837


def test_extracted_fields_match_appendix_a3():
    claim = parse_837(CLAIM_837)
    assert claim.hospital_claim_id == "HSP-CLM-100028"
    assert claim.member_id == "MEMBER-448820"
    assert claim.payer_id == "NSTHLTH01"
    assert claim.billing_npi == "1245319599"
    assert claim.billing_state == "WA"
    assert claim.rendering_npi == "1234567893"
    assert claim.procedure_qualifier == "HC"
    assert claim.procedure_code == "72148"
    assert claim.units == 1
    assert claim.billed == 4800
    assert claim.date_of_service == "20260810"


def test_diagnosis_normalized():
    claim = parse_837(CLAIM_837)
    assert claim.diagnosis_code == "M54.16"


def test_group_number_and_frequency_code():
    claim = parse_837(CLAIM_837)
    assert claim.group_number == "NST-PPO-GRP-01"
    assert claim.frequency_code == "1"


def test_frequency_code_7_detected():
    corrected = CLAIM_837.replace("CLM*HSP-CLM-100028*4800***11:B:1*", "CLM*HSP-CLM-100028*4800***11:B:7*")
    claim = parse_837(corrected)
    assert claim.frequency_code == "7"


def test_names_not_in_model_dump():
    claim = parse_837(CLAIM_837)
    assert "RIVERA" not in claim.model_dump_json()
