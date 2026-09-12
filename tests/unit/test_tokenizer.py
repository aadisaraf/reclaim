import pytest

from reclaim.x12.tokenizer import X12ParseError, tokenize

SAMPLE = (
    "ISA*00*          *00*          *ZZ*NORTHSTARHLTH  *ZZ*MOCKHOSPITAL   *260820*1200*^*00501*000000905*0*T*:~\n"
    "GS*HP*NORTHSTARHLTH*MOCKHOSPITAL*20260820*1200*905*X*005010X221A1~\n"
    "ST*835*0001~\n"
    "SE*2*0001~\n"
    "GE*1*905~\n"
    "IEA*1*000000905~\n"
)


def test_tokenizes_lf_segments():
    segments = tokenize(SAMPLE)
    ids = [s.id for s in segments]
    assert ids == ["ISA", "GS", "ST", "SE", "GE", "IEA"]
    assert segments[1].elements[0] == "HP"


def test_pipe_delimiters_tokenize_identically():
    piped = SAMPLE.replace("*", "|").replace(":", "}")
    # ISA16 (component sep) is at fixed position; element sep is ISA[3]
    segments = tokenize(piped)
    ids = [s.id for s in segments]
    assert ids == ["ISA", "GS", "ST", "SE", "GE", "IEA"]


def test_crlf_and_no_linebreaks_match():
    crlf = SAMPLE.replace("\n", "\r\n")
    no_breaks = SAMPLE.replace("\n", "")
    a = tokenize(SAMPLE)
    b = tokenize(crlf)
    c = tokenize(no_breaks)
    assert [s.id for s in a] == [s.id for s in b] == [s.id for s in c]


def test_empty_elements_preserved():
    text = SAMPLE.replace("CLP*HSP", "CLP**HSP") if "CLP" in SAMPLE else SAMPLE
    # construct a segment with an empty element explicitly
    with_empty = SAMPLE.replace("ST*835*0001~", "ST*835**0001~")
    segments = tokenize(with_empty)
    st = next(s for s in segments if s.id == "ST")
    assert st.elements[1] == ""


def test_truncated_isa_raises():
    with pytest.raises(X12ParseError):
        tokenize("ISA*00*short~")
