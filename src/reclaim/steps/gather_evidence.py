import calendar
from datetime import date

from pydantic import BaseModel

from reclaim.adapters.protocols import EhrClient, EhrNotFound, PolicyStore
from reclaim.audit import write_event
from reclaim.config import Settings
from reclaim.models import EvidenceItem, EvidenceSet
from reclaim.repo import Repo
from reclaim.steps.resolve_identity import check_post_read

CLINICAL_TYPES = [
    "Condition", "ServiceRequest", "Procedure", "DiagnosticReport", "Observation",
    "DocumentReference", "MedicationRequest",
]

RESOURCE_LABELS = {
    "Coverage": "Coverage", "Condition": "Condition", "ServiceRequest": "Order",
    "Procedure": "Procedure", "DiagnosticReport": "X-ray report", "Observation": "Pain score",
    "DocumentReference": "Note",
}


def _subtract_months(d: date, months: int) -> date:
    total = d.year * 12 + (d.month - 1) - months
    year, month = divmod(total, 12)
    month += 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def lookback_window(dos: date, months: int) -> tuple[date, date]:
    return _subtract_months(dos, months), dos


def resource_date(resource_type: str, resource: dict) -> str | None:
    if resource_type == "Condition":
        value = resource.get("recordedDate") or resource.get("onsetDateTime")
    elif resource_type == "DiagnosticReport":
        value = resource.get("effectiveDateTime") or resource.get("issued")
    elif resource_type == "Observation":
        value = resource.get("effectiveDateTime")
    elif resource_type in ("ServiceRequest", "MedicationRequest"):
        value = resource.get("authoredOn")
    elif resource_type == "Procedure":
        value = resource.get("performedDateTime") or (resource.get("performedPeriod") or {}).get("start")
    elif resource_type == "DocumentReference":
        value = resource.get("date")
    else:
        return None
    return value[:10] if value else None


def _plan_type(coverage: dict) -> str:
    for entry in coverage.get("class", []):
        codings = (entry.get("type") or {}).get("coding", [])
        if any(c.get("code") == "plan" for c in codings):
            return entry.get("name", "")
    return ""


class GatherEvidenceResult(BaseModel):
    evidence_set: EvidenceSet | None = None
    policy_id: str | None = None
    policy_version: str | None = None


async def gather_evidence(ctx, case: dict) -> GatherEvidenceResult:
    repo: Repo = ctx.repo
    settings: Settings = ctx.settings
    client: EhrClient = ctx.ehr_client
    policy_store: PolicyStore = ctx.policy_store
    case_id = case["case_id"]

    identity_output = repo.get_step_output(case_id, "resolve_identity")
    claim_map_entry = (identity_output or {}).get("claim_map_entry")
    if not claim_map_entry:
        write_event(repo, settings, case_id, "gather_evidence", "No claim map entry available")
        return GatherEvidenceResult()

    fetch_output = repo.get_step_output(case_id, "fetch_claim")
    original_claim = (fetch_output or {}).get("original_claim") or {}
    billing_state = original_claim.get("billing_state", "")

    patient_id = claim_map_entry["patientId"]
    encounter_id = claim_map_entry["encounterId"]
    dos = date.fromisoformat(claim_map_entry["dateOfService"])

    encounter = await client.read("Encounter", encounter_id)
    # encounterDate/encounterSubject depend only on `encounter`; coverage/member_id are unused
    # for those two, so evaluating with placeholders here (before Coverage is even read) is safe.
    date_check, subject_check, _ = check_post_read(
        encounter=encounter, patient_id=patient_id, coverage={}, member_id=None,
        date_of_service=claim_map_entry["dateOfService"],
    )
    if not date_check.passed:
        repo.update_case(case_id, status="needs-review", needs_review_field="encounterDate")
        write_event(repo, settings, case_id, "gather_evidence", "Encounter date mismatch",
                    ehr_requests=client.requests_made)
        return GatherEvidenceResult()
    if not subject_check.passed:
        repo.update_case(case_id, status="needs-review", needs_review_field="encounterSubject")
        write_event(repo, settings, case_id, "gather_evidence", "Encounter subject mismatch",
                    ehr_requests=client.requests_made)
        return GatherEvidenceResult()

    await client.read("Patient", patient_id)

    coverage_results = await client.search("Coverage", patient_id)
    coverage = coverage_results[0] if coverage_results else {}
    subscriber_check = check_post_read(
        encounter=encounter, patient_id=patient_id, coverage=coverage,
        member_id=case["member_id"], date_of_service=claim_map_entry["dateOfService"],
    )[2]
    if not subscriber_check.passed:
        repo.update_case(case_id, status="needs-review", needs_review_field="coverageSubscriberId")
        write_event(repo, settings, case_id, "gather_evidence", "Coverage subscriber mismatch",
                    ehr_requests=client.requests_made)
        return GatherEvidenceResult()

    plan_type = _plan_type(coverage)
    selection = policy_store.select(
        payer_id=case["payer_id"], plan_type=plan_type, state=billing_state,
        procedure_code=case["procedure_code"], date_of_service=dos,
    )
    if selection.policy is None:
        repo.update_case(case_id, status="needs-review", needs_review_field=selection.failed_selector)
        write_event(repo, settings, case_id, "gather_evidence", f"No matching policy: {selection.failed_selector}",
                    ehr_requests=client.requests_made)
        return GatherEvidenceResult()
    policy = selection.policy

    start, end = lookback_window(dos, policy.lookbackMonths)

    items: list[EvidenceItem] = [
        EvidenceItem(
            resource=f"Coverage/{coverage['id']}", resource_type="Coverage", date=None,
            source_url=f"Coverage/{coverage['id']}", included=True, summary=plan_type,
        )
    ]
    excluded_count = 0
    search_counts: dict[str, int] = {"Coverage": len(coverage_results)}

    in_window_doc_refs: list[dict] = []
    for resource_type in CLINICAL_TYPES:
        results = await client.search(resource_type, patient_id)
        search_counts[resource_type] = len(results)
        for resource in results:
            rdate = resource_date(resource_type, resource)
            included = True
            exclusion_reason = None
            if rdate is None:
                included = False
                exclusion_reason = "no date"
            elif not (start <= date.fromisoformat(rdate) <= end):
                included = False
                exclusion_reason = "outside 6-month lookback"

            if not included:
                excluded_count += 1

            items.append(EvidenceItem(
                resource=f"{resource_type}/{resource['id']}", resource_type=resource_type,
                date=rdate, source_url=f"{resource_type}/{resource['id']}",
                included=included, exclusion_reason=exclusion_reason,
            ))
            if resource_type == "DocumentReference" and included:
                in_window_doc_refs.append(resource)

    for doc_ref in in_window_doc_refs:
        binary_id = doc_ref["content"][0]["attachment"]["url"].removeprefix("Binary/")
        binary = await client.read_binary(binary_id)
        text = binary.data.decode()
        item = next(i for i in items if i.resource == f"DocumentReference/{doc_ref['id']}")
        item.document = f"Binary/{binary_id}"
        item.text = text

    evidence_set = EvidenceSet(
        items=items, excluded_count=excluded_count, search_counts=search_counts,
        lookback_start=start.isoformat(), lookback_end=end.isoformat(), coverage_plan_type=plan_type,
    )

    repo.update_case(case_id, status="evidence-gathered")
    included_count = sum(1 for i in items if i.included)
    write_event(
        repo, settings, case_id, "gather_evidence",
        f"Gathered evidence: {included_count} included, {excluded_count} excluded, policy {policy.policyId}",
        ehr_requests=client.requests_made,
    )
    return GatherEvidenceResult(evidence_set=evidence_set, policy_id=policy.policyId, policy_version=policy.version)
