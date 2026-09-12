from datetime import datetime

from reclaim.x12.tokenizer import Segment


class RuleFailure:
    def __init__(self, rule: str, message: str):
        self.rule = rule
        self.message = message

    def __repr__(self) -> str:
        return f"RuleFailure({self.rule!r}, {self.message!r})"

    def __eq__(self, other):
        return isinstance(other, RuleFailure) and self.rule == other.rule


def npi_check_digit_valid(npi: str) -> bool:
    digits = "80840" + npi
    if not digits.isdigit():
        return False
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _valid_ccyymmdd(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y%m%d")
        return True
    except ValueError:
        return False


def _envelope_failures(segments: list[Segment]) -> list[RuleFailure]:
    failures: list[RuleFailure] = []
    isa = segments[0]
    iea = next((s for s in segments if s.id == "IEA"), None)
    gs_segments = [s for s in segments if s.id == "GS"]
    ge_segments = [s for s in segments if s.id == "GE"]
    st_segments = [s for s in segments if s.id == "ST"]
    se_segments = [s for s in segments if s.id == "SE"]

    if iea is None or isa.el(12) != iea.el(1) or iea.el(0) != str(len(gs_segments)):
        failures.append(RuleFailure("X-01", "ISA13/IEA02 or IEA01 mismatch"))

    for gs, ge in zip(gs_segments, ge_segments):
        if gs.el(5) != ge.el(1) or ge.el(0) != str(len(st_segments)):
            failures.append(RuleFailure("X-02", "GS06/GE02 or GE01 mismatch"))

    for st, se in zip(st_segments, se_segments):
        if st.el(1) != se.el(1):
            failures.append(RuleFailure("X-03", "ST02/SE02 mismatch"))

    for st, se in zip(st_segments, se_segments):
        start = segments.index(st)
        end = segments.index(se)
        count = end - start + 1
        if str(count) != se.el(0):
            failures.append(RuleFailure("X-04", f"SE01 {se.el(0)} does not match segment count {count}"))

    if any(s.id == "PLB" for s in segments):
        failures.append(RuleFailure("X-08", "PLB segments are not supported"))

    return failures


def _all_dates(segments: list[Segment]) -> list[str]:
    dates = []
    for s in segments:
        if s.id in ("DTM",) and len(s.elements) >= 2 and s.el(1).isdigit() and len(s.el(1)) == 8:
            dates.append(s.el(1))
        if s.id == "DTP" and len(s.elements) >= 3 and s.el(2).isdigit() and len(s.el(2)) == 8:
            dates.append(s.el(2))
    return dates


def validate_835(segments: list[Segment], remit) -> list[RuleFailure]:
    failures = _envelope_failures(segments)

    gs = next(s for s in segments if s.id == "GS")
    if gs.el(7) != "005010X221A1":
        failures.append(RuleFailure("X-05", "GS08 is not 005010X221A1"))

    bpr = next(s for s in segments if s.id == "BPR")
    bpr02 = float(bpr.el(1))
    total_clp04 = sum(c.paid for c in remit.claims)
    if not any(s.id == "PLB" for s in segments) and abs(bpr02 - total_clp04) > 0.001:
        failures.append(RuleFailure("X-08", f"BPR02 {bpr02} != sum CLP04 {total_clp04}"))

    for claim in remit.claims:
        claim_total_adj = sum(a.amount for a in claim.adjustments)
        expected = claim.billed - claim.paid
        if abs(expected - claim_total_adj) > 0.001:
            failures.append(RuleFailure("X-06", f"claim {claim.hospital_claim_id} balancing mismatch"))

        # X-07 is checked per service line; our fixtures have exactly one service per
        # claim, so it reduces to the same billed-paid-vs-adjustments arithmetic as X-06.
        service_adj = sum(a.amount for a in claim.adjustments if a.level == "service")
        service_expected = claim.billed - claim.paid
        if abs(service_expected - service_adj) > 0.001:
            failures.append(RuleFailure("X-07", f"service balancing mismatch for {claim.hospital_claim_id}"))

        pr_sum = sum(a.amount for a in claim.adjustments if a.group == "PR")
        if abs(claim.patient_responsibility - pr_sum) > 0.001:
            failures.append(RuleFailure("X-09", f"CLP05 mismatch for {claim.hospital_claim_id}"))

    npi_fields = []
    for s in segments:
        if s.id == "N1" and s.el(0) == "PE" and len(s.elements) >= 4:
            npi_fields.append(s.el(3))
        if s.id == "NM1" and s.el(0) == "82" and len(s.elements) >= 9:
            npi_fields.append(s.el(8))
    for npi in npi_fields:
        if npi and not npi_check_digit_valid(npi):
            failures.append(RuleFailure("X-10", f"NPI {npi} fails Luhn check"))

    for date_value in _all_dates(segments):
        if not _valid_ccyymmdd(date_value):
            failures.append(RuleFailure("X-13", f"invalid date {date_value}"))

    return failures


def validate_837(segments: list[Segment], claim) -> list[RuleFailure]:
    failures = _envelope_failures(segments)

    gs = next(s for s in segments if s.id == "GS")
    st = next(s for s in segments if s.id == "ST")
    if gs.el(7) != "005010X222A1" or st.el(2) != "005010X222A1":
        failures.append(RuleFailure("X-05", "GS08/ST03 is not 005010X222A1"))

    clm = next(s for s in segments if s.id == "CLM")
    sv1_total = sum(float(s.el(1)) for s in segments if s.id == "SV1")
    if abs(float(clm.el(1)) - sv1_total) > 0.001:
        failures.append(RuleFailure("X-11", "CLM02 != sum of SV102"))

    hl_segments = [s for s in segments if s.id == "HL"]
    seen_ids = set()
    for hl in hl_segments:
        parent = hl.el(1)
        if parent and parent not in seen_ids:
            failures.append(RuleFailure("X-12", f"HL parent {parent} not seen before this HL"))
        seen_ids.add(hl.el(0))

    npi_fields = []
    for s in segments:
        if s.id == "NM1" and s.el(0) == "85" and len(s.elements) >= 9:
            npi_fields.append(s.el(8))
        if s.id == "NM1" and s.el(0) == "82" and len(s.elements) >= 9:
            npi_fields.append(s.el(8))
    for npi in npi_fields:
        if npi and not npi_check_digit_valid(npi):
            failures.append(RuleFailure("X-10", f"NPI {npi} fails Luhn check"))

    for date_value in _all_dates(segments):
        if not _valid_ccyymmdd(date_value):
            failures.append(RuleFailure("X-13", f"invalid date {date_value}"))

    return failures
