from reclaim.repo import Repo


def make_repo(tmp_path):
    repo = Repo(str(tmp_path / "test.db"))
    repo.init_schema()
    return repo


def test_init_schema_creates_tables(tmp_path):
    repo = make_repo(tmp_path)
    tables = {
        r["name"]
        for r in repo.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    expected = {
        "remit_files", "cases", "step_outputs", "audit_events", "tasks",
        "packets", "submissions", "documents",
    }
    assert expected.issubset(tables)


def test_insert_remit_file_dedupes(tmp_path):
    repo = make_repo(tmp_path)
    assert repo.insert_remit_file("abc123", "era.835", "processed", None, 3) is True
    assert repo.insert_remit_file("abc123", "era.835", "processed", None, 3) is False


def test_upsert_case_unique_hospital_claim_id(tmp_path):
    repo = make_repo(tmp_path)
    repo.upsert_case("case-100028", hospital_claim_id="HSP-CLM-100028", status="new")
    case = repo.get_case("case-100028")
    assert case["hospital_claim_id"] == "HSP-CLM-100028"
    repo.upsert_case("case-100028", status="claim-matched")
    assert repo.get_case("case-100028")["status"] == "claim-matched"


def test_save_step_output_overwrites(tmp_path):
    repo = make_repo(tmp_path)
    repo.save_step_output("case-100028", "ingest", '{"a": 1}')
    repo.save_step_output("case-100028", "ingest", '{"a": 2}')
    assert repo.get_step_output("case-100028", "ingest") == {"a": 2}


def test_reset_all_empties_every_table(tmp_path):
    repo = make_repo(tmp_path)
    repo.insert_remit_file("abc", "era.835", "processed", None, 1)
    repo.upsert_case("case-1", hospital_claim_id="HSP-1", status="new")
    repo.insert_audit_event(None, "ingest", "read file", {}, [], None)
    repo.reset_all()
    assert repo.list_cases() == []
    assert repo.list_events(None) == []
    assert repo.conn.execute("SELECT COUNT(*) c FROM remit_files").fetchone()["c"] == 0
