from reclaim.steps.ingest import ingest


def test_ingest_creates_three_cases(repo, settings, fixtures_dir):
    content = (fixtures_dir / "x12" / "era-2026-09-12.835").read_bytes()

    result = ingest(repo, settings, "era-2026-09-12.835", content)

    assert result.status == "processed"
    assert result.new_case_ids == ["case-100028"]

    hero = repo.get_case("case-100028")
    assert hero["lane"] == "medical-necessity"
    assert hero["status"] == "new"
    assert hero["payer_claim_id"] == "PAYER-CLM-99281"
    assert hero["denial_code"] == "CO-50"
    assert hero["billed_amount"] == 4800.0

    paid = repo.get_case("case-100031")
    assert paid["lane"] == "paid"
    assert paid["status"] == "paid"

    other = repo.get_case("case-100035")
    assert other["lane"] == "other-denial"
    assert other["status"] == "other-denial"

    events = repo.list_events(None)
    remit_events = [e for e in events if e["step"] == "ingest"]
    assert len(remit_events) == 1
    assert remit_events[0]["ehr_requests_json"] == "[]"


def test_ingest_dedupes_identical_bytes(repo, settings, fixtures_dir):
    content = (fixtures_dir / "x12" / "era-2026-09-12.835").read_bytes()
    ingest(repo, settings, "era-2026-09-12.835", content)

    result = ingest(repo, settings, "era-copy.835", content)

    assert result.status == "duplicate"
    assert repo.get_case("case-100028") is not None
    assert len(repo.list_cases()) == 3

    events = repo.list_events(None)
    assert any("already processed" in e["summary"] for e in events)


def test_ingest_rejects_unbalanced_file(repo, settings, fixtures_dir):
    content = (fixtures_dir / "x12" / "era-2026-09-12.835").read_bytes()
    text = content.decode()
    broken = text.replace("CAS*CO*50*4800~", "CAS*CO*50*4700~")

    result = ingest(repo, settings, "era-broken.835", broken.encode())

    assert result.status == "rejected"
    assert result.reject_rule in ("X-06", "X-07")
    assert repo.list_cases() == []
