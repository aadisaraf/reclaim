"""Validation tests for the JSON fixtures (Appendix A4, A6, A7).

Each fixture's parsed JSON is compared against a dict literal hand-typed from
docs/reclaim-speckit-prompts.md. Nothing here is derived from another
fixture's file contents, so these checks can't pass by accident if two
fixtures merely agree with each other but disagree with the Appendix.
"""

from __future__ import annotations

import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"


def _load(relative_path: str) -> dict:
    with open(FIXTURES_DIR / relative_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def test_claim_map_json_matches_appendix_a4():
    expected = {
        "HSP-CLM-100028": {
            "patientId": "patient-0042",
            "mrn": "MRN-0042",
            "encounterId": "encounter-20260810-42",
            "dateOfService": "2026-08-10",
            "procedureCode": "72148",
            "diagnosisCode": "M54.16",
        }
    }
    actual = _load("claim-map.json")
    assert actual == expected


def test_policy_nst_img_2026_04_matches_appendix_a7():
    expected = {
        "policyId": "NST-IMG-2026-04",
        "version": "2026.04",
        "title": "Advanced imaging of the lumbar spine (SYNTHETIC)",
        "payer": "Northstar Health",
        "payerId": "NSTHLTH01",
        "planType": "Commercial PPO",
        "states": ["WA"],
        "procedureCodes": ["72148"],
        "effectiveStart": "2026-01-01",
        "effectiveEnd": None,
        "appealWindowDays": 60,
        "lookbackMonths": 6,
        "requirements": [
            {
                "id": "R1",
                "text": "Documented diagnosis that supports lumbar imaging, such as lumbar radiculopathy",
                "evidenceTypes": ["Condition", "DocumentReference"],
            },
            {
                "id": "R2",
                "text": "Documented trial of conservative treatment lasting at least 6 weeks within the 6 months before the date of service",
                "evidenceTypes": ["DocumentReference", "MedicationRequest"],
            },
            {
                "id": "R3",
                "text": "Clinical rationale for the imaging order from the treating clinician",
                "evidenceTypes": ["ServiceRequest", "DocumentReference"],
            },
        ],
        "sourceUrl": "https://example.org/mock-policy/NST-IMG-2026-04",
        "sourceRetrievedAt": "2026-09-12",
    }
    actual = _load("policies/NST-IMG-2026-04.json")
    assert actual == expected


def test_payer_decision_json_matches_appendix_a6_get_decision_200_body():
    expected = {
        "payerClaimId": "PAYER-CLM-99281",
        "claimId": "HSP-CLM-100028",
        "decision": "denied",
        "decisionDate": "2026-08-20",
        "reasonCode": "CO-50",
        "reasonText": "Insufficient documentation of medical necessity",
        "appealDeadline": "2026-10-19",
        "allowedSubmissionChannels": ["portal", "fax"],
        "letter": {
            "documentId": "denial-letter-99281",
            "url": "/api/v1/documents/denial-letter-99281",
        },
    }
    actual = _load("payer/payer-decision.json")
    assert actual == expected


def test_appeal_response_json_matches_appendix_a6_post_appeals_201_body():
    expected = {
        "appealId": "NST-APL-80126",
        "status": "received",
        "receivedAt": "2026-09-12T18:32:00Z",
        "expectedResolutionDays": 14,
    }
    actual = _load("payer/appeal-response.json")
    assert actual == expected
