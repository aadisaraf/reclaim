import pytest

from reclaim.audit import list_events, write_event
from reclaim.config import Settings
from reclaim.repo import Repo


@pytest.fixture
def repo(tmp_path):
    r = Repo(str(tmp_path / "audit.db"))
    r.init_schema()
    return r


def test_write_event_stores_one_row(repo):
    settings = Settings()
    write_event(repo, settings, "case-100028", "ingest", "Read era.835: 1 claim.")
    events = list_events(repo, "case-100028")
    assert len(events) == 1
    assert events[0]["summary"] == "Read era.835: 1 claim."


def test_inbox_events_allow_none_case_id(repo):
    settings = Settings()
    write_event(repo, settings, None, "ingest", "Polled inbox: 0 new files.")
    events = list_events(repo, None)
    assert len(events) == 1


def test_list_events_insertion_order(repo):
    settings = Settings()
    write_event(repo, settings, "case-1", "ingest", "first")
    write_event(repo, settings, "case-1", "fetch_claim", "second")
    events = list_events(repo, "case-1")
    assert [e["summary"] for e in events] == ["first", "second"]


def test_write_event_raises_on_secret_leak(repo):
    settings = Settings(payer_token="super-secret-token")
    with pytest.raises(ValueError):
        write_event(repo, settings, "case-1", "payer_context", "token was super-secret-token")
