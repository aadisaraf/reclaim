"""US6: role-checked approval of one packet version, then upload + idempotent submission.

Outcome contract for `api.py` (T100, not implemented here):
  - `WrongRoleError`   -> persona missing/unrecognized, or role != "authorized-billing-user".
                          No case/packet lookup happens, no payer call is made, and exactly
                          one refusal audit event is written. Map to HTTP 403.
  - `CaseNotFoundError` -> unknown `case_id`. Map to HTTP 404.
  - `StaleVersionError` -> `version` isn't the case's latest packet version. Map to HTTP 409.
  - `NotReadyError`     -> packet/case isn't `ready-for-review`, or a matrix requirement isn't
                          `satisfied`. Map to HTTP 409.
  - Returns `ApproveAndSubmitResult(outcome="submitted", ...)` when the payer accepts the
    appeal (a fresh 201, or an idempotent-replayed 200 on a repeat call for the same version).
  - Returns `ApproveAndSubmitResult(outcome="refused", payer_error_code=..., ...)` when the
    payer returns a business-rule 4xx (e.g. `appeal_window_closed`). This is an expected
    business outcome, not a system error, so nothing is raised for it -- api.py can map
    `payer_error_code` to 422. `result.display` is always `None` for this outcome and no
    audit event written along this path contains the word "Submitted" (FR-032).

A case already `approved` or `submitted` for the *same* `version` is treated as an idempotent
retry: the one-time approval bookkeeping/audit event is skipped, but documents are
re-uploaded (harmless -- the payer's own upload endpoint returns 200, not 201, for identical
bytes) and `create_appeal` is called again with the same `Idempotency-Key`, which the payer
replays rather than creating a second appeal.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel

from reclaim.adapters.protocols import AppealRequest, PayerError, SubmittedBy
from reclaim.audit import write_event
from reclaim.models import Letter

AUTHORIZED_ROLE = "authorized-billing-user"

# A case in one of these statuses may (re-)run the upload+submit flow: freshly ready for a
# human decision, or already approved/submitted for this same version (an idempotent retry).
_SUBMITTABLE_CASE_STATUSES = {"ready-for-review", "approved", "submitted"}


class WrongRoleError(Exception):
    """Persona is missing, unrecognized, or its role isn't `authorized-billing-user`."""


class CaseNotFoundError(Exception):
    """`case_id` does not exist."""


class StaleVersionError(Exception):
    """`version` is not the case's latest packet version."""


class NotReadyError(Exception):
    """The packet/case isn't `ready-for-review`, or a matrix requirement isn't `satisfied`."""


class ApproveAndSubmitResult(BaseModel):
    case_id: str
    version: int
    outcome: Literal["submitted", "refused"]
    appeal_id: str | None = None
    expected_resolution_days: int | None = None
    display: str | None = None
    payer_error_code: str | None = None
    payer_error_message: str | None = None


def _letter_document_id(hospital_claim_id: str) -> str:
    # Matches src/reclaim/steps/draft_packet.py's own derivation exactly (same suffix split),
    # so the id this step uploads under is always the id draft_packet actually saved under.
    # Hero: HSP-CLM-100028 -> appeal-letter-100028 (Appendix A6/A8).
    return f"appeal-letter-{hospital_claim_id.split('-')[-1]}"


def _idempotency_key(case_id: str, version: int) -> str:
    return f"appeal-{case_id}-v{version}"


async def approve_and_submit(ctx, case_id: str, version: int, persona: dict | None) -> ApproveAndSubmitResult:
    repo = ctx.repo
    settings = ctx.settings

    user_id = (persona or {}).get("userId") or "unknown"
    role = (persona or {}).get("role")

    if role != AUTHORIZED_ROLE:
        write_event(
            repo, settings, case_id, "approve_and_submit",
            f"Refused approval: persona {user_id} has role {role or 'unknown'}, not {AUTHORIZED_ROLE}",
        )
        raise WrongRoleError(f"persona {user_id!r} has role {role!r}, not {AUTHORIZED_ROLE!r}")

    case = repo.get_case(case_id)
    if case is None:
        raise CaseNotFoundError(f"no case {case_id}")

    latest_packet = repo.latest_packet(case_id)
    if latest_packet is None or latest_packet["version"] != version:
        latest_version = latest_packet["version"] if latest_packet else None
        write_event(
            repo, settings, case_id, "approve_and_submit",
            f"Refused approval: requested version {version}, latest is {latest_version}",
        )
        raise StaleVersionError(f"requested version {version}, latest packet version is {latest_version}")

    if latest_packet["status"] != "ready-for-review":
        write_event(
            repo, settings, case_id, "approve_and_submit",
            f"Refused approval: packet v{version} status is {latest_packet['status']}, not ready-for-review",
        )
        raise NotReadyError(f"packet v{version} is {latest_packet['status']!r}, not ready-for-review")

    if case["status"] not in _SUBMITTABLE_CASE_STATUSES:
        write_event(
            repo, settings, case_id, "approve_and_submit",
            f"Refused approval: case status is {case['status']}, not ready-for-review",
        )
        raise NotReadyError(f"case status is {case['status']!r}, not ready-for-review")

    matrix_output = repo.get_step_output(case_id, "build_matrix") or {}
    rows = (matrix_output.get("matrix") or {}).get("requirements") or []
    unsatisfied = [r["requirement_id"] for r in rows if r.get("status") != "satisfied"]
    if not rows or unsatisfied:
        write_event(
            repo, settings, case_id, "approve_and_submit",
            f"Refused approval: requirement(s) not satisfied: {unsatisfied or '<no matrix>'}",
        )
        raise NotReadyError(f"requirement(s) not satisfied: {unsatisfied or '<no matrix>'}")

    if case["status"] == "ready-for-review":
        repo.update_case(case_id, status="approved")
        write_event(repo, settings, case_id, "approve_and_submit", f"Approved by {user_id} ({role})")

    letter = Letter.model_validate(json.loads(latest_packet["letter_json"]))
    letter_document_id = _letter_document_id(case["hospital_claim_id"])
    upload_ids = [letter_document_id, *letter.attachments]

    for document_id in upload_ids:
        doc = repo.get_document(document_id)
        if doc is None:
            raise NotReadyError(f"document {document_id} has not been drafted yet")
        await ctx.payer_adapter.upload_document(
            document_id=document_id, document_type=doc["document_type"],
            related_payer_claim_id=case["payer_claim_id"],
            content=doc["bytes"], content_type=doc["content_type"],
        )

    request = AppealRequest(
        payerClaimId=case["payer_claim_id"], hospitalClaimId=case["hospital_claim_id"],
        reasonCode=case["denial_code"], letterDocumentId=letter_document_id,
        attachments=list(letter.attachments), submittedBy=SubmittedBy(userId=user_id, role=role),
    )
    idempotency_key = _idempotency_key(case_id, version)
    request_sha256 = hashlib.sha256(json.dumps(request.model_dump(), sort_keys=True).encode()).hexdigest()

    try:
        receipt = await ctx.payer_adapter.create_appeal(request, idempotency_key=idempotency_key)
    except PayerError as exc:
        repo.save_submission(
            idempotency_key, case_id=case_id, version=version, request_sha256=request_sha256,
            status="refused", appeal_id=None, received_at=None, expected_resolution_days=None,
            payer_status=None, error_code=exc.code, error_message=exc.message,
        )
        write_event(
            repo, settings, case_id, "approve_and_submit",
            f"Payer refused the appeal: {exc.code} ({exc.message})",
            detail={"code": exc.code, "message": exc.message},
        )
        return ApproveAndSubmitResult(
            case_id=case_id, version=version, outcome="refused",
            payer_error_code=exc.code, payer_error_message=exc.message,
        )

    repo.save_submission(
        idempotency_key, case_id=case_id, version=version, request_sha256=request_sha256,
        status="confirmed", appeal_id=receipt.appeal_id, received_at=receipt.received_at,
        expected_resolution_days=receipt.expected_resolution_days, payer_status=receipt.status,
        error_code=None, error_message=None,
    )
    repo.update_case(case_id, status="submitted")
    display = (
        f"Submitted · Northstar confirmation {receipt.appeal_id} "
        f"· expected resolution {receipt.expected_resolution_days} days"
    )
    replay_note = " (idempotent replay)" if receipt.replayed else ""
    write_event(
        repo, settings, case_id, "approve_and_submit",
        f"Submitted appeal {receipt.appeal_id}, expected resolution {receipt.expected_resolution_days} days"
        + replay_note,
    )
    return ApproveAndSubmitResult(
        case_id=case_id, version=version, outcome="submitted", appeal_id=receipt.appeal_id,
        expected_resolution_days=receipt.expected_resolution_days, display=display,
    )
