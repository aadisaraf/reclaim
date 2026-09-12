import httpx

from reclaim.adapters.protocols import AppealReceipt, AppealRequest, AppealStatus, PayerDecision, PayerError


class NorthstarPayerAdapter:
    """Real: Northstar Health REST API (Appendix A6). Here: httpx against mock-northstar."""

    def __init__(self, base_url: str, token: str, transport: httpx.AsyncBaseTransport | None = None):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(transport=transport, headers={"Authorization": f"Bearer {token}"})

    @staticmethod
    def _raise_for_error(resp: httpx.Response) -> None:
        body = resp.json()
        error = body.get("error", {})
        raise PayerError(resp.status_code, error.get("code", "unknown_error"), error.get("message", ""))

    async def get_decision(self, payer_claim_id: str) -> PayerDecision:
        resp = await self._client.get(f"{self.base_url}/claims/{payer_claim_id}/decision")
        if resp.status_code != 200:
            self._raise_for_error(resp)
        return PayerDecision.model_validate(resp.json())

    async def get_document(self, document_id: str) -> bytes:
        resp = await self._client.get(f"{self.base_url}/documents/{document_id}")
        if resp.status_code != 200:
            self._raise_for_error(resp)
        return resp.content

    async def upload_document(
        self, *, document_id: str, document_type: str, related_payer_claim_id: str,
        content: bytes, content_type: str,
    ) -> bool:
        resp = await self._client.post(
            f"{self.base_url}/documents",
            data={
                "documentId": document_id,
                "documentType": document_type,
                "relatedPayerClaimId": related_payer_claim_id,
            },
            files={"file": (document_id, content, content_type)},
        )
        if resp.status_code not in (200, 201):
            self._raise_for_error(resp)
        return resp.status_code == 201

    async def create_appeal(self, request: AppealRequest, idempotency_key: str) -> AppealReceipt:
        resp = await self._client.post(
            f"{self.base_url}/appeals",
            json=request.model_dump(),
            headers={"Idempotency-Key": idempotency_key},
        )
        if resp.status_code not in (200, 201):
            self._raise_for_error(resp)
        body = resp.json()
        return AppealReceipt(
            appeal_id=body["appealId"],
            status=body["status"],
            received_at=body["receivedAt"],
            expected_resolution_days=body["expectedResolutionDays"],
            replayed=resp.headers.get("Idempotent-Replayed") == "true",
        )

    async def get_appeal(self, appeal_id: str) -> AppealStatus:
        resp = await self._client.get(f"{self.base_url}/appeals/{appeal_id}")
        if resp.status_code != 200:
            self._raise_for_error(resp)
        body = resp.json()
        return AppealStatus(appeal_id=body["appealId"], status=body["status"], updated_at=body["updatedAt"])
