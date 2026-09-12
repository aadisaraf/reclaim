import hashlib

from pydantic import BaseModel

from reclaim.audit import write_event
from reclaim.config import Settings
from reclaim.repo import Repo
from reclaim.x12.remit835 import DENIAL_REASON_LABELS, parse_835
from reclaim.x12.tokenizer import X12ParseError, tokenize
from reclaim.x12.validate import validate_835


class IngestResult(BaseModel):
    status: str  # "processed" | "duplicate" | "rejected"
    new_case_ids: list[str] = []
    reject_rule: str | None = None
    message: str = ""


def _case_id(hospital_claim_id: str) -> str:
    return "case-" + hospital_claim_id.rsplit("-", 1)[-1]


def _money(amount: float) -> str:
    return f"${amount:,.0f}"


def ingest(repo: Repo, settings: Settings, name: str, content: bytes) -> IngestResult:
    sha256 = hashlib.sha256(content).hexdigest()

    try:
        text = content.decode()
        segments = tokenize(text)
        remit = parse_835(text)
        failures = validate_835(segments, remit)
    except X12ParseError as exc:
        is_new = repo.insert_remit_file(sha256, name, "rejected", "X-01", 0)
        if not is_new:
            write_event(repo, settings, None, "ingest", f"{name}: already processed")
            return IngestResult(status="duplicate", message="already processed")
        write_event(repo, settings, None, "ingest", f"{name}: rejected (malformed X12: {exc})")
        return IngestResult(status="rejected", reject_rule="X-01", message=str(exc))

    if failures:
        rule = failures[0].rule
        is_new = repo.insert_remit_file(sha256, name, "rejected", rule, len(remit.claims))
        if not is_new:
            write_event(repo, settings, None, "ingest", f"{name}: already processed")
            return IngestResult(status="duplicate", message="already processed")
        write_event(repo, settings, None, "ingest", f"{name}: rejected ({rule}: {failures[0].message})")
        return IngestResult(status="rejected", reject_rule=rule, message=failures[0].message)

    is_new = repo.insert_remit_file(sha256, name, "processed", None, len(remit.claims))
    if not is_new:
        write_event(repo, settings, None, "ingest", f"{name}: already processed")
        return IngestResult(status="duplicate", message="already processed")

    new_case_ids: list[str] = []
    created_lines: list[str] = []
    paid_count = other_count = 0

    for claim in remit.claims:
        case_id = _case_id(claim.hospital_claim_id)
        existing = repo.get_case(case_id)
        if existing is not None:
            write_event(
                repo, settings, case_id, "ingest",
                f"{name}: later remittance for {claim.hospital_claim_id}, no changes applied",
            )
            continue

        denial_reason = None
        if claim.denial_code and "-" in claim.denial_code:
            denial_reason = DENIAL_REASON_LABELS.get(claim.denial_code.split("-", 1)[1])

        if claim.lane == "medical-necessity":
            status = "new"
            new_case_ids.append(case_id)
            created_lines.append(f"Created {case_id} ({claim.denial_code}, {_money(claim.billed)})")
        elif claim.lane == "paid":
            status = "paid"
            paid_count += 1
        else:
            status = "other-denial"
            other_count += 1

        repo.upsert_case(
            case_id,
            hospital_claim_id=claim.hospital_claim_id,
            lane=claim.lane,
            status=status,
            payer_claim_id=claim.payer_claim_id,
            payer=remit.payer_name,
            payer_id=remit.payer_id,
            member_id=claim.member_id,
            rendering_npi=claim.rendering_npi,
            procedure_qualifier=claim.procedure_qualifier,
            procedure_code=claim.procedure_code,
            date_of_service=claim.date_of_service,
            denial_code=claim.denial_code,
            denial_reason=denial_reason,
            billed_amount=claim.billed,
            paid_amount=claim.paid,
            denied_amount=claim.billed - claim.paid,
            remit_file=name,
            remit_sha256=sha256,
            needs_review_field=None,
            last_error=None,
            running=0,
        )

    summary_parts = [f"Read {name}: {len(remit.claims)} claims."] + created_lines
    if paid_count:
        summary_parts.append(f"{paid_count} paid claim{'s' if paid_count != 1 else ''}, no action.")
    if other_count:
        summary_parts.append(f"{other_count} other denial lane{'s' if other_count != 1 else ''}.")
    summary = " ".join(summary_parts)
    write_event(repo, settings, None, "ingest", summary, ehr_requests=[])

    return IngestResult(status="processed", new_case_ids=new_case_ids, message=summary)
