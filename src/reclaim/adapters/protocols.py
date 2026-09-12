from datetime import date
from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel

from reclaim.models import Policy

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
    async def deliver(self, name: str, content: bytes) -> None: ...
    async def clear(self) -> None: ...


class ClaimArchive(Protocol):
    """837 lookup. Real: SftpClaimArchive (/claim-archive/837/<hospitalClaimId>.837)."""

    async def get_837(self, hospital_claim_id: str) -> bytes | None: ...


class BinaryContent(BaseModel):
    id: str
    content_type: str
    data: bytes


class EhrNotFound(Exception):
    pass


class EhrClient(Protocol):
    """FHIR R4. Real: HttpEhrClient (httpx; client_credentials token; Accept application/fhir+json)."""

    requests_made: list[str]

    async def read(self, resource_type: str, resource_id: str) -> dict: ...
    async def search(self, resource_type: str, patient_id: str) -> list[dict]: ...
    async def read_binary(self, binary_id: str) -> BinaryContent: ...


class PayerDecision(BaseModel):
    payerClaimId: str
    claimId: str
    decision: str
    decisionDate: str
    reasonCode: str
    reasonText: str
    appealDeadline: str
    allowedSubmissionChannels: list[str]
    letter: dict


class SubmittedBy(BaseModel):
    userId: str
    role: str


class AppealRequest(BaseModel):
    payerClaimId: str
    hospitalClaimId: str
    appealType: str = "reconsideration"
    reasonCode: str
    letterDocumentId: str
    attachments: list[str]
    submittedBy: SubmittedBy


class AppealReceipt(BaseModel):
    appeal_id: str
    status: Literal["received", "in-review"]
    received_at: str
    expected_resolution_days: int
    replayed: bool


class AppealStatus(BaseModel):
    appeal_id: str
    status: Literal["received", "in-review"]
    updated_at: str


class PayerError(Exception):
    def __init__(self, status: int, code: str, message: str = ""):
        super().__init__(f"{status} {code}: {message}")
        self.status = status
        self.code = code
        self.message = message or code


class PayerAdapter(Protocol):
    """Decision, documents, appeals, tracking. Real: NorthstarPayerAdapter (httpx, Bearer token)."""

    async def get_decision(self, payer_claim_id: str) -> PayerDecision: ...
    async def get_document(self, document_id: str) -> bytes: ...
    async def upload_document(
        self, *, document_id: str,
        document_type: Literal["appeal-letter", "clinical-note", "order", "policy-snapshot"],
        related_payer_claim_id: str, content: bytes, content_type: str,
    ) -> bool: ...
    async def create_appeal(self, request: AppealRequest, idempotency_key: str) -> AppealReceipt: ...
    async def get_appeal(self, appeal_id: str) -> AppealStatus: ...


class PolicySelection(BaseModel):
    policy: Policy | None
    failed_selector: Literal["payerId", "planType", "state", "procedureCode", "dateOfService"] | None


class PolicyStore(Protocol):
    """Versioned payer policies. Real: FilePolicyStore (fixtures/policies/*.json)."""

    def select(self, *, payer_id: str, plan_type: str, state: str,
               procedure_code: str, date_of_service: date) -> PolicySelection: ...
    def snapshot_bytes(self, policy_id: str, version: str) -> bytes: ...


class LlmUsage(BaseModel):
    input_tokens: int
    cached_tokens: int
    output_tokens: int
    reasoning_tokens: int


class LlmResult(BaseModel):
    output: BaseModel
    usage: LlmUsage
    mode: Literal["live", "replay"]

    class Config:
        arbitrary_types_allowed = True


class ReplayMissError(Exception):
    def __init__(self, step: str, key: str):
        super().__init__(f"replay miss for step={step} key={key}")
        self.step = step
        self.key = key


class LlmClient(Protocol):
    """Live: OpenAiLlmClient. Replay: ReplayLlmClient (fixtures/llm-replay/)."""

    async def parse(
        self, *, step: Literal["build_matrix", "draft_packet"], instructions: str,
        input: list[dict], text_format: type[T], effort: Effort,
        max_output_tokens: int, prompt_cache_key: str,
    ) -> LlmResult: ...
