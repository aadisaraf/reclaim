from reclaim.models import Adjustment, Remit, RemitClaim
from reclaim.x12.tokenizer import Segment, X12ParseError, tokenize

DENIAL_REASON_LABELS = {"50": "Medical necessity"}


def _lane_for(claim_status: str, denial_code: str | None, paid: float) -> str:
    if claim_status == "4":
        return "medical-necessity" if denial_code == "CO-50" else "other-denial"
    if claim_status in ("1", "2", "3") and paid > 0:
        return "paid"
    return "other-denial"


def parse_835(text: str) -> Remit:
    segments = tokenize(text)

    isa = segments[0]
    gs = next(s for s in segments if s.id == "GS")
    st = next(s for s in segments if s.id == "ST")

    payer_name = payer_id = payee_npi = production_date = payment_date = ""
    total_paid = 0.0
    for s in segments:
        if s.id == "BPR":
            total_paid = float(s.el(1))
            payment_date = s.el(15)
        elif s.id == "N1" and s.el(0) == "PR":
            payer_name = s.el(1)
        elif s.id == "N1" and s.el(0) == "PE":
            payee_npi = s.el(3)
        elif s.id == "REF" and s.el(0) == "2U":
            payer_id = s.el(1)
        elif s.id == "DTM" and s.el(0) == "405":
            production_date = s.el(1)

    claims: list[RemitClaim] = []
    current: dict | None = None
    in_service = False

    def finalize_claim():
        if current is None:
            return
        service_cas = [a for a in current["adjustments"] if a.level == "service"]
        claim_cas = [a for a in current["adjustments"] if a.level == "claim"]
        source = service_cas or claim_cas
        denial_code = f"{source[0].group}-{source[0].reason}" if source else None
        date_of_service = current["service_date"] or current["dtm232"] or current["dtm233"] or ""
        lane = _lane_for(current["claim_status"], denial_code, current["paid"])
        claims.append(RemitClaim(
            hospital_claim_id=current["hospital_claim_id"],
            claim_status=current["claim_status"],
            billed=current["billed"],
            paid=current["paid"],
            patient_responsibility=current["patient_responsibility"],
            claim_filing_indicator=current["claim_filing_indicator"],
            payer_claim_id=current["payer_claim_id"],
            payer_id=payer_id,
            member_id=current["member_id"],
            rendering_npi=current["rendering_npi"],
            date_of_service=date_of_service,
            procedure_qualifier=current["procedure_qualifier"],
            procedure_code=current["procedure_code"],
            adjustments=current["adjustments"],
            denial_code=denial_code,
            lane=lane,
        ))

    for s in segments:
        if s.id == "CLP":
            finalize_claim()
            in_service = False
            current = {
                "hospital_claim_id": s.el(0),
                "claim_status": s.el(1),
                "billed": float(s.el(2)),
                "paid": float(s.el(3)),
                "patient_responsibility": float(s.el(4)) if s.el(4) else 0.0,
                "claim_filing_indicator": s.el(5),
                "payer_claim_id": s.el(6),
                "member_id": None,
                "rendering_npi": "",
                "procedure_qualifier": "",
                "procedure_code": "",
                "adjustments": [],
                "service_date": None,
                "dtm232": None,
                "dtm233": None,
            }
            continue
        if current is None:
            continue
        if s.id == "NM1" and s.el(0) == "QC":
            current["member_id"] = s.el(8) or None
        elif s.id == "NM1" and s.el(0) == "82":
            current["rendering_npi"] = s.el(8)
        elif s.id == "DTM" and s.el(0) == "232":
            current["dtm232"] = s.el(1)
        elif s.id == "DTM" and s.el(0) == "233":
            current["dtm233"] = s.el(1)
        elif s.id == "SVC":
            in_service = True
            composite = s.el(0).split(":")
            current["procedure_qualifier"] = composite[0] if composite else ""
            current["procedure_code"] = composite[1] if len(composite) > 1 else ""
        elif s.id == "DTM" and s.el(0) == "472" and in_service:
            current["service_date"] = s.el(1)
        elif s.id == "CAS":
            level = "service" if in_service else "claim"
            current["adjustments"].append(
                Adjustment(group=s.el(0), reason=s.el(1), amount=float(s.el(2)), level=level)
            )
        elif s.id == "PLB":
            raise X12ParseError("PLB segments are not supported")

    finalize_claim()

    return Remit(
        isa13=isa.el(12),
        gs06=gs.el(5),
        st02=st.el(1),
        usage=isa.el(14),
        payer_name=payer_name,
        payer_id=payer_id,
        payee_npi=payee_npi,
        production_date=production_date,
        payment_date=payment_date,
        total_paid=total_paid,
        claims=claims,
    )
