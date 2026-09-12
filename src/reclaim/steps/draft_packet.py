import hashlib
import json

from pydantic import BaseModel

from reclaim.adapters.protocols import PayerDecision
from reclaim.audit import write_event
from reclaim.models import (
    ClaimMapEntry, EvidenceMatrix, EvidenceSet, HeaderField, Letter, LetterDraft, LetterStatement,
    OriginalClaim, Policy,
)
from reclaim.pdf import render_html, render_pdf
from reclaim.prompts.draft_packet import INSTRUCTIONS, build_input
from reclaim.verify import verify_letter

FIRST_PASS_TOKENS = 3000
REQUESTED_ACTION = "Please reconsider and reprocess payment"
REQUIRED_APPROVER_ROLE = "authorized-billing-user"


def _iso_date(value: str | None) -> str | None:
    """YYYYMMDD (as stored on `cases`/OriginalClaim) -> YYYY-MM-DD. Already-ISO values pass through."""
    if value and len(value) == 8 and value.isdigit():
        return f"{value[:4]}-{value[4:6]}-{value[6:]}"
    return value


def _fmt_amount(amount: float) -> str:
    return f"${amount:,.0f}"


def build_header(
    case: dict, claim: OriginalClaim, claim_map: ClaimMapEntry, decision: PayerDecision, policy: Policy,
) -> list[HeaderField]:
    """The A8 packet header, hand-ordered: hospital/payer claim ids, patient/member identifiers,
    procedure, diagnosis, provider, service date, amount, denial reason, then policy."""
    return [
        HeaderField(label="Hospital claim ID", value=case["hospital_claim_id"], source="remit"),
        HeaderField(label="Payer claim ID", value=case["payer_claim_id"], source="remit"),
        HeaderField(label="Patient MRN", value=claim_map.mrn, source="claimMap"),
        HeaderField(label="Member ID", value=claim.member_id, source="claim837"),
        HeaderField(label="Procedure code", value=claim.procedure_code, source="claim837"),
        HeaderField(label="Diagnosis code", value=claim.diagnosis_code, source="claim837"),
        HeaderField(label="Rendering provider NPI", value=claim.rendering_npi, source="claim837"),
        HeaderField(label="Date of service", value=_iso_date(claim.date_of_service), source="claim837"),
        HeaderField(label="Billed amount", value=_fmt_amount(case["billed_amount"]), source="remit"),
        HeaderField(
            label="Denial reason", value=f"{decision.reasonCode} {decision.reasonText}",
            source="payerDecision",
        ),
        HeaderField(label="Policy", value=f"{policy.policyId} v{policy.version}", source="policy"),
    ]


def attachment_ids(matrix: EvidenceMatrix) -> list[str]:
    """data-model.md §3 "Attachments": cited DocumentReferences first (citation order), then
    cited ServiceRequests, then policy-snapshot-<policyId>. Condition citations aren't attached."""
    doc_refs: list[str] = []
    service_requests: list[str] = []
    for row in matrix.requirements:
        for citation in row.evidence:
            if citation.resource.startswith("DocumentReference/"):
                rid = citation.resource.split("/", 1)[1]
                if rid not in doc_refs:
                    doc_refs.append(rid)
            elif citation.resource.startswith("ServiceRequest/"):
                rid = citation.resource.split("/", 1)[1]
                if rid not in service_requests:
                    service_requests.append(rid)
    return [*doc_refs, *service_requests, f"policy-snapshot-{matrix.policy_id}"]


# Pure status-line helpers, kept here so both a future api.py and these tests share one
# implementation. api.py's case-detail assembly may already compute completenessLine and
# recoveryLine independently (see tests/contract/test_app_api_case_detail_full.py) -- these
# exist primarily as documentation of the exact A9-step-5 wording and are safe to call directly.
def status_line(blocked: bool) -> str:
    return "Blocked" if blocked else "Ready for review"


def completeness_line(matrix: EvidenceMatrix) -> str:
    return f"Evidence completeness: {matrix.summary['satisfied']}/{matrix.summary['total']} policy criteria satisfied"


def recovery_line(case: dict) -> str:
    return f"Expected recovery: {_fmt_amount(case['billed_amount'])}"


def _content_sha256(
    letter_payload: dict, attachment_shas: dict[str, str], policy_id: str, policy_version: str,
) -> str:
    """data-model.md §5: SHA-256 of canonical JSON {letter_json, attachment ids and sha256s,
    policy_id, policy_version}. `letter_payload` deliberately excludes the `version` field --
    version is derived FROM this hash (reuse vs. bump), so it can't be part of the input."""
    payload = json.dumps(
        {"letter": letter_payload, "attachments": attachment_shas,
         "policy_id": policy_id, "policy_version": policy_version},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _resolve_version(repo, case_id: str, content_sha256: str) -> int:
    latest = repo.latest_packet(case_id)
    if latest is None:
        return 1
    if latest["content_sha256"] == content_sha256:
        return latest["version"]
    return latest["version"] + 1


class DraftPacketResult(BaseModel):
    packet_version: int
    blocked: bool


async def draft_packet(ctx, case: dict) -> DraftPacketResult:
    repo = ctx.repo
    settings = ctx.settings
    case_id = case["case_id"]

    evidence_output = repo.get_step_output(case_id, "gather_evidence") or {}
    evidence_set = EvidenceSet.model_validate(evidence_output["evidence_set"])
    evidence_by_resource = {item.resource: item for item in evidence_set.items}
    policy_id = evidence_output["policy_id"]
    policy_version = evidence_output["policy_version"]
    policy = Policy.model_validate_json(ctx.policy_store.snapshot_bytes(policy_id, policy_version))

    matrix_output = repo.get_step_output(case_id, "build_matrix") or {}
    matrix = EvidenceMatrix.model_validate(matrix_output["matrix"])

    fetch_output = repo.get_step_output(case_id, "fetch_claim") or {}
    claim = OriginalClaim.model_validate(fetch_output["original_claim"])

    identity_output = repo.get_step_output(case_id, "resolve_identity") or {}
    claim_map = ClaimMapEntry.model_validate(identity_output["claim_map_entry"])

    payer_output = repo.get_step_output(case_id, "payer_context") or {}
    decision = PayerDecision.model_validate(payer_output["decision"])

    requirement_texts = {r["id"]: r["text"] for r in policy.requirements}

    result = await ctx.llm_client.parse(
        step="draft_packet", instructions=INSTRUCTIONS, input=build_input(matrix, requirement_texts),
        text_format=LetterDraft, effort=settings.effort_draft_packet,
        max_output_tokens=FIRST_PASS_TOKENS, prompt_cache_key=policy.policyId,
    )
    draft: LetterDraft = result.output
    usages = [result.usage]

    check = verify_letter(draft, matrix)
    all_satisfied = all(row.status == "satisfied" for row in matrix.requirements)
    blocked = check.blocked or not all_satisfied
    blocked_reason = check.blocked_reason if check.blocked else (
        "Not all policy requirements are satisfied." if blocked else None
    )

    attachment_id_list = attachment_ids(matrix)
    attachment_contents: dict[str, tuple[bytes, str, str]] = {}
    for attachment_id in attachment_id_list:
        if attachment_id == f"policy-snapshot-{policy_id}":
            content = ctx.policy_store.snapshot_bytes(policy_id, policy_version)
            attachment_contents[attachment_id] = (content, "application/json", "policy-snapshot")
            continue
        item = (
            evidence_by_resource.get(f"DocumentReference/{attachment_id}")
            or evidence_by_resource.get(f"ServiceRequest/{attachment_id}")
        )
        if item is None:
            continue
        if item.resource_type == "DocumentReference":
            attachment_contents[attachment_id] = ((item.text or "").encode("utf-8"), "text/plain", "clinical-note")
        else:
            attachment_contents[attachment_id] = (
                json.dumps(item.raw, sort_keys=True).encode("utf-8"), "application/json", "order",
            )

    attachment_shas = {aid: hashlib.sha256(content).hexdigest() for aid, (content, _, _) in attachment_contents.items()}

    def _save_attachments() -> None:
        for attachment_id, (content, content_type, document_type) in attachment_contents.items():
            repo.save_document(
                document_id=attachment_id, case_id=case_id, document_type=document_type,
                content_type=content_type, content=content, sha256=attachment_shas[attachment_id],
            )

    if blocked:
        content_sha256 = _content_sha256(draft.model_dump(), attachment_shas, policy_id, policy_version)
        version = _resolve_version(repo, case_id, content_sha256)

        _save_attachments()
        repo.save_packet(
            case_id, version, status="blocked", content_sha256=content_sha256,
            letter_json=draft.model_dump_json(), blocked_reason=blocked_reason,
            html=None, pdf=None, approved_by=None, approved_role=None, approved_at=None,
        )
        repo.update_case(case_id, status="evidence-gathered")

        write_event(
            repo, settings, case_id, "draft_packet", f"Appeal packet v{version} blocked: {blocked_reason}",
            llm_usage={"calls": [u.model_dump() for u in usages]},
        )
        return DraftPacketResult(packet_version=version, blocked=True)

    header = build_header(case, claim, claim_map, decision, policy)
    body = [
        LetterStatement(
            statement_id=f"S{i}", text=statement.text,
            requirement_ids=statement.requirementIds, citation_ids=statement.citationIds,
        )
        for i, statement in enumerate(draft.statements, start=1)
    ]
    letter = Letter(
        header=header, body=body, requested_action=REQUESTED_ACTION, attachments=attachment_id_list,
        required_approver=REQUIRED_APPROVER_ROLE, version=0,
    )

    content_sha256 = _content_sha256(
        letter.model_dump(exclude={"version"}), attachment_shas, policy_id, policy_version,
    )
    version = _resolve_version(repo, case_id, content_sha256)
    letter.version = version

    pdf_bytes = render_pdf(letter)
    html = render_html(letter)

    _save_attachments()
    hospital_claim_suffix = case["hospital_claim_id"].split("-")[-1]
    repo.save_document(
        document_id=f"appeal-letter-{hospital_claim_suffix}", case_id=case_id, document_type="appeal-letter",
        content_type="application/pdf", content=pdf_bytes, sha256=hashlib.sha256(pdf_bytes).hexdigest(),
    )

    repo.save_packet(
        case_id, version, status="ready-for-review", content_sha256=content_sha256,
        letter_json=letter.model_dump_json(), blocked_reason=None, html=html, pdf=pdf_bytes,
        approved_by=None, approved_role=None, approved_at=None,
    )
    repo.update_case(case_id, status="ready-for-review")

    write_event(
        repo, settings, case_id, "draft_packet", f"Appeal packet v{version} ready for review",
        llm_usage={"calls": [u.model_dump() for u in usages]},
    )
    return DraftPacketResult(packet_version=version, blocked=False)
