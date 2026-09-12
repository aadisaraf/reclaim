"""Contract tests for adapters/payer.py::NorthstarPayerAdapter against the real mock-northstar ASGI app."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from mocks.northstar import app as payer_app
from reclaim.adapters.payer import NorthstarPayerAdapter
from reclaim.adapters.protocols import AppealRequest, PayerError, SubmittedBy
from reclaim.config import Settings

BASE_URL = "http://mock-northstar-health.example/api/v1"
FIXED_NOW = datetime(2026, 9, 12, 18, 32, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _reset_payer_state():
    payer_app.reset_state()
    payer_app.set_now_fn(lambda: FIXED_NOW)
    yield
    payer_app.reset_state()
    payer_app.reset_now_fn()


@pytest.fixture
def settings() -> Settings:
    return Settings.from_env()


@pytest.fixture
def adapter(settings: Settings) -> NorthstarPayerAdapter:
    transport = httpx.ASGITransport(app=payer_app.app)
    return NorthstarPayerAdapter(base_url=BASE_URL, token=settings.payer_token, transport=transport)


def _appeal_request() -> AppealRequest:
    return AppealRequest(
        payerClaimId="PAYER-CLM-99281", hospitalClaimId="HSP-CLM-100028", reasonCode="CO-50",
        letterDocumentId="appeal-letter-100028",
        attachments=["note-progress-031", "treatment-note-022", "order-901", "policy-snapshot-NST-IMG-2026-04"],
        submittedBy=SubmittedBy(userId="billing-approver-01", role="authorized-billing-user"),
    )


async def _upload_appeal_attachments(adapter: NorthstarPayerAdapter) -> None:
    for doc_id in ["appeal-letter-100028", "note-progress-031", "treatment-note-022", "order-901",
                    "policy-snapshot-NST-IMG-2026-04"]:
        await adapter.upload_document(
            document_id=doc_id, document_type="clinical-note", related_payer_claim_id="PAYER-CLM-99281",
            content=f"content for {doc_id}".encode(), content_type="text/plain",
        )


async def test_get_decision_returns_a6_values(adapter: NorthstarPayerAdapter):
    decision = await adapter.get_decision("PAYER-CLM-99281")

    assert decision.decision == "denied"
    assert decision.decisionDate == "2026-08-20"
    assert decision.reasonCode == "CO-50"
    assert decision.appealDeadline == "2026-10-19"
    assert decision.allowedSubmissionChannels == ["portal", "fax"]
    assert decision.letter["documentId"] == "denial-letter-99281"


async def test_get_decision_unknown_claim_raises_not_found(adapter: NorthstarPayerAdapter):
    with pytest.raises(PayerError) as exc_info:
        await adapter.get_decision("PAYER-CLM-UNKNOWN")
    assert exc_info.value.status == 404
    assert exc_info.value.code == "claim_not_found"


async def test_get_document_returns_pdf_bytes(adapter: NorthstarPayerAdapter):
    pdf_bytes = await adapter.get_document("denial-letter-99281")
    assert pdf_bytes.startswith(b"%PDF")


async def test_upload_document_then_replay_then_conflict(adapter: NorthstarPayerAdapter):
    first = await adapter.upload_document(
        document_id="note-progress-031", document_type="clinical-note",
        related_payer_claim_id="PAYER-CLM-99281", content=b"same bytes", content_type="text/plain",
    )
    assert first is True

    second = await adapter.upload_document(
        document_id="note-progress-031", document_type="clinical-note",
        related_payer_claim_id="PAYER-CLM-99281", content=b"same bytes", content_type="text/plain",
    )
    assert second is False

    with pytest.raises(PayerError) as exc_info:
        await adapter.upload_document(
            document_id="note-progress-031", document_type="clinical-note",
            related_payer_claim_id="PAYER-CLM-99281", content=b"different bytes", content_type="text/plain",
        )
    assert exc_info.value.status == 409
    assert exc_info.value.code == "document_conflict"


async def test_create_appeal_gives_hero_id_then_replays(adapter: NorthstarPayerAdapter):
    await _upload_appeal_attachments(adapter)
    request = _appeal_request()

    receipt = await adapter.create_appeal(request, idempotency_key="appeal-case-100028-v1")
    assert receipt.appeal_id == "NST-APL-80126"
    assert receipt.status == "received"
    assert receipt.expected_resolution_days == 14
    assert receipt.replayed is False

    replay = await adapter.create_appeal(request, idempotency_key="appeal-case-100028-v1")
    assert replay.appeal_id == "NST-APL-80126"
    assert replay.replayed is True


async def test_get_appeal_returns_appeal_status(adapter: NorthstarPayerAdapter):
    await _upload_appeal_attachments(adapter)
    receipt = await adapter.create_appeal(_appeal_request(), idempotency_key="appeal-case-100028-v1")

    status = await adapter.get_appeal(receipt.appeal_id)

    assert status.appeal_id == "NST-APL-80126"
    assert status.status == "received"
