from pydantic import BaseModel

from reclaim.audit import write_event
from reclaim.models import EvidenceMatrix, EvidenceSet, MatrixProposal, Policy
from reclaim.prompts.build_matrix import INSTRUCTIONS, build_input
from reclaim.verify import verify_matrix

RETRY_EFFORT = "high"
FIRST_PASS_TOKENS = 6000
RETRY_TOKENS = 12000


class BuildMatrixResult(BaseModel):
    matrix: EvidenceMatrix | None = None


def _question_for(requirement_id: str, policy: Policy) -> str:
    """data-model.md §6: R2 gets the hand-written A8 wording; every other requirement falls
    back to the template built from the policy's own requirement text."""
    if requirement_id == "R2":
        return (
            "The policy requires documentation of prior conservative treatment. "
            "Please identify the relevant note or provide a factual attestation."
        )
    requirement_text = next(
        (r["text"] for r in policy.requirements if r["id"] == requirement_id), requirement_id
    )
    return f"The policy requires {requirement_text}. Please identify the relevant note or provide a factual attestation."


def _sync_tasks(repo, case_id: str, matrix: EvidenceMatrix, policy: Policy) -> None:
    """data-model.md §6: one open task per missing requirement, created only the first time that
    row goes missing; a row that's now satisfied closes its existing open task; a still-missing
    row is left untouched (no duplicate, no update)."""
    existing_by_requirement = {t["requirement_id"]: t for t in repo.list_tasks(case_id)}
    for row in matrix.requirements:
        task = existing_by_requirement.get(row.requirement_id)
        if row.status == "missing":
            if task is None:
                repo.upsert_task(
                    f"task-{case_id}-{row.requirement_id}",
                    case_id=case_id,
                    task_type="clinical-evidence-request",
                    requirement_id=row.requirement_id,
                    assignee_role="treating-clinician",
                    question=_question_for(row.requirement_id, policy),
                    status="open",
                    close_note=None,
                )
        elif task is not None and task["status"] == "open":
            repo.close_task(
                task["task_id"], f"Requirement {row.requirement_id} is now satisfied by a verified citation."
            )


async def build_matrix(ctx, case: dict) -> BuildMatrixResult:
    repo = ctx.repo
    settings = ctx.settings
    case_id = case["case_id"]

    evidence_output = repo.get_step_output(case_id, "gather_evidence") or {}
    evidence_set = EvidenceSet.model_validate(evidence_output["evidence_set"])
    policy = Policy.model_validate_json(
        ctx.policy_store.snapshot_bytes(evidence_output["policy_id"], evidence_output["policy_version"])
    )

    usages = []
    result = await ctx.llm_client.parse(
        step="build_matrix", instructions=INSTRUCTIONS, input=build_input(policy, evidence_set),
        text_format=MatrixProposal, effort=settings.effort_build_matrix,
        max_output_tokens=FIRST_PASS_TOKENS, prompt_cache_key=policy.policyId,
    )
    usages.append(result.usage)
    matrix, rejections = verify_matrix(result.output, evidence_set, policy)
    first_pass_rejections = rejections

    if rejections:
        retry = await ctx.llm_client.parse(
            step="build_matrix", instructions=INSTRUCTIONS,
            input=build_input(policy, evidence_set, rejections=rejections),
            text_format=MatrixProposal, effort=RETRY_EFFORT,
            max_output_tokens=RETRY_TOKENS, prompt_cache_key=policy.policyId,
        )
        usages.append(retry.usage)
        matrix, rejections = verify_matrix(retry.output, evidence_set, policy)

    matrix = matrix.model_copy(update={"case_id": case_id})
    if any(row.status == "missing" for row in matrix.requirements):
        repo.update_case(case_id, status="needs-evidence")

    _sync_tasks(repo, case_id, matrix, policy)

    write_event(
        repo, settings, case_id, "build_matrix",
        f"Evidence matrix: {matrix.summary['satisfied']}/{matrix.summary['total']} satisfied",
        detail={"rejections": [r.model_dump() for r in first_pass_rejections]},
        llm_usage={"calls": [u.model_dump() for u in usages]},
    )
    return BuildMatrixResult(matrix=matrix)
