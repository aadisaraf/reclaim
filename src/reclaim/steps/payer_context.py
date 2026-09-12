import hashlib
from datetime import date, timedelta

from pydantic import BaseModel

from reclaim.adapters.protocols import PayerDecision, PayerError
from reclaim.audit import write_event
from reclaim.models import Deadline, _fmt_date
from reclaim.repo import Repo


def compute_deadline(decision_date: str, appeal_deadline: str, window_days: int, today: str) -> Deadline:
    policy_window_date = date.fromisoformat(decision_date) + timedelta(days=window_days)
    policy_window_iso = policy_window_date.isoformat()
    days_left = (date.fromisoformat(appeal_deadline) - date.fromisoformat(today)).days
    warning = None
    if policy_window_iso != appeal_deadline:
        warning = (
            f"Payer deadline {_fmt_date(appeal_deadline)} differs from the policy window "
            f"date {_fmt_date(policy_window_iso)}."
        )
    return Deadline(
        deadline_of_record=appeal_deadline, policy_window_date=policy_window_iso,
        days_left=days_left, warning=warning,
    )


def deadline_line(deadline: Deadline) -> str:
    return deadline.line


class PayerContextResult(BaseModel):
    decision: PayerDecision | None = None
    deadline: Deadline | None = None
    policy_id: str | None = None
    policy_version: str | None = None


async def payer_context(ctx, case: dict) -> PayerContextResult:
    repo: Repo = ctx.repo
    settings = ctx.settings
    case_id = case["case_id"]

    evidence_output = repo.get_step_output(case_id, "gather_evidence") or {}
    policy_id = evidence_output.get("policy_id")
    policy_version = evidence_output.get("policy_version")
    appeal_window_days = evidence_output.get("appeal_window_days")

    try:
        decision = await ctx.payer_adapter.get_decision(case["payer_claim_id"])
    except PayerError as exc:
        if exc.status == 404:
            repo.update_case(case_id, status="needs-review", needs_review_field="payerClaimId")
            write_event(repo, settings, case_id, "payer_context", "Payer claim not found")
            return PayerContextResult()
        raise

    pdf_bytes = await ctx.payer_adapter.get_document(decision.letter["documentId"])
    repo.save_document(
        document_id=decision.letter["documentId"], case_id=case_id, document_type="denial-letter",
        content_type="application/pdf", content=pdf_bytes, sha256=hashlib.sha256(pdf_bytes).hexdigest(),
    )

    deadline = compute_deadline(
        decision_date=decision.decisionDate, appeal_deadline=decision.appealDeadline,
        window_days=appeal_window_days, today=settings.demo_today,
    )

    write_event(
        repo, settings, case_id, "payer_context",
        f"Payer decision: {decision.decision}, deadline {deadline.deadline_of_record} ({deadline.days_left} days left)",
    )
    return PayerContextResult(decision=decision, deadline=deadline, policy_id=policy_id, policy_version=policy_version)
