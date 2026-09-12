from typing import Literal

from pydantic import BaseModel

CaseStatus = Literal[
    "new", "claim-matched", "needs-review", "evidence-gathered", "needs-evidence",
    "ready-for-review", "approved", "submitted", "in-review", "paid", "other-denial",
]
Lane = Literal["medical-necessity", "paid", "other-denial"]


class Adjustment(BaseModel):
    group: str
    reason: str
    amount: float
    level: Literal["claim", "service"]


class RemitClaim(BaseModel):
    hospital_claim_id: str
    claim_status: str
    billed: float
    paid: float
    patient_responsibility: float
    claim_filing_indicator: str
    payer_claim_id: str
    payer_id: str
    member_id: str | None
    rendering_npi: str
    date_of_service: str
    procedure_qualifier: str
    procedure_code: str
    adjustments: list[Adjustment] = []
    denial_code: str | None = None
    lane: Lane


class Remit(BaseModel):
    isa13: str
    gs06: str
    st02: str
    usage: str
    payer_name: str
    payer_id: str
    payee_npi: str
    production_date: str
    payment_date: str
    total_paid: float
    claims: list[RemitClaim]


class OriginalClaim(BaseModel):
    hospital_claim_id: str
    billed: float
    frequency_code: str
    member_id: str | None
    group_number: str
    payer_id: str
    billing_npi: str
    billing_state: str
    rendering_npi: str
    procedure_qualifier: str
    procedure_code: str
    units: float
    diagnosis_code: str
    date_of_service: str


class ClaimMapEntry(BaseModel):
    patientId: str
    mrn: str
    encounterId: str
    dateOfService: str
    procedureCode: str
    diagnosisCode: str


class IdentityCheck(BaseModel):
    field: str
    source_a: str
    value_a: str | None
    source_b: str
    value_b: str | None
    passed: bool


class EvidenceItem(BaseModel):
    resource: str
    resource_type: str
    date: str | None
    source_url: str
    included: bool
    exclusion_reason: str | None = None
    summary: str = ""
    document: str | None = None
    text: str | None = None


class EvidenceSet(BaseModel):
    items: list[EvidenceItem]
    excluded_count: int
    search_counts: dict[str, int]
    lookback_start: str
    lookback_end: str
    coverage_plan_type: str


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


class Policy(BaseModel):
    policyId: str
    version: str
    title: str
    payer: str
    payerId: str
    planType: str
    states: list[str]
    procedureCodes: list[str]
    effectiveStart: str
    effectiveEnd: str | None
    appealWindowDays: int
    lookbackMonths: int
    requirements: list[dict]
    sourceUrl: str
    sourceRetrievedAt: str


class PolicySelection(BaseModel):
    policy: Policy | None
    failed_selector: Literal["payerId", "planType", "state", "procedureCode", "dateOfService"] | None


class Deadline(BaseModel):
    deadline_of_record: str
    policy_window_date: str
    days_left: int
    warning: str | None = None

    @property
    def line(self) -> str:
        return f"Appeal deadline: {_fmt_date(self.deadline_of_record)} ({self.days_left} days left)"


def _fmt_date(iso_date: str) -> str:
    import datetime

    d = datetime.date.fromisoformat(iso_date)
    return d.strftime("%B %-d, %Y") if hasattr(d, "strftime") else iso_date


class Citation(BaseModel):
    citation_id: str
    resource: str
    document: str | None = None
    date: str | None = None
    excerpt: str
    verified: bool
    rejection_reason: str | None = None


class MatrixRow(BaseModel):
    requirement_id: str
    status: Literal["satisfied", "missing"]
    reason: str | None = None
    evidence: list[Citation] = []


class EvidenceMatrix(BaseModel):
    case_id: str
    policy_id: str
    policy_version: str
    summary: dict
    requirements: list[MatrixRow]


class LetterStatement(BaseModel):
    statement_id: str
    text: str
    requirement_ids: list[str]
    citation_ids: list[str]


class HeaderField(BaseModel):
    label: str
    value: str
    source: Literal["remit", "claim837", "payerDecision", "claimMap", "policy"]


class Letter(BaseModel):
    header: list[HeaderField]
    body: list[LetterStatement]
    requested_action: str
    attachments: list[str]
    required_approver: str
    version: int
    footer: str = "SYNTHETIC DEMO DATA"


class Persona(BaseModel):
    userId: str
    role: str


class LlmUsage(BaseModel):
    input_tokens: int
    cached_tokens: int
    output_tokens: int
    reasoning_tokens: int
    usd: float = 0.0


class CitationProposal(BaseModel):
    resource: str
    excerpt: str


class RequirementProposal(BaseModel):
    requirementId: str
    status: Literal["satisfied", "missing"]
    reason: str | None = None
    citations: list[CitationProposal] = []


class MatrixProposal(BaseModel):
    requirements: list[RequirementProposal]


class StatementProposal(BaseModel):
    text: str
    requirementIds: list[str]
    citationIds: list[str]


class LetterDraft(BaseModel):
    statements: list[StatementProposal]
