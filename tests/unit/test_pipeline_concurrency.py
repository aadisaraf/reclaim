"""T122: `run_case` gates concurrent case processing behind `asyncio.Semaphore(settings.llm_concurrency)`
(see `_get_semaphore` in src/reclaim/pipeline.py). This monkeypatches `reclaim.pipeline.STEPS` for
the duration of the test (never edits pipeline.py itself) to install fake steps that record
concurrency and per-case ordering, then restores both `STEPS` and the module-level semaphore
singleton afterwards so this test cannot leak state into any other test."""

import asyncio
import dataclasses

import pytest
from pydantic import BaseModel

import reclaim.pipeline as pipeline_mod
from reclaim.config import Settings
from reclaim.context import AppContext
from reclaim.pipeline import run_case

CASE_IDS = [f"case-conc-{i}" for i in range(6)]


class FakeStepResult(BaseModel):
    ok: bool = True


class ConcurrencyTracker:
    def __init__(self):
        self.current = 0
        self.max_seen = 0

    async def touch(self):
        self.current += 1
        self.max_seen = max(self.max_seen, self.current)
        await asyncio.sleep(0.05)
        self.current -= 1


@pytest.fixture
def _restore_pipeline_module():
    """Save/restore reclaim.pipeline's mutable module state around the test."""
    original_steps = pipeline_mod.STEPS
    original_semaphore = pipeline_mod._semaphore
    yield
    pipeline_mod.STEPS = original_steps
    pipeline_mod._semaphore = original_semaphore


def _seed_cases(repo):
    for case_id in CASE_IDS:
        repo.upsert_case(
            case_id, hospital_claim_id=f"HSP-{case_id}", lane="medical-necessity", status="new",
            payer_claim_id="PAYER-CLM-1", payer="Northstar Health", payer_id="NSTHLTH01",
            member_id="MEMBER-1", rendering_npi="1234567893", procedure_qualifier="HC",
            procedure_code="72148", date_of_service="20260810", denial_code="CO-50",
            denial_reason="Medical necessity", billed_amount=100.0, paid_amount=0.0, denied_amount=100.0,
        )


def _ctx(repo, settings):
    return AppContext(
        repo=repo, settings=settings, remit_inbox=None, claim_archive=None, ehr_client=None,
        policy_store=None, payer_adapter=None, llm_client=None,
    )


async def test_at_most_llm_concurrency_cases_run_at_once(repo, settings, _restore_pipeline_module):
    _seed_cases(repo)
    tracker = ConcurrencyTracker()

    async def fake_step(ctx, case):
        await tracker.touch()
        return FakeStepResult()

    pipeline_mod.STEPS = [("fake_step", fake_step)]
    pipeline_mod._semaphore = None  # force a fresh semaphore sized for this test's settings

    settings4 = dataclasses.replace(settings, llm_concurrency=4)
    ctx = _ctx(repo, settings4)

    await asyncio.gather(*(run_case(ctx, case_id) for case_id in CASE_IDS))

    assert tracker.max_seen <= 4
    assert tracker.max_seen == 4  # 6 cases contending for 4 slots should actually saturate it
    assert tracker.current == 0
    for case_id in CASE_IDS:
        case = repo.get_case(case_id)
        assert case["running"] == 0


async def test_steps_within_one_case_run_in_order(repo, settings, _restore_pipeline_module):
    _seed_cases(repo)
    order_log: dict[str, list[str]] = {case_id: [] for case_id in CASE_IDS}

    def make_step(label):
        async def step(ctx, case):
            order_log[case["case_id"]].append(label)
            await asyncio.sleep(0.01)
            return FakeStepResult()
        return step

    pipeline_mod.STEPS = [("first", make_step("first")), ("second", make_step("second"))]
    pipeline_mod._semaphore = None

    settings4 = dataclasses.replace(settings, llm_concurrency=4)
    ctx = _ctx(repo, settings4)

    await asyncio.gather(*(run_case(ctx, case_id) for case_id in CASE_IDS))

    for case_id in CASE_IDS:
        assert order_log[case_id] == ["first", "second"]
