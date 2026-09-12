from reclaim.context import AppContext
from reclaim.poller import _poll_once
from tests.fakes import FakeInbox


def _ctx(repo, settings, inbox):
    return AppContext(
        repo=repo, settings=settings, remit_inbox=inbox, claim_archive=None, ehr_client=None,
        policy_store=None, payer_adapter=None, llm_client=None,
    )


async def test_poll_once_ingests_new_file_and_schedules_case(repo, settings, fixtures_dir):
    inbox = FakeInbox()
    content = (fixtures_dir / "x12" / "era-2026-09-12.835").read_bytes()
    await inbox.deliver("era-2026-09-12.835", content)
    ctx = _ctx(repo, settings, inbox)
    seen: set[tuple[str, int, int]] = set()

    await _poll_once(ctx, seen)

    assert repo.get_case("case-100028") is not None
    assert len(seen) == 1


async def test_poll_once_skips_already_seen_file(repo, settings, fixtures_dir):
    inbox = FakeInbox()
    content = (fixtures_dir / "x12" / "era-2026-09-12.835").read_bytes()
    await inbox.deliver("era-2026-09-12.835", content)
    ctx = _ctx(repo, settings, inbox)
    seen: set[tuple[str, int, int]] = set()
    await _poll_once(ctx, seen)

    events_before = len(repo.list_events(None))
    await _poll_once(ctx, seen)
    events_after = len(repo.list_events(None))

    assert events_before == events_after
