"""T117: a second, different 835 (new ISA13/GS06/TRN02, same claim numbers) that repeats an
already-ingested `hospital_claim_id` must not create a duplicate case -- it should just write a
"later remittance" audit event onto the existing case (see src/reclaim/steps/ingest.py:
`existing = repo.get_case(case_id); if existing is not None: write_event(...); continue`)."""

from reclaim.steps.ingest import ingest

ISA13_OLD = "*000000905*0*T*:~"
ISA13_NEW = "*000000906*0*T*:~"
IEA_OLD = "IEA*1*000000905~"
IEA_NEW = "IEA*1*000000906~"
GS06_OLD = "*1200*905*X*005010X221A1~"
GS06_NEW = "*1200*906*X*005010X221A1~"
GE_OLD = "GE*1*905~"
GE_NEW = "GE*1*906~"
TRN_OLD = "TRN*1*NST-CHK-000905*1990000001~"
TRN_NEW = "TRN*1*NST-CHK-000906*1990000001~"


def _mutate_control_numbers(text: str) -> str:
    """ISA13 must still match IEA02, and GS06 must still match GE02 (see
    src/reclaim/x12/validate.py's `_envelope_failures`), so the ISA/IEA pair and the GS/GE pair
    are each bumped together to keep the file well-formed -- otherwise it would be rejected
    (X-01/X-02) rather than processed as a legitimate second remittance."""
    for old, new in [(ISA13_OLD, ISA13_NEW), (IEA_OLD, IEA_NEW), (GS06_OLD, GS06_NEW),
                     (GE_OLD, GE_NEW), (TRN_OLD, TRN_NEW)]:
        assert text.count(old) == 1, old
        text = text.replace(old, new, 1)
    return text


async def test_second_remittance_for_same_claim_creates_no_new_case(repo, settings, fixtures_dir):
    original_text = (fixtures_dir / "x12" / "era-2026-09-12.835").read_text()
    first_result = ingest(repo, settings, "era-2026-09-12.835", original_text.encode())
    assert first_result.status == "processed"
    assert len(repo.list_cases()) == 3
    events_before = len(repo.list_events("case-100028"))

    mutated_text = _mutate_control_numbers(original_text)
    assert mutated_text != original_text

    second_result = ingest(repo, settings, "era-2026-09-13.835", mutated_text.encode())

    assert second_result.status == "processed"
    assert len(repo.list_cases()) == 3
    assert repo.get_case("case-100028") is not None
    assert repo.get_case("case-100031") is not None
    assert repo.get_case("case-100035") is not None

    events_after = repo.list_events("case-100028")
    assert len(events_after) == events_before + 1
    new_event = events_after[-1]
    assert "later remittance" in new_event["summary"]
    assert "HSP-CLM-100028" in new_event["summary"]
