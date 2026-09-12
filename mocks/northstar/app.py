"""mock-northstar-health: a FastAPI mock of the Northstar Health payer API (SYNTHETIC DEMO DATA).

Implements Appendix A6 / `contracts/mock-northstar-payer.openapi.yaml` under `/api/v1`. All
data is in-memory and synthetic; there is no real payer behind this service. Every endpoint
except `POST /_control/reset` requires `Authorization: Bearer <token>` checked against
`Settings.payer_token` (never hard-coded here).

Two pieces of demo state are deliberately injectable so contract tests never need to sleep
or fiddle with real environment variables mid-run:
  - the clock (`now_fn`, set via `set_now_fn`) drives `receivedAt`/`updatedAt` and the
    received -> in-review transition;
  - `DEMO_TODAY` (set via `set_demo_today`) drives the appeal-window-closed check.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Body, FastAPI, File, Form, Header, UploadFile
from fastapi.responses import JSONResponse, Response

from reclaim.config import Settings

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "payer"

# `Settings.payer_base_url` (Appendix A6) is "https://mock-northstar-health.example/api/v1",
# matching a real payer's versioned REST API. Every route below is mounted under that same
# `/api/v1` prefix so a `NorthstarPayerAdapter` built from that base URL hits real paths.
router = APIRouter(prefix="/api/v1")

VALID_DOCUMENT_TYPES = {"appeal-letter", "clinical-note", "order", "policy-snapshot"}
REQUIRED_APPEAL_FIELDS = (
    "payerClaimId",
    "hospitalClaimId",
    "appealType",
    "reasonCode",
    "letterDocumentId",
    "attachments",
    "submittedBy",
)

app = FastAPI(
    title="mock-northstar-health",
    description="SYNTHETIC DEMO DATA -- mock of the Northstar Health payer API for the Reclaim hackathon demo.",
)

settings = Settings.from_env()

decision: dict[str, Any] = json.loads((FIXTURES_DIR / "payer-decision.json").read_text())
_appeal_response_fixture: dict[str, Any] = json.loads((FIXTURES_DIR / "appeal-response.json").read_text())
FIRST_APPEAL_ID: str = _appeal_response_fixture["appealId"]
EXPECTED_RESOLUTION_DAYS: int = _appeal_response_fixture["expectedResolutionDays"]

# Documents loaded from fixtures at startup and never cleared by `/_control/reset` (the
# contract's "keep the loaded decision/letter fixtures"), separate from documents uploaded
# during the demo via `POST /documents`, which reset *does* clear.
_STATIC_DOCUMENTS: dict[str, dict[str, Any]] = {
    "denial-letter-99281": {
        "bytes": (FIXTURES_DIR / "denial-letter.pdf").read_bytes(),
        "content_type": "application/pdf",
    }
}
documents: dict[str, dict[str, Any]] = {}
appeals: dict[str, dict[str, Any]] = {}
idempotency_records: dict[str, dict[str, Any]] = {}
_appeal_counter = 0


# --- injectable clock and DEMO_TODAY ------------------------------------------------------


def _default_now() -> datetime:
    return datetime.now(timezone.utc)


_now_fn: Callable[[], datetime] = _default_now


def set_now_fn(fn: Callable[[], datetime]) -> None:
    global _now_fn
    _now_fn = fn


def reset_now_fn() -> None:
    global _now_fn
    _now_fn = _default_now


def now() -> datetime:
    return _now_fn()


_demo_today_override: str | None = None


def set_demo_today(value: str | None) -> None:
    global _demo_today_override
    _demo_today_override = value


def get_demo_today() -> str:
    return _demo_today_override or settings.demo_today


def reset_state() -> None:
    """Clears uploaded documents, appeals, and idempotency records; keeps the loaded
    decision/letter fixtures. Used by `POST /_control/reset` and by tests for isolation.
    Does NOT touch the injected clock or DEMO_TODAY override -- callers reset those
    separately (tests typically want the clock reset once per test, not implicitly here)."""
    global _appeal_counter
    documents.clear()
    appeals.clear()
    idempotency_records.clear()
    _appeal_counter = 0


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get_document(document_id: str) -> dict[str, Any] | None:
    return documents.get(document_id) or _STATIC_DOCUMENTS.get(document_id)


def _error(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(content={"error": {"code": code, "message": message}}, status_code=status_code)


def _require_auth(authorization: str | None) -> JSONResponse | None:
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
    if not token or token != settings.payer_token:
        return _error("unauthorized", "Missing or invalid bearer token", 401)
    return None


def _next_appeal_id() -> str:
    global _appeal_counter
    if _appeal_counter == 0:
        appeal_id = FIRST_APPEAL_ID
    else:
        # Appendix A6 only fixes the id of the first appeal in the demo script; later
        # appeals (not exercised by the contract) get a simple synthetic suffix.
        appeal_id = f"{FIRST_APPEAL_ID}-{_appeal_counter}"
    _appeal_counter += 1
    return appeal_id


def _appeal_status_and_updated(appeal: dict[str, Any]) -> tuple[str, datetime]:
    received_at: datetime = appeal["receivedAt"]
    transition_at = received_at + timedelta(seconds=30)
    if now() >= transition_at:
        return "in-review", transition_at
    return "received", received_at


# --- claim decision + documents -----------------------------------------------------------


@router.get("/claims/{payer_claim_id}/decision")
async def get_decision(payer_claim_id: str, authorization: str | None = Header(None)):
    error = _require_auth(authorization)
    if error is not None:
        return error
    if payer_claim_id != decision["payerClaimId"]:
        return _error("claim_not_found", f"No claim {payer_claim_id}", 404)
    return JSONResponse(content=decision, status_code=200)


@router.get("/documents/{document_id}")
async def get_document(document_id: str, authorization: str | None = Header(None)):
    error = _require_auth(authorization)
    if error is not None:
        return error
    doc = _get_document(document_id)
    if doc is None:
        return _error("document_not_found", f"No document {document_id}", 404)
    return Response(content=doc["bytes"], media_type=doc["content_type"], status_code=200)


@router.post("/documents")
async def upload_document(
    documentId: str = Form(...),
    documentType: str = Form(...),
    relatedPayerClaimId: str = Form(...),
    file: UploadFile = File(...),
    authorization: str | None = Header(None),
):
    error = _require_auth(authorization)
    if error is not None:
        return error

    if documentType not in VALID_DOCUMENT_TYPES:
        return _error("invalid_request", f"Invalid documentType {documentType!r}", 400)

    file_bytes = await file.read()
    existing = _get_document(documentId)
    if existing is None:
        documents[documentId] = {
            "bytes": file_bytes,
            "content_type": file.content_type or "application/octet-stream",
            "documentType": documentType,
            "relatedPayerClaimId": relatedPayerClaimId,
        }
        return JSONResponse(content={"documentId": documentId}, status_code=201)

    if existing["bytes"] == file_bytes:
        return JSONResponse(content={"documentId": documentId}, status_code=200)

    return _error("document_conflict", f"Document {documentId} already exists with different content", 409)


# --- appeals --------------------------------------------------------------------------------


@router.post("/appeals")
async def create_appeal(
    payload: dict[str, Any] = Body(...),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    authorization: str | None = Header(None),
):
    # x-evaluation-order (from the contract): 401 auth; 400 schema/header; stored key with
    # same body -> 200 replay; stored key with different body -> 409; 404 claim; 422
    # appeal_window_closed; 422 unknown_attachment; 201.
    error = _require_auth(authorization)
    if error is not None:
        return error

    if not idempotency_key:
        return _error("invalid_request", "Missing Idempotency-Key header", 400)

    missing = [field for field in REQUIRED_APPEAL_FIELDS if field not in payload]
    if missing:
        return _error("invalid_request", f"Missing fields: {missing}", 400)

    body_key = json.dumps(payload, sort_keys=True)
    existing = idempotency_records.get(idempotency_key)
    if existing is not None:
        if existing["body_key"] == body_key:
            response = JSONResponse(content=existing["response_body"], status_code=200)
            response.headers["Idempotent-Replayed"] = "true"
            return response
        return _error(
            "idempotency_key_reused",
            f"Idempotency-Key {idempotency_key} was used with a different request body",
            409,
        )

    payer_claim_id = payload["payerClaimId"]
    if payer_claim_id != decision["payerClaimId"]:
        return _error("claim_not_found", f"No claim {payer_claim_id}", 404)

    if date.fromisoformat(get_demo_today()) > date.fromisoformat(decision["appealDeadline"]):
        return _error("appeal_window_closed", f"Appeal deadline {decision['appealDeadline']} has passed", 422)

    attachments_to_check = list(payload.get("attachments") or []) + [payload["letterDocumentId"]]
    for doc_id in attachments_to_check:
        if _get_document(doc_id) is None:
            return _error("unknown_attachment", f"Document {doc_id} has not been uploaded", 422)

    appeal_id = _next_appeal_id()
    received_at = now()
    response_body = {
        "appealId": appeal_id,
        "status": "received",
        "receivedAt": _iso(received_at),
        "expectedResolutionDays": EXPECTED_RESOLUTION_DAYS,
    }
    idempotency_records[idempotency_key] = {"body_key": body_key, "response_body": response_body}
    appeals[appeal_id] = {"receivedAt": received_at}
    return JSONResponse(content=response_body, status_code=201)


@router.get("/appeals/{appeal_id}")
async def get_appeal(appeal_id: str, authorization: str | None = Header(None)):
    error = _require_auth(authorization)
    if error is not None:
        return error
    appeal = appeals.get(appeal_id)
    if appeal is None:
        return _error("appeal_not_found", f"No appeal {appeal_id}", 404)
    status, updated_at = _appeal_status_and_updated(appeal)
    return JSONResponse(
        content={"appealId": appeal_id, "status": status, "updatedAt": _iso(updated_at)}, status_code=200
    )


# --- demo-only control ----------------------------------------------------------------------


@router.post("/_control/reset", status_code=204)
async def control_reset():
    # Deliberately unauthenticated: this is a demo-only reset hook (not in Appendix A6, and
    # not reachable in the real product, where there is no such endpoint on a real payer).
    # Requiring a token here would only make the demo harder to reset between scenarios for
    # no security benefit, since the whole service is synthetic.
    reset_state()
    return Response(status_code=204)


app.include_router(router)
