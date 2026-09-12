"""Unit tests for build_header, attachment_ids, render_pdf, render_html, and the packet status
lines (T087). All expected values are hand-copied from docs/reclaim-speckit-prompts.md Appendix
A3, A5, A6, A7, A8 -- never derived by running the pipeline steps.
"""

from reclaim.adapters.protocols import PayerDecision
from reclaim.models import (
    Citation, ClaimMapEntry, EvidenceMatrix, Letter, LetterStatement, MatrixRow, OriginalClaim, Policy,
)
from reclaim.pdf import render_html, render_pdf
from reclaim.steps.draft_packet import (
    attachment_ids, build_header, completeness_line, recovery_line, status_line,
)

HERO_CASE = dict(hospital_claim_id="HSP-CLM-100028", payer_claim_id="PAYER-CLM-99281", billed_amount=4800.0)

HERO_CLAIM = OriginalClaim(
    hospital_claim_id="HSP-CLM-100028", billed=4800.0, frequency_code="1",
    member_id="MEMBER-448820", group_number="NST-PPO-GRP-01", payer_id="NSTHLTH01",
    billing_npi="1245319599", billing_state="WA", rendering_npi="1234567893",
    procedure_qualifier="HC", procedure_code="72148", units=1, diagnosis_code="M54.16",
    date_of_service="20260810",
)

HERO_CLAIM_MAP = ClaimMapEntry(
    patientId="patient-0042", mrn="MRN-0042", encounterId="encounter-20260810-42",
    dateOfService="2026-08-10", procedureCode="72148", diagnosisCode="M54.16",
)

HERO_DECISION = PayerDecision(
    payerClaimId="PAYER-CLM-99281", claimId="HSP-CLM-100028", decision="denied",
    decisionDate="2026-08-20", reasonCode="CO-50",
    reasonText="Insufficient documentation of medical necessity",
    appealDeadline="2026-10-19", allowedSubmissionChannels=["portal", "fax"],
    letter={"documentId": "denial-letter-99281", "url": "/api/v1/documents/denial-letter-99281"},
)

HERO_POLICY = Policy(
    policyId="NST-IMG-2026-04", version="2026.04", title="Advanced imaging of the lumbar spine (SYNTHETIC)",
    payer="Northstar Health", payerId="NSTHLTH01", planType="Commercial PPO", states=["WA"],
    procedureCodes=["72148"], effectiveStart="2026-01-01", effectiveEnd=None, appealWindowDays=60,
    lookbackMonths=6,
    requirements=[
        {"id": "R1", "text": "Documented diagnosis that supports lumbar imaging, such as lumbar radiculopathy",
         "evidenceTypes": ["Condition", "DocumentReference"]},
        {"id": "R2", "text": "Documented trial of conservative treatment lasting at least 6 weeks within "
                             "the 6 months before the date of service",
         "evidenceTypes": ["DocumentReference", "MedicationRequest"]},
        {"id": "R3", "text": "Clinical rationale for the imaging order from the treating clinician",
         "evidenceTypes": ["ServiceRequest", "DocumentReference"]},
    ],
    sourceUrl="https://example.org/mock-policy/NST-IMG-2026-04", sourceRetrievedAt="2026-09-12",
)


def _hero_matrix() -> EvidenceMatrix:
    return EvidenceMatrix(
        case_id="case-100028", policy_id="NST-IMG-2026-04", policy_version="2026.04",
        summary={"satisfied": 3, "total": 3},
        requirements=[
            MatrixRow(requirement_id="R1", status="satisfied", evidence=[
                Citation(citation_id="R1-C1", resource="Condition/condition-100",
                         excerpt="Lumbar radiculopathy", verified=True),
                Citation(citation_id="R1-C2", resource="DocumentReference/note-progress-031",
                         document="Binary/note-progress-031",
                         excerpt="consistent with lumbar radiculopathy", verified=True),
            ]),
            MatrixRow(requirement_id="R2", status="satisfied", evidence=[
                Citation(citation_id="R2-C1", resource="DocumentReference/treatment-note-022",
                         document="Binary/treatment-note-022",
                         excerpt="6 weeks of supervised physical therapy", verified=True),
            ]),
            MatrixRow(requirement_id="R3", status="satisfied", evidence=[
                Citation(citation_id="R3-C1", resource="ServiceRequest/order-901",
                         excerpt="Ordering lumbar MRI without contrast given radiating left leg pain",
                         verified=True),
            ]),
        ],
    )


def _hero_letter(version: int = 1) -> Letter:
    header = build_header(HERO_CASE, HERO_CLAIM, HERO_CLAIM_MAP, HERO_DECISION, HERO_POLICY)
    body = [
        LetterStatement(statement_id="S1", text="The patient has a documented diagnosis of lumbar radiculopathy.",
                         requirement_ids=["R1"], citation_ids=["R1-C1", "R1-C2"]),
        LetterStatement(statement_id="S2", text="The patient completed 6 weeks of supervised physical therapy.",
                         requirement_ids=["R2"], citation_ids=["R2-C1"]),
        LetterStatement(statement_id="S3", text="The treating clinician documented clinical rationale for the MRI.",
                         requirement_ids=["R3"], citation_ids=["R3-C1"]),
    ]
    return Letter(
        header=header, body=body, requested_action="Please reconsider and reprocess payment",
        attachments=attachment_ids(_hero_matrix()), required_approver="authorized-billing-user",
        version=version,
    )


def test_build_header_matches_a8_hero_values_with_sources():
    header = build_header(HERO_CASE, HERO_CLAIM, HERO_CLAIM_MAP, HERO_DECISION, HERO_POLICY)
    by_label = {field.label: field for field in header}

    assert by_label["Hospital claim ID"].value == "HSP-CLM-100028"
    assert by_label["Hospital claim ID"].source == "remit"

    assert by_label["Payer claim ID"].value == "PAYER-CLM-99281"
    assert by_label["Payer claim ID"].source == "remit"

    assert by_label["Patient MRN"].value == "MRN-0042"
    assert by_label["Patient MRN"].source == "claimMap"

    assert by_label["Member ID"].value == "MEMBER-448820"
    assert by_label["Member ID"].source == "claim837"

    assert by_label["Procedure code"].value == "72148"
    assert by_label["Procedure code"].source == "claim837"

    assert by_label["Diagnosis code"].value == "M54.16"
    assert by_label["Diagnosis code"].source == "claim837"

    assert by_label["Rendering provider NPI"].value == "1234567893"
    assert by_label["Rendering provider NPI"].source == "claim837"

    assert by_label["Date of service"].value == "2026-08-10"
    assert by_label["Date of service"].source == "claim837"

    assert by_label["Billed amount"].value == "$4,800"
    assert by_label["Billed amount"].source == "remit"

    assert by_label["Denial reason"].value == "CO-50 Insufficient documentation of medical necessity"
    assert by_label["Denial reason"].source == "payerDecision"

    assert by_label["Policy"].value == "NST-IMG-2026-04 v2026.04"
    assert by_label["Policy"].source == "policy"


def test_attachment_ids_hero_deterministic_order():
    assert attachment_ids(_hero_matrix()) == [
        "note-progress-031", "treatment-note-022", "order-901", "policy-snapshot-NST-IMG-2026-04",
    ]


def test_attachment_ids_excludes_condition_citations():
    # R1 cites both Condition/condition-100 and a DocumentReference; only the DocumentReference
    # is attached (data-model.md §3: "Condition resources are cited in the letter but not attached").
    ids = attachment_ids(_hero_matrix())
    assert not any("condition" in i for i in ids)


def test_render_pdf_is_deterministic_and_contains_expected_text():
    letter = _hero_letter()

    pdf_1 = render_pdf(letter)
    pdf_2 = render_pdf(letter)

    assert pdf_1 == pdf_2

    text = pdf_1.decode("latin-1")
    assert "SYNTHETIC DEMO DATA" in text
    assert "reconsider and reprocess payment" in text
    assert "v1" in text


def test_render_html_returns_a_string_with_the_key_content():
    html = render_html(_hero_letter())

    assert isinstance(html, str)
    assert "SYNTHETIC DEMO DATA" in html
    assert "Please reconsider and reprocess payment" in html
    assert "note-progress-031" in html


def test_status_lines_match_a9_step_5():
    assert status_line(blocked=False) == "Ready for review"
    assert completeness_line(_hero_matrix()) == "Evidence completeness: 3/3 policy criteria satisfied"
    assert recovery_line(HERO_CASE) == "Expected recovery: $4,800"
