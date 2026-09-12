import asyncio

from reclaim.audit import write_event
from reclaim.steps.build_matrix import build_matrix
from reclaim.steps.draft_packet import draft_packet
from reclaim.steps.fetch_claim import fetch_claim
from reclaim.steps.gather_evidence import gather_evidence
from reclaim.steps.payer_context import payer_context
from reclaim.steps.resolve_identity import resolve_identity

STEPS: list[tuple[str, object]] = [
    ("fetch_claim", fetch_claim),
    ("resolve_identity", resolve_identity),
    ("gather_evidence", gather_evidence),
    ("payer_context", payer_context),
    ("build_matrix", build_matrix),
    ("draft_packet", draft_packet),
]

CONTINUE_STATUSES = {"new", "claim-matched", "evidence-gathered"}

_semaphore: asyncio.Semaphore | None = None


def _get_semaphore(concurrency: int) -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(concurrency)
    return _semaphore


async def run_case(ctx, case_id: str) -> None:
    repo = ctx.repo
    async with _get_semaphore(ctx.settings.llm_concurrency):
        repo.update_case(case_id, running=1)
        try:
            for step_name, step_fn in STEPS:
                case = repo.get_case(case_id)
                try:
                    result = await step_fn(ctx, case)
                    repo.save_step_output(case_id, step_name, result.model_dump_json())
                except Exception as exc:
                    repo.update_case(case_id, last_error=str(exc))
                    write_event(repo, ctx.settings, case_id, step_name, f"Error in {step_name}: {exc}")
                    break
                if repo.get_case(case_id)["status"] not in CONTINUE_STATUSES:
                    break
        finally:
            repo.update_case(case_id, running=0)


async def rerun_case(ctx, case_id: str) -> None:
    ctx.repo.update_case(case_id, status="new", last_error=None, needs_review_field=None)
    await run_case(ctx, case_id)
