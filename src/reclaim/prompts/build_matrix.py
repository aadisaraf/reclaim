import json

from reclaim.models import EvidenceSet, Policy
from reclaim.verify import Rejection

INSTRUCTIONS = (
    "You are building an evidence matrix for a medical-necessity appeal. For each policy "
    "requirement, decide whether the given evidence satisfies it. Cite only resources listed "
    "in the evidence message -- never a resource you were not given."
)

OUTPUT_RULES = (
    "Excerpts must be exact, verbatim, case-sensitive substrings of the cited resource's text "
    "(for a DocumentReference) or of some string value in its JSON (for any other type). Never "
    "paraphrase or summarize an excerpt. When no evidence supports a requirement, set its status "
    "to 'missing', give a one-sentence reason, and leave citations empty."
)


def build_input(policy: Policy, evidence_set: EvidenceSet, rejections: list[Rejection] | None = None) -> list[dict]:
    allowed_types = {t for requirement in policy.requirements for t in requirement["evidenceTypes"]}
    candidates = [item for item in evidence_set.items if item.included and item.resource_type in allowed_types]
    candidate_payload = [
        {
            "resource": item.resource, "type": item.resource_type, "date": item.date,
            "text": item.text if item.resource_type == "DocumentReference" else None,
            "json": None if item.resource_type == "DocumentReference" else item.raw,
        }
        for item in candidates
    ]

    messages = [
        {"role": "user", "content": OUTPUT_RULES + "\n\nPolicy:\n" + json.dumps(policy.model_dump(), sort_keys=True)},
        {"role": "user", "content": "Evidence:\n" + json.dumps(candidate_payload, sort_keys=True)},
    ]
    if rejections:
        messages.append({
            "role": "user",
            "content": "The previous proposal had rejected citations. Fix these and try again:\n"
            + json.dumps([r.model_dump() for r in rejections], sort_keys=True),
        })
    return messages
