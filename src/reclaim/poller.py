import asyncio

from reclaim.pipeline import run_case
from reclaim.steps.ingest import ingest
from reclaim.steps.track import track_submitted_cases


async def _poll_once(ctx, seen: set[tuple[str, int, int]]) -> None:
    files = await ctx.remit_inbox.list_files()
    for f in files:
        key = (f.name, f.size, f.mtime)
        if key in seen:
            continue
        seen.add(key)
        content = await ctx.remit_inbox.download(f.name)
        result = ingest(ctx.repo, ctx.settings, f.name, content)
        for case_id in result.new_case_ids:
            asyncio.create_task(run_case(ctx, case_id))


async def run_inbox_poller(ctx, interval: float = 1.0) -> None:
    while True:
        await _poll_once(ctx, ctx.poller_seen)
        await asyncio.sleep(interval)


async def run_tracking_poller(ctx, interval: float = 5.0) -> None:
    while True:
        await track_submitted_cases(ctx)
        await asyncio.sleep(interval)
