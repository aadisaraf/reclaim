from reclaim.x12.remit835 import parse_835
from reclaim.x12.tokenizer import tokenize
from reclaim.x12.validate import validate_835
from tests.unit.x12_samples import REMIT_835


def _failures(text):
    segments = tokenize(text)
    remit = parse_835(text)
    return [f.rule for f in validate_835(segments, remit)]


def test_fixture_passes():
    assert _failures(REMIT_835) == []


def test_se_count_mismatch_gives_x04():
    bad = REMIT_835.replace("SE*37*0001~", "SE*36*0001~")
    assert "X-04" in _failures(bad)


def test_unbalanced_cas_gives_x06():
    bad = REMIT_835.replace("CAS*CO*50*4800~", "CAS*CO*50*4700~")
    assert "X-06" in _failures(bad)


def test_bpr02_mismatch_gives_x08():
    bad = REMIT_835.replace("BPR*C*280*C*CHK", "BPR*C*290*C*CHK")
    assert "X-08" in _failures(bad)


def test_bad_npi_gives_x10():
    bad = REMIT_835.replace("1234567893", "1234567890")
    assert "X-10" in _failures(bad)


def test_wrong_version_gives_x05():
    bad = REMIT_835.replace("005010X221A1", "004010X091A1")
    assert "X-05" in _failures(bad)
