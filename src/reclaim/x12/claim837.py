from reclaim.models import OriginalClaim
from reclaim.x12.tokenizer import tokenize


def _normalize_diagnosis(raw: str) -> str:
    if len(raw) > 3 and "." not in raw:
        return f"{raw[:3]}.{raw[3:]}"
    return raw


def parse_837(text: str) -> OriginalClaim:
    segments = tokenize(text)

    billing_npi = billing_state = ""
    member_id = None
    group_number = payer_id = ""
    rendering_npi = ""
    diagnosis_code = ""
    hospital_claim_id = ""
    billed = 0.0
    frequency_code = ""
    procedure_qualifier = procedure_code = ""
    units = 0.0
    date_of_service = ""

    seen_billing_provider = False
    for s in segments:
        if s.id == "NM1" and s.el(0) == "85":
            billing_npi = s.el(8)
            seen_billing_provider = True
        elif s.id == "N4" and seen_billing_provider and not billing_state:
            billing_state = s.el(1)
        elif s.id == "SBR":
            group_number = s.el(2)
        elif s.id == "NM1" and s.el(0) == "IL":
            member_id = s.el(8) or None
        elif s.id == "NM1" and s.el(0) == "PR":
            payer_id = s.el(8)
        elif s.id == "CLM":
            hospital_claim_id = s.el(0)
            billed = float(s.el(1))
            clm05 = s.el(4).split(":")
            frequency_code = clm05[2] if len(clm05) > 2 else ""
        elif s.id == "HI":
            hi01 = s.el(0).split(":")
            if len(hi01) > 1:
                diagnosis_code = _normalize_diagnosis(hi01[1])
        elif s.id == "NM1" and s.el(0) == "82":
            rendering_npi = s.el(8)
        elif s.id == "SV1":
            composite = s.el(0).split(":")
            procedure_qualifier = composite[0] if composite else ""
            procedure_code = composite[1] if len(composite) > 1 else ""
            units = float(s.el(3)) if s.el(3) else 0.0
        elif s.id == "DTP" and s.el(0) == "472":
            date_of_service = s.el(2)

    return OriginalClaim(
        hospital_claim_id=hospital_claim_id,
        billed=billed,
        frequency_code=frequency_code,
        member_id=member_id,
        group_number=group_number,
        payer_id=payer_id,
        billing_npi=billing_npi,
        billing_state=billing_state,
        rendering_npi=rendering_npi,
        procedure_qualifier=procedure_qualifier,
        procedure_code=procedure_code,
        units=units,
        diagnosis_code=diagnosis_code,
        date_of_service=date_of_service,
    )
