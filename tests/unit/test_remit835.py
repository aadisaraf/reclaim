from reclaim.x12.remit835 import parse_835
from tests.unit.x12_samples import REMIT_835


def test_three_claims():
    remit = parse_835(REMIT_835)
    assert len(remit.claims) == 3


def test_hero_claim_fields():
    remit = parse_835(REMIT_835)
    hero = remit.claims[0]
    assert hero.hospital_claim_id == "HSP-CLM-100028"
    assert hero.claim_status == "4"
    assert hero.billed == 4800
    assert hero.paid == 0
    assert hero.claim_filing_indicator == "12"
    assert hero.payer_claim_id == "PAYER-CLM-99281"
    assert hero.member_id == "MEMBER-448820"
    assert hero.rendering_npi == "1234567893"
    assert hero.date_of_service == "20260810"
    assert hero.procedure_qualifier == "HC"
    assert hero.procedure_code == "72148"
    assert hero.denial_code == "CO-50"


def test_cas_moved_to_claim_level_still_gives_denial_code():
    moved = REMIT_835.replace(
        "SVC*HC:72148*4800*0**1~\nDTM*472*20260810~\nCAS*CO*50*4800~\n",
        "CAS*CO*50*4800~\nSVC*HC:72148*4800*0**1~\nDTM*472*20260810~\n",
    )
    remit = parse_835(moved)
    assert remit.claims[0].denial_code == "CO-50"


def test_lanes():
    remit = parse_835(REMIT_835)
    lanes = {c.hospital_claim_id: c.lane for c in remit.claims}
    assert lanes["HSP-CLM-100028"] == "medical-necessity"
    assert lanes["HSP-CLM-100031"] == "paid"
    assert lanes["HSP-CLM-100035"] == "other-denial"


def test_payer_and_payee():
    remit = parse_835(REMIT_835)
    assert remit.payer_name == "NORTHSTAR HEALTH"
    assert remit.payer_id == "NSTHLTH01"
    assert remit.payee_npi == "1245319599"


def test_names_not_in_model_dump():
    remit = parse_835(REMIT_835)
    assert "RIVERA" not in remit.model_dump_json()
