from reclaim.x12.claim837 import parse_837
from reclaim.x12.tokenizer import tokenize
from reclaim.x12.validate import validate_837
from tests.unit.x12_samples import CLAIM_837


def _failures(text):
    segments = tokenize(text)
    claim = parse_837(text)
    return [f.rule for f in validate_837(segments, claim)]


def test_fixture_passes():
    assert _failures(CLAIM_837) == []


def test_se_count_mismatch_gives_x04():
    bad = CLAIM_837.replace("SE*25*0001~", "SE*24*0001~")
    assert "X-04" in _failures(bad)


def test_sv1_clm02_mismatch_gives_x11():
    bad = CLAIM_837.replace("SV1*HC:72148*4800*UN*1***1~", "SV1*HC:72148*4700*UN*1***1~")
    assert "X-11" in _failures(bad)


def test_hl_parent_mismatch_gives_x12():
    bad = CLAIM_837.replace("HL*2*1*22*0~", "HL*2*3*22*0~")
    assert "X-12" in _failures(bad)
