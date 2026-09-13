import httpx

from reclaim.adapters.protocols import BinaryContent, EhrNotFound

FHIR_ACCEPT = "application/fhir+json"


class HttpEhrClient:
    """Real: SMART Backend Services FHIR R4 client. Here: httpx against mock-hospital."""

    def __init__(self, base_url: str, token_url: str, client_id: str, client_secret: str,
                 transport: httpx.AsyncBaseTransport | None = None):
        self.base_url = base_url.rstrip("/")
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self._client = httpx.AsyncClient(transport=transport)
        self._token: str | None = None
        self.requests_made: list[str] = []

    async def _get_token(self) -> str:
        if self._token is not None:
            return self._token
        resp = await self._client.post(
            self.token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )
        resp.raise_for_status()
        self._token = resp.json()["access_token"]
        return self._token

    async def _get(self, path: str) -> httpx.Response:
        token = await self._get_token()
        self.requests_made.append(f"GET /fhir/R4/{path}")
        return await self._client.get(
            f"{self.base_url}/{path}",
            headers={"Authorization": f"Bearer {token}", "Accept": FHIR_ACCEPT},
        )

    async def read(self, resource_type: str, resource_id: str) -> dict:
        resp = await self._get(f"{resource_type}/{resource_id}")
        if resp.status_code == 404:
            raise EhrNotFound(f"{resource_type}/{resource_id}")
        resp.raise_for_status()
        return resp.json()

    async def search(self, resource_type: str, patient_id: str) -> list[dict]:
        resp = await self._get(f"{resource_type}?patient={patient_id}")
        resp.raise_for_status()
        bundle = resp.json()
        return [entry["resource"] for entry in bundle.get("entry", [])]

    async def control(self, method: str, path: str, json: dict | None = None) -> dict:
        token = await self._get_token()
        root = self.base_url.removesuffix("/fhir/R4")
        resp = await self._client.request(
            method, f"{root}/_control/{path}", json=json,
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        return resp.json()

    async def read_binary(self, binary_id: str) -> BinaryContent:
        import base64

        resp = await self._get(f"Binary/{binary_id}")
        if resp.status_code == 404:
            raise EhrNotFound(f"Binary/{binary_id}")
        resp.raise_for_status()
        body = resp.json()
        return BinaryContent(
            id=binary_id,
            content_type=body.get("contentType", "text/plain"),
            data=base64.b64decode(body["data"]),
        )
