"""Unit tests for verify_letter(draft, matrix) -> LetterCheck (T086).

data-model.md §3 "Letter body": every statement needs >=1 citation_id; every cited id must
exist in the verified matrix; a statement's requirementIds must equal the requirements of its
cited rows; every (satisfied) requirement must be covered by >=1 statement. Any failure blocks
the packet, naming the offending statement's text.

The hero matrix and its citation ids (R1-C1, R2-C1, R3-C1) mirror
tests/integration/test_matrix_pipeline.py and docs/reclaim-speckit-prompts.md Appendix A8.
"""

from reclaim.models import Citation, EvidenceMatrix, LetterDraft, MatrixRow, StatementProposal
from reclaim.verify import verify_letter

R1_TEXT = "The patient has a documented diagnosis of lumbar radiculopathy."
R2_TEXT = "The patient completed 6 weeks of supervised physical therapy."
R3_TEXT = "The treating clinician documented clinical rationale for ordering the MRI."


def _hero_matrix() -> EvidenceMatrix:
    return EvidenceMatrix(
        case_id="case-100028", policy_id="NST-IMG-2026-04", policy_version="2026.04",
        summary={"satisfied": 3, "total": 3},
        requirements=[
            MatrixRow(requirement_id="R1", status="satisfied", evidence=[
                Citation(citation_id="R1-C1", resource="Condition/condition-100",
                         excerpt="Lumbar radiculopathy", verified=True),
            ]),
            MatrixRow(requirement_id="R2", status="satisfied", evidence=[
                Citation(citation_id="R2-C1", resource="DocumentReference/treatment-note-022",
                         excerpt="6 weeks of supervised physical therapy", verified=True),
            ]),
            MatrixRow(requirement_id="R3", status="satisfied", evidence=[
                Citation(citation_id="R3-C1", resource="ServiceRequest/order-901",
                         excerpt="Ordering lumbar MRI without contrast given radiating left leg pain",
                         verified=True),
            ]),
        ],
    )


def _hero_draft() -> LetterDraft:
    return LetterDraft(statements=[
        StatementProposal(text=R1_TEXT, requirementIds=["R1"], citationIds=["R1-C1"]),
        StatementProposal(text=R2_TEXT, requirementIds=["R2"], citationIds=["R2-C1"]),
        StatementProposal(text=R3_TEXT, requirementIds=["R3"], citationIds=["R3-C1"]),
    ])


def test_hero_draft_citing_r1_r2_r3_passes():
    check = verify_letter(_hero_draft(), _hero_matrix())

    assert check.blocked is False
    assert check.blocked_reason is None


def test_statement_with_no_citations_blocks_naming_its_text():
    draft = _hero_draft()
    draft.statements[0] = StatementProposal(text=R1_TEXT, requirementIds=["R1"], citationIds=[])

    check = verify_letter(draft, _hero_matrix())

    assert check.blocked is True
    assert R1_TEXT in check.blocked_reason


def test_citation_to_nonexistent_row_blocks_naming_its_text():
    draft = _hero_draft()
    draft.statements[0] = StatementProposal(text=R1_TEXT, requirementIds=["R1"], citationIds=["R9-C1"])

    check = verify_letter(draft, _hero_matrix())

    assert check.blocked is True
    assert R1_TEXT in check.blocked_reason
    assert "R9-C1" in check.blocked_reason


def test_no_statement_covering_r3_blocks():
    draft = LetterDraft(statements=[
        StatementProposal(text=R1_TEXT, requirementIds=["R1"], citationIds=["R1-C1"]),
        StatementProposal(text=R2_TEXT, requirementIds=["R2"], citationIds=["R2-C1"]),
    ])

    check = verify_letter(draft, _hero_matrix())

    assert check.blocked is True
    assert "R3" in check.blocked_reason


def test_requirement_ids_disagreeing_with_cited_row_blocks_naming_its_text():
    draft = _hero_draft()
    # R1-C1 belongs to requirement R1, not R2 -- requirementIds must match the citation's own row.
    draft.statements[0] = StatementProposal(text=R1_TEXT, requirementIds=["R2"], citationIds=["R1-C1"])

    check = verify_letter(draft, _hero_matrix())

    assert check.blocked is True
    assert R1_TEXT in check.blocked_reason
