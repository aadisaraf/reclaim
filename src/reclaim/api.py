import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response

from reclaim import demo
from reclaim.adapters.llm import cost_usd
from reclaim.adapters.protocols import LlmUsage
from reclaim.context import AppContext
from reclaim.models import Deadline, Policy
from reclaim.steps.approve_and_submit import (
    CaseNotFoundError,
    NotReadyError,
    StaleVersionError,
    WrongRoleError,
    approve_and_submit,
)

router = APIRouter()

PERSONAS = [
    {"userId": "billing-approver-01", "role": "authorized-billing-user", "canApprove": True},
    {"userId": "viewer-01", "role": "viewer", "canApprove": False},
]

STATUS_LINES = {
    "new": "New",
    "claim-matched": "Claim matched",
    "needs-review": "Needs review",
    "evidence-gathered": "Evidence gathered",
    "needs-evidence": "Needs evidence",
    "ready-for-review": "Ready for review",
    "approved": "Approved",
    "submitted": "Submitted",
    "in-review": "In review",
    "paid": "Paid",
    "other-denial": "Other denial lane: not handled in this demo",
}

RERUN_BLOCKED_STATUSES = {"approved", "submitted", "in-review", "paid", "other-denial"}


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx


def _not_found(case_id: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"error": {"code": "not_found", "message": f"No case {case_id}"}},
    )


@router.get("/api/health")
def health() -> dict:
    return {"ok": True}


@router.get("/api/config")
def get_config(ctx: AppContext = Depends(get_ctx)) -> dict:
    settings = ctx.settings
    config = settings.public()
    config["synthetic"] = True
    config["missingEvidence"] = demo.get_missing_evidence()
    config["baseUrls"]["clearinghouse"] = f"sftp://{settings.sftp_host}:{settings.sftp_port}"
    return config


@router.get("/api/personas")
def list_personas() -> list[dict]:
    return PERSONAS


@router.get("/api/queue")
def get_queue(ctx: AppContext = Depends(get_ctx)) -> dict:
    repo = ctx.repo
    cases = repo.list_cases()
    medical = [c for c in cases if c["lane"] == "medical-necessity"]
    paid = [c for c in cases if c["lane"] == "paid"]
    other = [c for c in cases if c["lane"] == "other-denial"]

    case_list = [
        {
            "caseId": c["case_id"],
            "headline": (
                f"{c['payer'].title()} · {c['denial_code']} {c['denial_reason']} · "
                f"${c['denied_amount']:,.0f}"
            ),
            "status": c["status"],
            "running": bool(c["running"]),
        }
        for c in medical
    ]

    lines: list[str] = []
    if len(paid) > 0:
        n = len(paid)
        lines.append(f"{n} paid claim{'s' if n != 1 else ''}, no action")
    if len(other) > 0:
        n = len(other)
        lines.append(f"{n} other denial lane{'s' if n != 1 else ''}: not handled in this demo")

    summary = {"paidClaims": len(paid), "otherDenials": len(other), "lines": lines}

    other_lane = [
        {
            "caseId": c["case_id"],
            "hospitalClaimId": c["hospital_claim_id"],
            "denialCode": c["denial_code"],
            "amount": c["denied_amount"],
            "label": "Other denial lane: not handled in this demo",
        }
        for c in other
    ]

    remit_files = [
        {"fileName": r["file_name"], "status": r["status"], "claimCount": r["claim_count"]}
        for r in repo.list_remit_files()
    ]

    return {"cases": case_list, "summary": summary, "otherLane": other_lane, "remitFiles": remit_files}


@router.post("/api/demo/simulate-remit", status_code=202)
async def simulate_remit_endpoint(ctx: AppContext = Depends(get_ctx)) -> dict:
    filename = await demo.simulate_remit(ctx)
    return {"delivered": filename}


def _sum_llm_usage(events: list[dict]) -> LlmUsage:
    input_tokens = cached_tokens = output_tokens = reasoning_tokens = 0
    for event in events:
        raw = event.get("llm_usage_json")
        if not raw:
            continue
        usage_data = json.loads(raw)
        for call in usage_data.get("calls", []):
            input_tokens += call.get("input_tokens", 0)
            cached_tokens += call.get("cached_tokens", 0)
            output_tokens += call.get("output_tokens", 0)
            reasoning_tokens += call.get("reasoning_tokens", 0)
    return LlmUsage(
        input_tokens=input_tokens, cached_tokens=cached_tokens,
        output_tokens=output_tokens, reasoning_tokens=reasoning_tokens,
    )


def _submission_display(submission: dict) -> str | None:
    if submission["status"] != "confirmed" or not submission["appeal_id"]:
        return None
    return (
        f"Submitted · Northstar confirmation {submission['appeal_id']} "
        f"· expected resolution {submission['expected_resolution_days']} days"
    )


@router.get("/api/cases/{case_id}")
def get_case_detail(case_id: str, ctx: AppContext = Depends(get_ctx)) -> dict:
    repo = ctx.repo
    case = repo.get_case(case_id)
    if case is None:
        raise _not_found(case_id)

    running = bool(case["running"])
    status_line = STATUS_LINES.get(case["status"], case["status"])

    identity_output = repo.get_step_output(case_id, "resolve_identity") or {}
    claim_map_entry = identity_output.get("claim_map_entry")
    chain = [case["hospital_claim_id"], f"837 {case['hospital_claim_id']}"]
    if claim_map_entry:
        chain.append(claim_map_entry["encounterId"])
    identity = {"chain": chain, "checks": identity_output.get("checks", [])}

    evidence_output = repo.get_step_output(case_id, "gather_evidence") or {}
    evidence_set = evidence_output.get("evidence_set")
    if evidence_set:
        items = evidence_set["items"]
        excluded_count = evidence_set["excluded_count"]
        search_counts = evidence_set["search_counts"]
    else:
        items, excluded_count, search_counts = [], 0, {}
    excluded_line = f"{excluded_count} record{'s' if excluded_count != 1 else ''} excluded (outside 6-month lookback)"
    evidence = {"items": items, "excludedLine": excluded_line, "searchCounts": search_counts}

    payer_output = repo.get_step_output(case_id, "payer_context") or {}
    payer_decision = payer_output.get("decision")

    policy_id = evidence_output.get("policy_id") or payer_output.get("policy_id")
    policy_version = evidence_output.get("policy_version") or payer_output.get("policy_version")
    policy = None
    if policy_id and policy_version:
        title = Policy.model_validate_json(
            ctx.policy_store.snapshot_bytes(policy_id, policy_version)
        ).title
        policy = {"label": f"Policy {policy_id} v{policy_version}", "title": title}

    deadline_dict = payer_output.get("deadline")
    deadline = None
    if deadline_dict:
        deadline = {
            "line": Deadline.model_validate(deadline_dict).line,
            "warning": deadline_dict.get("warning"),
        }

    matrix_output = repo.get_step_output(case_id, "build_matrix") or {}
    matrix = matrix_output.get("matrix")

    completeness_line = None
    if matrix and matrix.get("summary"):
        summary = matrix["summary"]
        completeness_line = f"Evidence completeness: {summary['satisfied']}/{summary['total']} policy criteria satisfied"

    recovery_line = f"Expected recovery: ${case['denied_amount']:,.0f}"

    latest_packet = repo.latest_packet(case_id)
    packet = None
    submission = None
    if latest_packet:
        letter_data = json.loads(latest_packet["letter_json"])
        if latest_packet["status"] == "blocked":
            packet = {
                "version": latest_packet["version"],
                "status": latest_packet["status"],
                "blockedReason": latest_packet["blocked_reason"],
                "header": None,
                "statements": letter_data.get("statements"),
                "attachments": None,
                "requestedAction": None,
                "requiredApprover": None,
                "footer": None,
            }
        else:
            packet = {
                "version": latest_packet["version"],
                "status": latest_packet["status"],
                "blockedReason": None,
                "header": letter_data["header"],
                "statements": [
                    {
                        "statementId": s["statement_id"],
                        "text": s["text"],
                        "requirementIds": s["requirement_ids"],
                        "citationIds": s["citation_ids"],
                    }
                    for s in letter_data["body"]
                ],
                "attachments": letter_data["attachments"],
                "requestedAction": letter_data["requested_action"],
                "requiredApprover": letter_data["required_approver"],
                "footer": letter_data["footer"],
            }

        submission_row = repo.get_submission(f"appeal-{case_id}-v{latest_packet['version']}")
        if submission_row:
            submission = {
                "idempotencyKey": submission_row["idempotency_key"],
                "status": submission_row["status"],
                "appealId": submission_row["appeal_id"],
                "expectedResolutionDays": submission_row["expected_resolution_days"],
                "payerStatus": submission_row["payer_status"],
                "errorCode": submission_row["error_code"],
                "errorMessage": submission_row["error_message"],
                "display": _submission_display(submission_row),
            }

    events = repo.list_events(case_id)
    usage = _sum_llm_usage(events)
    usd = cost_usd(usage, ctx.settings)
    ai_cost = {
        "inputTokens": usage.input_tokens,
        "cachedTokens": usage.cached_tokens,
        "outputTokens": usage.output_tokens,
        "reasoningTokens": usage.reasoning_tokens,
        "usd": round(usd, 4),
        "line": f"AI cost for this case (estimate): ${usd:.4f}",
    }

    if running:
        rerun_unavailable_reason = "Case is currently running"
    elif case["status"] in RERUN_BLOCKED_STATUSES:
        rerun_unavailable_reason = f"A case in status {case['status']} cannot be re-run. Reset the demo first."
    else:
        rerun_unavailable_reason = None
    actions = {
        "canRerun": case["status"] not in RERUN_BLOCKED_STATUSES and not running,
        "rerunUnavailableReason": rerun_unavailable_reason,
        "canApprove": bool(latest_packet) and latest_packet["status"] == "ready-for-review"
        and case["status"] == "ready-for-review",
    }

    timeline = [
        {
            "step": e["step"],
            "summary": e["summary"],
            "ehrRequests": json.loads(e["ehr_requests_json"] or "[]"),
            "llmUsage": json.loads(e["llm_usage_json"]) if e["llm_usage_json"] else None,
            "createdAt": e["created_at"],
        }
        for e in events
    ]

    return {
        "case": case,
        "running": running,
        "statusLine": status_line,
        "identity": identity,
        "evidence": evidence,
        "payerDecision": payer_decision,
        "policy": policy,
        "deadline": deadline,
        "matrix": matrix,
        "completenessLine": completeness_line,
        "needsLine": None,
        "recoveryLine": recovery_line,
        "tasks": [],
        "packet": packet,
        "submission": submission,
        "aiCost": ai_cost,
        "actions": actions,
        "timeline": timeline,
    }


@router.get("/api/cases/{case_id}/packets/{version}/pdf")
def get_packet_pdf(case_id: str, version: int, ctx: AppContext = Depends(get_ctx)) -> Response:
    packet = ctx.repo.get_packet(case_id, version)
    if packet is None or packet["pdf"] is None:
        raise _not_found(f"{case_id} packet v{version} pdf")
    return Response(content=packet["pdf"], media_type="application/pdf")


@router.get("/api/cases/{case_id}/documents/{document_id}")
def get_case_document(case_id: str, document_id: str, ctx: AppContext = Depends(get_ctx)) -> Response:
    doc = ctx.repo.get_document(document_id)
    if doc is None or doc["case_id"] != case_id:
        raise _not_found(f"{case_id} document {document_id}")
    return Response(content=doc["bytes"], media_type=doc["content_type"])


@router.post("/api/cases/{case_id}/packets/{version}/approve-and-submit")
async def approve_and_submit_endpoint(
    case_id: str, version: int, x_persona: str = Header(...), ctx: AppContext = Depends(get_ctx)
) -> dict:
    persona = next((p for p in PERSONAS if p["userId"] == x_persona), None)
    try:
        result = await approve_and_submit(ctx, case_id, version, persona)
    except WrongRoleError as exc:
        raise HTTPException(403, detail={"error": {"code": "wrong_role", "message": str(exc)}}) from exc
    except CaseNotFoundError:
        raise _not_found(case_id) from None
    except StaleVersionError as exc:
        raise HTTPException(
            409, detail={"error": {"code": "not_latest_version", "message": str(exc)}}
        ) from exc
    except NotReadyError as exc:
        raise HTTPException(
            409, detail={"error": {"code": "not_ready_for_review", "message": str(exc)}}
        ) from exc

    if result.outcome == "refused":
        raise HTTPException(
            422,
            detail={
                "error": {
                    "code": "payer_refused",
                    "message": f"{result.payer_error_code}: {result.payer_error_message}",
                }
            },
        )

    submission_row = ctx.repo.get_submission(f"appeal-{case_id}-v{version}")
    return {
        "idempotencyKey": submission_row["idempotency_key"],
        "status": submission_row["status"],
        "appealId": result.appeal_id,
        "expectedResolutionDays": result.expected_resolution_days,
        "payerStatus": submission_row["payer_status"],
        "errorCode": None,
        "errorMessage": None,
        "display": result.display,
    }
