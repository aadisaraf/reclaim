"""US6: polls the payer for a submitted case's appeal status.

`track(ctx, case)` finds the submitted appeal via the case's latest packet version -- the
submission row written by `approve_and_submit.py` is keyed by `appeal-<caseId>-v<version>`, so
`repo.latest_packet(case_id)["version"]` gives the version and `repo.get_submission(key)` gives
the `appeal_id`. If there is no packet, no submission row, or the submission has no
`appeal_id` yet (e.g. it was `refused`), this is a no-op: there is nothing to track.

It moves the case to `in-review` the first time the payer reports that, writing exactly one
audit event for that transition (data-model.md §4). Repeated polls that see no change write
nothing. `track_submitted_cases(ctx)` is the standalone poll-all helper `poller.py` should call
on a 5s interval for every case currently `submitted`.
"""

from __future__ import annotations

from pydantic import BaseModel

from reclaim.audit import write_event


class TrackResult(BaseModel):
    case_id: str
    appeal_id: str | None = None
    previous_status: str | None = None
    payer_status: str | None = None
    changed: bool = False


def _idempotency_key(case_id: str, version: int) -> str:
    return f"appeal-{case_id}-v{version}"


async def track(ctx, case: dict) -> TrackResult:
    repo = ctx.repo
    settings = ctx.settings
    case_id = case["case_id"]
    previous_status = case["status"]

    packet = repo.latest_packet(case_id)
    if packet is None:
        return TrackResult(case_id=case_id, previous_status=previous_status)

    idempotency_key = _idempotency_key(case_id, packet["version"])
    submission = repo.get_submission(idempotency_key)
    if submission is None or not submission.get("appeal_id"):
        return TrackResult(case_id=case_id, previous_status=previous_status)

    appeal_id = submission["appeal_id"]
    appeal_status = await ctx.payer_adapter.get_appeal(appeal_id)

    new_status = "in-review" if appeal_status.status == "in-review" else previous_status
    changed = new_status != previous_status

    repo.save_submission(idempotency_key, payer_status=appeal_status.status)

    if changed:
        repo.update_case(case_id, status=new_status)
        write_event(repo, settings, case_id, "track", f"Appeal {appeal_id} is now {appeal_status.status}")

    return TrackResult(
        case_id=case_id, appeal_id=appeal_id, previous_status=previous_status,
        payer_status=appeal_status.status, changed=changed,
    )


async def track_submitted_cases(ctx) -> None:
    """Standalone poll-all helper: calls `track` for every case currently `submitted`.

    Not wired into `poller.py` here -- that file is being edited concurrently. Add a 5s-
    interval call to this function there, e.g. alongside `run_inbox_poller`.
    """
    repo = ctx.repo
    for case in repo.list_cases():
        if case["status"] == "submitted":
            await track(ctx, case)
