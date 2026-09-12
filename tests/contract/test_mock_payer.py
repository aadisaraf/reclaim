"""Contract tests for mocks/northstar/app.py, per
specs/001-denial-recovery/contracts/mock-northstar-payer.openapi.yaml (Appendix A6).

Runs the real ASGI app in-process via httpx.ASGITransport -- no real network, no real payer.
Uses the app's injectable clock (`set_now_fn`) and DEMO_TODAY override (`set_demo_today`)
instead of real sleeping or environment variables.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest

from mocks.northstar import app as payer_app
from reclaim.config import Settings

BASE_URL = "http://mock-northstar-health.example"

FIXED_NOW = datetime(2026, 9, 12, 18, 32, 0, tzinfo=timezone.utc)

APPEAL_BODY = {
    "payerClaimId": "PAYER-CLM-99281",
    "hospitalClaimId": "HSP-CLM-100028",
    "appealType": "reconsideration",
    "reasonCode": "CO-50",
    "letterDocumentId": "appeal-letter-100028",
    "attachments": [
        "note-progress-031",
        "treatment-note-022",
        "order-901",
        "policy-snapshot-NST-IMG-2026-04",
    ],
    "submittedBy": {"userId": "billing-approver-01", "role": "authorized-billing-user"},
}


@pytest.fixture(autouse=True)
def _reset_payer_state():
    payer_app.reset_state()
    payer_app.set_now_fn(lambda: FIXED_NOW)
    payer_app.set_demo_today(None)
    yield
    payer_app.reset_state()
    payer_app.reset_now_fn()
    payer_app.set_demo_today(None)


@pytest.fixture
def settings() -> Settings:
    return Settings.from_env()


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=payer_app.app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as c:
        yield c


def _auth_headers(settings: Settings) -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.payer_token}"}


async def _upload_all_appeal_documents(client: httpx.AsyncClient, settings: Settings) -> None:
    uploads = [
        ("appeal-letter-100028", "appeal-letter", b"SYNTHETIC DEMO DATA - appeal letter"),
        ("note-progress-031", "clinical-note", b"SYNTHETIC DEMO DATA - progress note"),
        ("treatment-note-022", "clinical-note", b"SYNTHETIC DEMO DATA - PT discharge summary"),
        ("order-901", "order", b"SYNTHETIC DEMO DATA - order"),
        ("policy-snapshot-NST-IMG-2026-04", "policy-snapshot", b"SYNTHETIC DEMO DATA - policy snapshot"),
    ]
    for document_id, document_type, content in uploads:
        resp = await client.post(
            "/api/v1/documents",
            data={
                "documentId": document_id,
                "documentType": document_type,
                "relatedPayerClaimId": "PAYER-CLM-99281",
            },
            files={"file": ("file.bin", content, "application/octet-stream")},
            headers=_auth_headers(settings),
        )
        assert resp.status_code == 201, resp.text


# --- decision ------------------------------------------------------------------------------


async def test_get_decision_success(client: httpx.AsyncClient, settings: Settings):
    resp = await client.get("/api/v1/claims/PAYER-CLM-99281/decision", headers=_auth_headers(settings))
    assert resp.status_code == 200
    assert resp.json() == payer_app.decision


async def test_get_decision_unauthorized(client: httpx.AsyncClient):
    resp = await client.get("/api/v1/claims/PAYER-CLM-99281/decision")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"

    resp2 = await client.get(
        "/api/v1/claims/PAYER-CLM-99281/decision", headers={"Authorization": "Bearer wrong-token"}
    )
    assert resp2.status_code == 401


async def test_get_decision_unknown_claim(client: httpx.AsyncClient, settings: Settings):
    resp = await client.get("/api/v1/claims/PAYER-CLM-00000/decision", headers=_auth_headers(settings))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "claim_not_found"


# --- documents -----------------------------------------------------------------------------


async def test_get_denial_letter_pdf(client: httpx.AsyncClient, settings: Settings):
    resp = await client.get("/api/v1/documents/denial-letter-99281", headers=_auth_headers(settings))
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


async def test_get_document_unknown_returns_404(client: httpx.AsyncClient, settings: Settings):
    resp = await client.get("/api/v1/documents/unknown-doc", headers=_auth_headers(settings))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "document_not_found"


async def test_upload_document_lifecycle(client: httpx.AsyncClient, settings: Settings):
    headers = _auth_headers(settings)
    payload = {
        "documentId": "note-progress-031",
        "documentType": "clinical-note",
        "relatedPayerClaimId": "PAYER-CLM-99281",
    }

    created = await client.post(
        "/api/v1/documents", data=payload, files={"file": ("f.txt", b"hello", "text/plain")}, headers=headers
    )
    assert created.status_code == 201
    assert created.json() == {"documentId": "note-progress-031"}

    same_bytes = await client.post(
        "/api/v1/documents", data=payload, files={"file": ("f.txt", b"hello", "text/plain")}, headers=headers
    )
    assert same_bytes.status_code == 200
    assert same_bytes.json() == {"documentId": "note-progress-031"}

    different_bytes = await client.post(
        "/api/v1/documents", data=payload, files={"file": ("f.txt", b"goodbye", "text/plain")}, headers=headers
    )
    assert different_bytes.status_code == 409
    assert different_bytes.json()["error"]["code"] == "document_conflict"

    bad_type = await client.post(
        "/api/v1/documents",
        data={**payload, "documentType": "not-a-real-type"},
        files={"file": ("f.txt", b"hello", "text/plain")},
        headers=headers,
    )
    assert bad_type.status_code == 400
    assert bad_type.json()["error"]["code"] == "invalid_request"

    fetched = await client.get("/api/v1/documents/note-progress-031", headers=headers)
    assert fetched.status_code == 200
    assert fetched.content == b"hello"


# --- appeals ---------------------------------------------------------------------------------


async def test_create_appeal_happy_path_matches_fixture(client: httpx.AsyncClient, settings: Settings):
    await _upload_all_appeal_documents(client, settings)
    headers = {**_auth_headers(settings), "Idempotency-Key": "appeal-case-100028-v1"}

    resp = await client.post("/api/v1/appeals", json=APPEAL_BODY, headers=headers)
    assert resp.status_code == 201
    assert resp.json() == {
        "appealId": "NST-APL-80126",
        "status": "received",
        "receivedAt": "2026-09-12T18:32:00Z",
        "expectedResolutionDays": 14,
    }


async def test_create_appeal_replay_same_key_same_body(client: httpx.AsyncClient, settings: Settings):
    await _upload_all_appeal_documents(client, settings)
    headers = {**_auth_headers(settings), "Idempotency-Key": "appeal-case-100028-v1"}

    first = await client.post("/api/v1/appeals", json=APPEAL_BODY, headers=headers)
    assert first.status_code == 201

    replay = await client.post("/api/v1/appeals", json=APPEAL_BODY, headers=headers)
    assert replay.status_code == 200
    assert replay.headers["Idempotent-Replayed"] == "true"
    assert replay.json() == first.json()


async def test_create_appeal_same_key_different_body_conflict(client: httpx.AsyncClient, settings: Settings):
    await _upload_all_appeal_documents(client, settings)
    headers = {**_auth_headers(settings), "Idempotency-Key": "appeal-case-100028-v1"}

    first = await client.post("/api/v1/appeals", json=APPEAL_BODY, headers=headers)
    assert first.status_code == 201

    different_body = {**APPEAL_BODY, "reasonCode": "CO-99"}
    conflict = await client.post("/api/v1/appeals", json=different_body, headers=headers)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_key_reused"


async def test_create_appeal_missing_upload_returns_unknown_attachment(
    client: httpx.AsyncClient, settings: Settings
):
    # None of the 5 documents uploaded this time.
    headers = {**_auth_headers(settings), "Idempotency-Key": "appeal-case-missing-docs"}
    resp = await client.post("/api/v1/appeals", json=APPEAL_BODY, headers=headers)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "unknown_attachment"


async def test_create_appeal_after_deadline_returns_appeal_window_closed(
    client: httpx.AsyncClient, settings: Settings
):
    await _upload_all_appeal_documents(client, settings)
    payer_app.set_demo_today("2026-10-20")
    headers = {**_auth_headers(settings), "Idempotency-Key": "appeal-case-late"}

    resp = await client.post("/api/v1/appeals", json=APPEAL_BODY, headers=headers)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "appeal_window_closed"


async def test_create_appeal_unknown_claim_returns_404(client: httpx.AsyncClient, settings: Settings):
    await _upload_all_appeal_documents(client, settings)
    headers = {**_auth_headers(settings), "Idempotency-Key": "appeal-case-unknown-claim"}
    body = {**APPEAL_BODY, "payerClaimId": "PAYER-CLM-00000"}

    resp = await client.post("/api/v1/appeals", json=body, headers=headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "claim_not_found"


async def test_create_appeal_missing_idempotency_key_returns_400(client: httpx.AsyncClient, settings: Settings):
    resp = await client.post("/api/v1/appeals", json=APPEAL_BODY, headers=_auth_headers(settings))
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_request"


async def test_get_appeal_transitions_to_in_review_after_30_seconds(
    client: httpx.AsyncClient, settings: Settings
):
    await _upload_all_appeal_documents(client, settings)
    headers = {**_auth_headers(settings), "Idempotency-Key": "appeal-case-100028-v1"}
    created = await client.post("/api/v1/appeals", json=APPEAL_BODY, headers=headers)
    appeal_id = created.json()["appealId"]

    received = await client.get(f"/api/v1/appeals/{appeal_id}", headers=_auth_headers(settings))
    assert received.status_code == 200
    assert received.json()["status"] == "received"

    payer_app.set_now_fn(lambda: FIXED_NOW + timedelta(seconds=30))
    in_review = await client.get(f"/api/v1/appeals/{appeal_id}", headers=_auth_headers(settings))
    assert in_review.status_code == 200
    assert in_review.json()["status"] == "in-review"
    assert in_review.json()["updatedAt"] == "2026-09-12T18:32:30Z"


async def test_get_appeal_unknown_id_returns_404(client: httpx.AsyncClient, settings: Settings):
    resp = await client.get("/api/v1/appeals/NST-APL-00000", headers=_auth_headers(settings))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "appeal_not_found"


# --- control ---------------------------------------------------------------------------------


async def test_control_reset_clears_appeals(client: httpx.AsyncClient, settings: Settings):
    await _upload_all_appeal_documents(client, settings)
    headers = {**_auth_headers(settings), "Idempotency-Key": "appeal-case-100028-v1"}
    created = await client.post("/api/v1/appeals", json=APPEAL_BODY, headers=headers)
    appeal_id = created.json()["appealId"]

    # No auth required on the demo-only reset endpoint.
    reset_resp = await client.post("/api/v1/_control/reset")
    assert reset_resp.status_code == 204

    after_reset = await client.get(f"/api/v1/appeals/{appeal_id}", headers=_auth_headers(settings))
    assert after_reset.status_code == 404

    # The static decision/letter fixtures survive the reset.
    decision_resp = await client.get("/api/v1/claims/PAYER-CLM-99281/decision", headers=_auth_headers(settings))
    assert decision_resp.status_code == 200
    letter_resp = await client.get("/api/v1/documents/denial-letter-99281", headers=_auth_headers(settings))
    assert letter_resp.status_code == 200
