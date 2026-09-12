from pydantic import BaseModel

from reclaim.adapters.protocols import ClaimArchive
from reclaim.audit import write_event
from reclaim.config import Settings
from reclaim.models import OriginalClaim
from reclaim.repo import Repo
from reclaim.x12.claim837 import parse_837
from reclaim.x12.tokenizer import X12ParseError, tokenize
from reclaim.x12.validate import validate_837


class FetchClaimResult(BaseModel):
    original_claim: OriginalClaim | None = None


async def fetch_claim(ctx, case: dict) -> FetchClaimResult:
    repo: Repo = ctx.repo
    settings: Settings = ctx.settings
    archive: ClaimArchive = ctx.claim_archive
    case_id = case["case_id"]
    hospital_claim_id = case["hospital_claim_id"]

    content = await archive.get_837(hospital_claim_id)
    if content is None:
        repo.update_case(case_id, status="needs-review", needs_review_field="originalClaim")
        write_event(repo, settings, case_id, "fetch_claim", f"No 837 found for {hospital_claim_id}")
        return FetchClaimResult(original_claim=None)

    try:
        text = content.decode()
        segments = tokenize(text)
        original_claim = parse_837(text)
        failures = validate_837(segments, original_claim)
    except X12ParseError as exc:
        repo.update_case(case_id, status="needs-review", needs_review_field="originalClaim")
        write_event(repo, settings, case_id, "fetch_claim", f"837 for {hospital_claim_id} is malformed: {exc}")
        return FetchClaimResult(original_claim=None)

    if failures:
        repo.update_case(case_id, status="needs-review", needs_review_field="originalClaim")
        write_event(
            repo, settings, case_id, "fetch_claim",
            f"837 for {hospital_claim_id} failed validation: {failures[0].rule} {failures[0].message}",
        )
        return FetchClaimResult(original_claim=None)

    write_event(repo, settings, case_id, "fetch_claim", f"Fetched 837 for {hospital_claim_id}")
    return FetchClaimResult(original_claim=original_claim)
