# Contract: Adapters (Constitution VI)

Everything lives in `src/reclaim/adapters/protocols.py`. Every external boundary is one
`typing.Protocol`.

- Production code depends only on these Protocols.
- `src/reclaim/main.py` wires the concrete class for each one from config.
- Tests use small in-memory fakes that implement the same Protocols.

Models referenced here are defined in [data-model.md](../data-model.md).

```python
from datetime import date
from typing import Literal, Protocol, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)
Effort = Literal["low", "medium", "high"]


class RemitFileRef(BaseModel):
    name: str
    size: int
    mtime: int


class RemitInbox(Protocol):
    """835 delivery. Real: SftpRemitInbox (paramiko, /outbound/835)."""

    async def list_files(self) -> list[RemitFileRef]: ...
    async def download(self, name: str) -> bytes: ...
    async def deliver(self, name: str, content: bytes) -> None: ...   # "Simulate incoming remit" only
    async def clear(self) -> None: ...                               # demo reset only


class ClaimArchive(Protocol):
    """837 lookup. Real: SftpClaimArchive (/claim-archive/837/<hospitalClaimId>.837)."""

    async def get_837(self, hospital_claim_id: str) -> bytes | None: ...   # None = not archived


class BinaryContent(BaseModel):
    id: str
    content_type: str
    data: bytes


class EhrClient(Protocol):
    """FHIR R4. Real: HttpEhrClient (httpx; client_credentials token; Accept application/fhir+json)."""

    requests_made: list[str]   # "GET /fhir/R4/Encounter/encounter-20260810-42", in order; copied into the audit event

    async def read(self, resource_type: str, resource_id: str) -> dict: ...     # raises EhrNotFound
    async def search(self, resource_type: str, patient_id: str) -> list[dict]: ...  # searchset entries
    async def read_binary(self, binary_id: str) -> BinaryContent: ...           # raises EhrNotFound


class PayerDecision(BaseModel): ...   # A6 decision JSON
class AppealRequest(BaseModel): ...   # A6 POST /appeals body


class AppealReceipt(BaseModel):
    appeal_id: str
    status: Literal["received", "in-review"]
    received_at: str
    expected_resolution_days: int
    replayed: bool   # Idempotent-Replayed: true


class AppealStatus(BaseModel):
    appeal_id: str
    status: Literal["received", "in-review"]
    updated_at: str


class PayerError(Exception):
    """Carries HTTP status and the A6 error envelope: code, message."""
    status: int
    code: str
    message: str


class PayerAdapter(Protocol):
    """Decision, documents, appeals, tracking. Real: NorthstarPayerAdapter (httpx, Bearer token)."""

    async def get_decision(self, payer_claim_id: str) -> PayerDecision: ...
    async def get_document(self, document_id: str) -> bytes: ...
    async def upload_document(
        self, *, document_id: str, document_type: Literal["appeal-letter", "clinical-note", "order", "policy-snapshot"],
        related_payer_claim_id: str, content: bytes, content_type: str,
    ) -> bool: ...   # True = created (201), False = already stored with same bytes (200)
    async def create_appeal(self, request: AppealRequest, idempotency_key: str) -> AppealReceipt: ...
    async def get_appeal(self, appeal_id: str) -> AppealStatus: ...


class PolicySelection(BaseModel):
    policy: "Policy | None"
    failed_selector: Literal["payerId", "planType", "state", "procedureCode", "dateOfService"] | None


class PolicyStore(Protocol):
    """Versioned payer policies. Real: FilePolicyStore (fixtures/policies/*.json)."""

    def select(self, *, payer_id: str, plan_type: str, state: str,
               procedure_code: str, date_of_service: date) -> PolicySelection: ...
    def snapshot_bytes(self, policy_id: str, version: str) -> bytes: ...   # canonical JSON for upload


class LlmUsage(BaseModel):
    input_tokens: int
    cached_tokens: int
    output_tokens: int
    reasoning_tokens: int


class LlmResult(BaseModel):
    output: BaseModel   # instance of text_format
    usage: LlmUsage
    mode: Literal["live", "replay"]


class ReplayMissError(Exception): ...   # step + key; never falls back


class LlmClient(Protocol):
    """Live: OpenAiLlmClient (responses.parse, store=False, 45 s, max_retries=0 + one 429/5xx retry,
    optional recording). Replay: ReplayLlmClient (fixtures/llm-replay/, raises ReplayMissError)."""

    async def parse(
        self, *, step: Literal["build_matrix", "draft_packet"], instructions: str,
        input: list[dict], text_format: type[T], effort: Effort,
        max_output_tokens: int, prompt_cache_key: str,
    ) -> LlmResult: ...
```

## Rules for every adapter

- Base URLs, tokens, and SFTP credentials come from `src/reclaim/config.py`, which reads the
  environment and `.env`. None are hard-coded.
- Adapters never write to audit events or SQLite. Steps do that with the adapter's return value,
  and `EhrClient.requests_made` feeds the audit event.
- Tokens, API keys, and `Authorization` headers are never logged.

## Test fakes

Fakes live in `tests/fakes.py`:
- `FakeInbox` and `FakeArchive` are dicts of bytes.
- `FixtureEhrClient` wraps the mock-hospital ASGI app through `httpx.ASGITransport`, so it runs
  the real HTTP code in-process.
- `FakeLlmClient` returns hand-written `MatrixProposal`/`LetterDraft` objects and records how each
  call was made.

Presenter controls such as the hospital toggle and the payer reset are not production
boundaries. `src/reclaim/demo.py` calls the mocks' `/_control/*` endpoints directly with httpx
and is documented as demo-only.
