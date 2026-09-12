import json

from reclaim.models import EvidenceMatrix

INSTRUCTIONS = (
    "You are drafting the body of a medical-necessity appeal letter. Using only the verified "
    "policy requirements and citations you are given, write one short factual statement per "
    "requirement (grouping requirements together only when a single sentence genuinely covers "
    "both). Cite only citation ids listed in the input -- never invent a citation, a "
    "requirement, or a fact that isn't present in the given excerpts."
)

OUTPUT_RULES = (
    "Every statement needs at least one citationId taken from the input. A statement's "
    "requirementIds must list exactly the requirements owned by the citations it cites -- no "
    "more, no fewer. Every given requirement must be covered by at least one statement. Do not "
    "paraphrase facts beyond what the excerpts say, and do not cite a requirement or citation id "
    "that isn't listed below."
)


def build_input(matrix: EvidenceMatrix, requirement_texts: dict[str, str]) -> list[dict]:
    """Same shape convention as prompts/build_matrix.py's build_input.

    Only rows the verifier already accepted (status == "satisfied") are ever shown to the
    model -- a "missing" row has no verified citation to ground a statement in, so including it
    would just invite fabrication.
    """
    satisfied_rows = [row for row in matrix.requirements if row.status == "satisfied"]
    payload = [
        {
            "requirementId": row.requirement_id,
            "requirementText": requirement_texts.get(row.requirement_id, ""),
            "citations": [
                {"citationId": citation.citation_id, "resource": citation.resource, "excerpt": citation.excerpt}
                for citation in row.evidence
            ],
        }
        for row in satisfied_rows
    ]

    return [
        {
            "role": "user",
            "content": OUTPUT_RULES + "\n\nVerified requirements and citations:\n"
            + json.dumps(payload, sort_keys=True),
        },
    ]
