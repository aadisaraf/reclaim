"""Validation tests for the X12 835/837P fixtures (Appendix A2 / A3).

These are raw-text checks only. They do NOT import from ``src/reclaim`` (that
module doesn't exist yet at the time these fixtures are authored). Delimiter
splitting and NPI Luhn validation are re-implemented inline, small and
self-contained, matching contracts/x12-fixtures.md.
"""

from __future__ import annotations

from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "x12"
ERA_835_PATH = FIXTURES_DIR / "era-2026-09-12.835"
CLM_837_PATH = FIXTURES_DIR / "HSP-CLM-100028.837"

# ---------------------------------------------------------------------------
# Expected byte-exact content, hand-copied from docs/reclaim-speckit-prompts.md
# Appendix A2 and A3. LF line endings, `~` segment terminators kept in place.
# ---------------------------------------------------------------------------

EXPECTED_835 = """\
ISA*00*          *00*          *ZZ*NORTHSTARHLTH  *ZZ*MOCKHOSPITAL   *260820*1200*^*00501*000000905*0*T*:~
GS*HP*NORTHSTARHLTH*MOCKHOSPITAL*20260820*1200*905*X*005010X221A1~
ST*835*0001~
BPR*C*280*C*CHK************20260820~
TRN*1*NST-CHK-000905*1990000001~
DTM*405*20260820~
N1*PR*NORTHSTAR HEALTH~
N3*100 SYNTHETIC WAY~
N4*SEATTLE*WA*98101~
REF*2U*NSTHLTH01~
PER*BL*PROVIDER SERVICES*TE*5555550100~
N1*PE*MOCK HOSPITAL*XX*1245319599~
LX*1~
CLP*HSP-CLM-100028*4*4800*0**12*PAYER-CLM-99281*11*1~
NM1*QC*1*RIVERA*JORDAN****MI*MEMBER-448820~
NM1*82*1*LEE*SAM****XX*1234567893~
DTM*232*20260810~
DTM*233*20260810~
SVC*HC:72148*4800*0**1~
DTM*472*20260810~
CAS*CO*50*4800~
REF*6R*HSP-CLM-100028-1~
CLP*HSP-CLM-100031*1*350*280**12*PAYER-CLM-99305*11*1~
NM1*QC*1*PATEL*AVERY****MI*MEMBER-448901~
DTM*232*20260812~
DTM*233*20260812~
SVC*HC:99213*350*280**1~
DTM*472*20260812~
CAS*CO*45*70~
REF*6R*HSP-CLM-100031-1~
CLP*HSP-CLM-100035*4*620*0**12*PAYER-CLM-99310*11*1~
NM1*QC*1*NGUYEN*CASEY****MI*MEMBER-449012~
DTM*232*20260813~
DTM*233*20260813~
SVC*HC:73030*620*0**1~
DTM*472*20260813~
CAS*CO*16*620~
REF*6R*HSP-CLM-100035-1~
SE*37*0001~
GE*1*905~
IEA*1*000000905~
"""

EXPECTED_837 = """\
ISA*00*          *00*          *ZZ*MOCKHOSPITAL   *ZZ*MOCKCLEARINGHS *260811*0900*^*00501*000000712*0*T*:~
GS*HC*MOCKHOSPITAL*MOCKCLEARINGHS*20260811*0900*712*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*HSP-BATCH-0712*20260811*0900*CH~
NM1*41*2*MOCK HOSPITAL*****46*MOCKHOSP01~
PER*IC*BILLING OFFICE*TE*5555550199~
NM1*40*2*MOCK CLEARINGHOUSE*****46*MOCKCH01~
HL*1**20*1~
NM1*85*2*MOCK HOSPITAL*****XX*1245319599~
N3*1 SYNTHETIC PLAZA~
N4*SEATTLE*WA*98104~
REF*EI*990000001~
HL*2*1*22*0~
SBR*P*18*NST-PPO-GRP-01******12~
NM1*IL*1*RIVERA*JORDAN****MI*MEMBER-448820~
N3*200 EXAMPLE AVE~
N4*SEATTLE*WA*98105~
DMG*D8*19800214*U~
NM1*PR*2*NORTHSTAR HEALTH*****PI*NSTHLTH01~
CLM*HSP-CLM-100028*4800***11:B:1*Y*A*Y*I~
HI*ABK:M5416~
NM1*82*1*LEE*SAM****XX*1234567893~
LX*1~
SV1*HC:72148*4800*UN*1***1~
DTP*472*D8*20260810~
REF*6R*HSP-CLM-100028-1~
SE*25*0001~
GE*1*712~
IEA*1*000000712~
"""


def _read(path: Path) -> str:
    with open(path, "r", newline="") as fh:
        return fh.read()


def _segments(text: str) -> list[str]:
    """Split into segments on '~', dropping the trailing empty piece from the
    final terminator, and dropping the line-break characters that follow each
    terminator (LF here, since fixtures are stored with LF line endings)."""
    raw = text.replace("\r\n", "\n")
    pieces = [seg.strip("\n") for seg in raw.split("~")]
    # Drop trailing empty segment produced by the final '~' + newline.
    if pieces and pieces[-1] == "":
        pieces = pieces[:-1]
    return pieces


def _elements(segment: str) -> list[str]:
    return segment.split("*")


def _luhn_ok(digits: str) -> bool:
    """Standard Luhn checksum over a string of digits."""
    total = 0
    parity = len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def npi_passes_luhn_80840(npi: str) -> bool:
    """NPIs are validated by prepending the fixed prefix 80840 to the 10-digit
    NPI, then applying the standard Luhn check digit algorithm to the full
    15-digit string (per contracts/x12-fixtures.md rule X-10)."""
    assert len(npi) == 10 and npi.isdigit()
    return _luhn_ok("80840" + npi)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_835_fixture_exists_and_matches_appendix_a2_exactly():
    assert ERA_835_PATH.is_file()
    actual = _read(ERA_835_PATH)
    assert actual == EXPECTED_835


def test_837_fixture_exists_and_matches_appendix_a3_exactly():
    assert CLM_837_PATH.is_file()
    actual = _read(CLM_837_PATH)
    assert actual == EXPECTED_837


def test_835_line_endings_are_lf_only():
    raw = ERA_835_PATH.read_bytes()
    assert b"\r" not in raw


def test_837_line_endings_are_lf_only():
    raw = CLM_837_PATH.read_bytes()
    assert b"\r" not in raw


def test_isa_is_106_characters():
    for path in (ERA_835_PATH, CLM_837_PATH):
        first_line = _read(path).splitlines()[0]
        assert len(first_line) == 106, f"{path.name}: ISA line is {len(first_line)} chars"
        assert first_line.startswith("ISA*")
        assert first_line.endswith("~")


def test_se01_is_37_for_835():
    segments = _segments(_read(ERA_835_PATH))
    se_segments = [s for s in segments if s.startswith("SE*")]
    assert len(se_segments) == 1
    se01 = _elements(se_segments[0])[1]
    assert se01 == "37"


def test_se01_is_25_for_837p():
    segments = _segments(_read(CLM_837_PATH))
    se_segments = [s for s in segments if s.startswith("SE*")]
    assert len(se_segments) == 1
    se01 = _elements(se_segments[0])[1]
    assert se01 == "25"


def test_se01_actually_counts_segments_st_through_se_inclusive_835():
    segments = _segments(_read(ERA_835_PATH))
    st_index = next(i for i, s in enumerate(segments) if s.startswith("ST*"))
    se_index = next(i for i, s in enumerate(segments) if s.startswith("SE*"))
    count = se_index - st_index + 1
    assert count == 37


def test_se01_actually_counts_segments_st_through_se_inclusive_837():
    segments = _segments(_read(CLM_837_PATH))
    st_index = next(i for i, s in enumerate(segments) if s.startswith("ST*"))
    se_index = next(i for i, s in enumerate(segments) if s.startswith("SE*"))
    count = se_index - st_index + 1
    assert count == 25


def test_control_numbers_match_for_835():
    segments = _segments(_read(ERA_835_PATH))
    isa = _elements(next(s for s in segments if s.startswith("ISA*")))
    gs = _elements(next(s for s in segments if s.startswith("GS*")))
    ge = _elements(next(s for s in segments if s.startswith("GE*")))
    iea = _elements(next(s for s in segments if s.startswith("IEA*")))
    # ISA13 = control number
    assert isa[13] == "000000905"
    # ISA13 = IEA02
    assert iea[2] == "000000905"
    # GS06 = group control number
    assert gs[6] == "905"
    # GS06 = GE02
    assert ge[2] == "905"


def test_control_numbers_match_for_837():
    segments = _segments(_read(CLM_837_PATH))
    isa = _elements(next(s for s in segments if s.startswith("ISA*")))
    gs = _elements(next(s for s in segments if s.startswith("GS*")))
    ge = _elements(next(s for s in segments if s.startswith("GE*")))
    iea = _elements(next(s for s in segments if s.startswith("IEA*")))
    assert isa[13] == "000000712"
    assert iea[2] == "000000712"
    assert gs[6] == "712"
    assert ge[2] == "712"


def test_per_claim_balancing_835():
    """CLP03 (billed) - CLP04 (paid) = sum of CAS amounts at claim+service level,
    per claim, matching Appendix A2's stated balancing."""
    segments = _segments(_read(ERA_835_PATH))

    # Group segments into per-claim chunks, starting at each CLP.
    claims: list[list[str]] = []
    current: list[str] | None = None
    for seg in segments:
        if seg.startswith("CLP*"):
            current = [seg]
            claims.append(current)
        elif current is not None:
            current.append(seg)

    assert len(claims) == 3

    expected = {
        "HSP-CLM-100028": (4800, 0, 4800),
        "HSP-CLM-100031": (350, 280, 70),
        "HSP-CLM-100035": (620, 0, 620),
    }

    seen = set()
    for claim_segments in claims:
        clp = _elements(claim_segments[0])
        claim_id = clp[1]
        billed = int(clp[3])
        paid = int(clp[4])

        cas_total = 0
        for seg in claim_segments[1:]:
            if seg.startswith("CAS*"):
                els = _elements(seg)
                # CAS*group*(reason*amount)+ ; els[0]=CAS, els[1]=group,
                # then (reason, amount) pairs start at index 2, so amounts
                # sit at odd indices starting from 3.
                amounts = els[3::2]
                for amt in amounts:
                    if amt:
                        cas_total += int(float(amt))

        exp_billed, exp_paid, exp_cas = expected[claim_id]
        assert billed == exp_billed, claim_id
        assert paid == exp_paid, claim_id
        assert cas_total == exp_cas, claim_id
        assert billed - paid == cas_total, claim_id
        seen.add(claim_id)

    assert seen == set(expected)


def test_bpr02_equals_total_paid_across_claims():
    segments = _segments(_read(ERA_835_PATH))
    bpr = _elements(next(s for s in segments if s.startswith("BPR*")))
    bpr02 = int(bpr[2])
    assert bpr02 == 280

    clp_paid_sum = 0
    for seg in segments:
        if seg.startswith("CLP*"):
            els = _elements(seg)
            clp_paid_sum += int(els[4])
    assert clp_paid_sum == 280
    assert bpr02 == clp_paid_sum


def test_npis_pass_luhn_with_80840_prefix():
    assert npi_passes_luhn_80840("1234567893")
    assert npi_passes_luhn_80840("1245319599")


def test_npi_1234567890_fails_luhn_regression_guard():
    # Appendix B / A1: the original placeholder NPI 1234567890 fails the check
    # digit and must never appear as a rendering/billing NPI in fixtures.
    assert not npi_passes_luhn_80840("1234567890")


def test_clm02_equals_sv102_837():
    segments = _segments(_read(CLM_837_PATH))
    clm = _elements(next(s for s in segments if s.startswith("CLM*")))
    sv1 = _elements(next(s for s in segments if s.startswith("SV1*")))
    clm02 = int(clm[2])
    sv102 = int(sv1[2])
    assert clm02 == 4800
    assert sv102 == 4800
    assert clm02 == sv102


def test_ref_6r_follows_svc_on_every_835_claim():
    segments = _segments(_read(ERA_835_PATH))
    svc_indices = [i for i, s in enumerate(segments) if s.startswith("SVC*")]
    assert len(svc_indices) == 3
    for idx in svc_indices:
        # Between SVC and the next REF*6R there may be DTM/CAS lines; find the
        # next REF*6R before the next SVC or CLP.
        j = idx + 1
        found = False
        while j < len(segments) and not segments[j].startswith("SVC*") and not segments[j].startswith("CLP*"):
            if segments[j].startswith("REF*6R*"):
                found = True
                break
            j += 1
        assert found, f"No REF*6R found after SVC at segment index {idx}"


def test_837_rendering_and_billing_npis_present_and_valid():
    segments = _segments(_read(CLM_837_PATH))
    nm1_85 = _elements(next(s for s in segments if s.startswith("NM1*85*")))
    nm1_82 = _elements(next(s for s in segments if s.startswith("NM1*82*")))
    billing_npi = nm1_85[-1]
    rendering_npi = nm1_82[-1]
    assert billing_npi == "1245319599"
    assert rendering_npi == "1234567893"
    assert npi_passes_luhn_80840(billing_npi)
    assert npi_passes_luhn_80840(rendering_npi)


def test_835_rendering_and_payee_npis_present_and_valid():
    segments = _segments(_read(ERA_835_PATH))
    nm1_82_all = [_elements(s) for s in segments if s.startswith("NM1*82*")]
    n1_pe = _elements(next(s for s in segments if s.startswith("N1*PE*")))
    payee_npi = n1_pe[-1]
    assert payee_npi == "1245319599"
    assert npi_passes_luhn_80840(payee_npi)
    # Hero claim's rendering NPI
    hero_rendering_npi = nm1_82_all[0][-1]
    assert hero_rendering_npi == "1234567893"
    assert npi_passes_luhn_80840(hero_rendering_npi)
