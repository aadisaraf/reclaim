from pathlib import Path

REMIT_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "x12" / "era-2026-09-12.835"

_missing_evidence_enabled = False


async def simulate_remit(ctx) -> str:
    content = REMIT_FIXTURE.read_bytes()
    await ctx.remit_inbox.deliver(REMIT_FIXTURE.name, content)
    return REMIT_FIXTURE.name


def get_missing_evidence() -> bool:
    return _missing_evidence_enabled


def set_missing_evidence(enabled: bool) -> bool:
    global _missing_evidence_enabled
    _missing_evidence_enabled = enabled
    return _missing_evidence_enabled


async def reset_demo(ctx) -> None:
    ctx.repo.reset_all()
    await ctx.remit_inbox.clear()
    set_missing_evidence(False)
