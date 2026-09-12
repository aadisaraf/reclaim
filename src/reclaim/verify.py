from collections.abc import Iterator

from pydantic import BaseModel

from reclaim.models import (
    Citation, EvidenceItem, EvidenceMatrix, EvidenceSet, LetterDraft, MatrixProposal, MatrixRow, Policy,
)

MIN_EXCERPT_LEN = 12


class Rejection(BaseModel):
    requirement_id: str
    resource: str
    excerpt: str
    reason: str


def _json_strings(value) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _json_strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _json_strings(v)


def _verify_citation(resource: str, excerpt: str, evidence_types: list[str],
                      evidence_by_resource: dict[str, EvidenceItem]) -> str | None:
    item = evidence_by_resource.get(resource)
    if item is None:
        return "not fetched for this case"
    if not item.included:
        return "outside lookback"
    if item.resource_type not in evidence_types:
        return "type not allowed"
    if len(excerpt) < MIN_EXCERPT_LEN:
        return "excerpt too short"
    if item.resource_type == "DocumentReference":
        found = item.text is not None and excerpt in item.text
    else:
        found = any(excerpt in s for s in _json_strings(item.raw))
    if not found:
        return "excerpt not found verbatim"
    return None


def verify_matrix(proposal: MatrixProposal, evidence_set: EvidenceSet, policy: Policy) -> tuple[EvidenceMatrix, list[Rejection]]:
    evidence_by_resource = {item.resource: item for item in evidence_set.items}

    proposed_by_id: dict[str, object] = {}
    for entry in proposal.requirements:
        if entry.requirementId in proposed_by_id:
            raise ValueError(f"duplicate requirement id in proposal: {entry.requirementId}")
        proposed_by_id[entry.requirementId] = entry

    rows: list[MatrixRow] = []
    rejections: list[Rejection] = []
    satisfied_count = 0

    for requirement in policy.requirements:
        req_id = requirement["id"]
        evidence_types = requirement["evidenceTypes"]
        entry = proposed_by_id.get(req_id)

        if entry is None:
            rows.append(MatrixRow(requirement_id=req_id, status="missing",
                                   reason="No evidence proposed for this requirement."))
            continue

        verified: list[Citation] = []
        reasons: list[str] = []
        for i, citation in enumerate(entry.citations, start=1):
            failure = _verify_citation(citation.resource, citation.excerpt, evidence_types, evidence_by_resource)
            if failure is None:
                item = evidence_by_resource[citation.resource]
                verified.append(Citation(
                    citation_id=f"{req_id}-C{i}", resource=citation.resource, document=item.document,
                    date=item.date, excerpt=citation.excerpt, verified=True,
                ))
            else:
                reasons.append(failure)
                rejections.append(Rejection(
                    requirement_id=req_id, resource=citation.resource, excerpt=citation.excerpt, reason=failure,
                ))

        if verified:
            satisfied_count += 1
            rows.append(MatrixRow(requirement_id=req_id, status="satisfied", evidence=verified))
        elif entry.citations:
            rows.append(MatrixRow(
                requirement_id=req_id, status="missing",
                reason=f"All proposed citations failed verification: {'; '.join(reasons)}",
            ))
        else:
            rows.append(MatrixRow(
                requirement_id=req_id, status="missing",
                reason=entry.reason or "No evidence proposed for this requirement.",
            ))

    matrix = EvidenceMatrix(
        case_id="", policy_id=policy.policyId, policy_version=policy.version,
        summary={"satisfied": satisfied_count, "total": len(policy.requirements)}, requirements=rows,
    )
    return matrix, rejections


class LetterCheck(BaseModel):
    blocked: bool
    blocked_reason: str | None = None


def verify_letter(draft: LetterDraft, matrix: EvidenceMatrix) -> LetterCheck:
    """data-model.md §3 "Letter body" rule.

    Every statement needs at least 1 citation_id, and every id must exist in the verified
    matrix. A statement's requirement_ids must equal the requirements owned by its cited rows.
    Every requirement satisfied in the matrix must be covered by at least one statement. Any
    failure blocks the packet, naming the offending statement's text (or, when no statement
    covers a requirement, naming that requirement).
    """
    citation_requirement: dict[str, str] = {
        citation.citation_id: row.requirement_id
        for row in matrix.requirements
        for citation in row.evidence
    }

    covered: set[str] = set()
    for statement in draft.statements:
        if not statement.citationIds:
            return LetterCheck(
                blocked=True,
                blocked_reason=f'Statement has no citations: "{statement.text}"',
            )

        statement_requirements: set[str] = set()
        for citation_id in statement.citationIds:
            requirement_id = citation_requirement.get(citation_id)
            if requirement_id is None:
                return LetterCheck(
                    blocked=True,
                    blocked_reason=(
                        f'Statement cites {citation_id}, which is not in the verified matrix: '
                        f'"{statement.text}"'
                    ),
                )
            statement_requirements.add(requirement_id)

        if statement_requirements != set(statement.requirementIds):
            return LetterCheck(
                blocked=True,
                blocked_reason=(
                    f'Statement requirementIds {statement.requirementIds} do not match the '
                    f'requirements owned by its citations {sorted(statement_requirements)}: '
                    f'"{statement.text}"'
                ),
            )

        covered |= statement_requirements

    required = {row.requirement_id for row in matrix.requirements if row.status == "satisfied"}
    missing = sorted(required - covered)
    if missing:
        return LetterCheck(
            blocked=True,
            blocked_reason=f"No statement covers requirement(s): {', '.join(missing)}",
        )

    return LetterCheck(blocked=False)
