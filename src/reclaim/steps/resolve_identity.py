import json
from pathlib import Path

from pydantic import BaseModel

from reclaim.audit import write_event
from reclaim.config import Settings
from reclaim.models import ClaimMapEntry, IdentityCheck, OriginalClaim
from reclaim.repo import Repo


def _normalize_date(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) == 8 and value.isdigit():
        return f"{value[:4]}-{value[4:6]}-{value[6:]}"
    return value


def run_identity_gate(case: dict, original_claim: OriginalClaim) -> list[IdentityCheck]:
    checks = [
        IdentityCheck(
            field="claimId", source_a="remit", value_a=case["hospital_claim_id"],
            source_b="claim837", value_b=original_claim.hospital_claim_id,
            passed=case["hospital_claim_id"] == original_claim.hospital_claim_id,
        ),
        IdentityCheck(
            field="memberId", source_a="remit", value_a=case["member_id"],
            source_b="claim837", value_b=original_claim.member_id,
            passed=case["member_id"] is not None and case["member_id"] == original_claim.member_id,
        ),
        IdentityCheck(
            field="dateOfService", source_a="remit", value_a=_normalize_date(case["date_of_service"]),
            source_b="claim837", value_b=_normalize_date(original_claim.date_of_service),
            passed=_normalize_date(case["date_of_service"]) == _normalize_date(original_claim.date_of_service),
        ),
        IdentityCheck(
            field="payerId", source_a="remit", value_a=case["payer_id"],
            source_b="claim837", value_b=original_claim.payer_id,
            passed=case["payer_id"] == original_claim.payer_id,
        ),
        IdentityCheck(
            field="renderingNpi", source_a="remit", value_a=case["rendering_npi"],
            source_b="claim837", value_b=original_claim.rendering_npi,
            passed=case["rendering_npi"] == original_claim.rendering_npi,
        ),
        IdentityCheck(
            field="procedureCode",
            source_a="remit", value_a=f"{case['procedure_qualifier']}:{case['procedure_code']}",
            source_b="claim837",
            value_b=f"{original_claim.procedure_qualifier}:{original_claim.procedure_code}",
            passed=(
                f"{case['procedure_qualifier']}:{case['procedure_code']}"
                == f"{original_claim.procedure_qualifier}:{original_claim.procedure_code}"
            ),
        ),
    ]
    if original_claim.frequency_code == "7":
        checks.append(
            IdentityCheck(
                field="claimFrequency", source_a="claim837", value_a=original_claim.frequency_code,
                source_b="claim837", value_b="not 7", passed=False,
            )
        )
    return checks


def check_post_read(
    *, encounter: dict, patient_id: str, coverage: dict, member_id: str | None, date_of_service: str,
) -> list[IdentityCheck]:
    encounter_start = (encounter.get("period") or {}).get("start", "")
    encounter_date = encounter_start[:10]
    subject_ref = (encounter.get("subject") or {}).get("reference", "")
    subscriber_id = coverage.get("subscriberId")

    return [
        IdentityCheck(
            field="encounterDate", source_a="ehr:Encounter", value_a=encounter_date,
            source_b="remit", value_b=date_of_service, passed=encounter_date == date_of_service,
        ),
        IdentityCheck(
            field="encounterSubject", source_a="ehr:Encounter", value_a=subject_ref,
            source_b="ehr:Patient", value_b=f"Patient/{patient_id}",
            passed=subject_ref == f"Patient/{patient_id}",
        ),
        IdentityCheck(
            field="coverageSubscriberId", source_a="ehr:Coverage", value_a=subscriber_id,
            source_b="remit", value_b=member_id, passed=subscriber_id == member_id,
        ),
    ]


class ResolveIdentityResult(BaseModel):
    checks: list[IdentityCheck]
    claim_map_entry: ClaimMapEntry | None = None


async def resolve_identity(ctx, case: dict) -> ResolveIdentityResult:
    repo: Repo = ctx.repo
    settings: Settings = ctx.settings
    case_id = case["case_id"]

    fetch_output = repo.get_step_output(case_id, "fetch_claim")
    original_claim = OriginalClaim.model_validate(fetch_output["original_claim"]) if fetch_output else None
    if original_claim is None:
        return ResolveIdentityResult(checks=[])

    checks = run_identity_gate(case, original_claim)
    failed = next((c for c in checks if not c.passed), None)

    if failed is not None:
        repo.update_case(case_id, status="needs-review", needs_review_field=failed.field)
        write_event(
            repo, settings, case_id, "resolve_identity",
            f"Identity check failed: {failed.field}", detail={"checks": [c.model_dump() for c in checks]},
        )
        return ResolveIdentityResult(checks=checks)

    claim_map: dict = json.loads(Path(ctx.claim_map_path).read_text())
    entry_raw = claim_map.get(original_claim.hospital_claim_id)
    if entry_raw is None:
        repo.update_case(case_id, status="needs-review", needs_review_field="claimMap")
        write_event(repo, settings, case_id, "resolve_identity", "No claim map entry found")
        return ResolveIdentityResult(checks=checks)

    entry = ClaimMapEntry.model_validate(entry_raw)
    repo.update_case(case_id, status="claim-matched")
    write_event(
        repo, settings, case_id, "resolve_identity",
        f"All {len(checks)} identity checks passed", detail={"checks": [c.model_dump() for c in checks]},
    )
    return ResolveIdentityResult(checks=checks, claim_map_entry=entry)
