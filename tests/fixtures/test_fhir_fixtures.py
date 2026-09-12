"""Validation tests for the FHIR R4 fixtures (Appendix A5).

Every fixtures/fhir/*.json file must parse with the corresponding
fhir.resources.R4B model, and Appendix A5's stated values are checked by
hand (never derived from another fixture file).
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from fhir.resources.R4B.binary import Binary
from fhir.resources.R4B.condition import Condition
from fhir.resources.R4B.coverage import Coverage
from fhir.resources.R4B.diagnosticreport import DiagnosticReport
from fhir.resources.R4B.documentreference import DocumentReference
from fhir.resources.R4B.encounter import Encounter
from fhir.resources.R4B.observation import Observation
from fhir.resources.R4B.organization import Organization
from fhir.resources.R4B.patient import Patient
from fhir.resources.R4B.practitioner import Practitioner
from fhir.resources.R4B.procedure import Procedure
from fhir.resources.R4B.servicerequest import ServiceRequest

FHIR_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "fhir"


def _load_raw(filename: str) -> dict:
    with open(FHIR_DIR / filename, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_text(filename: str) -> str:
    with open(FHIR_DIR / filename, "r", encoding="utf-8") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# Generic: every fixtures/fhir/*.json file parses with its R4B model
# ---------------------------------------------------------------------------

_MODEL_BY_RESOURCE_TYPE = {
    "Patient": Patient,
    "Coverage": Coverage,
    "Practitioner": Practitioner,
    "Organization": Organization,
    "Encounter": Encounter,
    "Condition": Condition,
    "DiagnosticReport": DiagnosticReport,
    "Observation": Observation,
    "ServiceRequest": ServiceRequest,
    "Procedure": Procedure,
    "DocumentReference": DocumentReference,
    "Binary": Binary,
}


def test_every_fhir_fixture_file_parses_with_its_r4b_model():
    files = sorted(FHIR_DIR.glob("*.json"))
    assert files, "expected fixtures/fhir/*.json files to exist"
    checked = 0
    for path in files:
        raw = json.loads(path.read_text(encoding="utf-8"))
        resource_type = raw["resourceType"]
        model = _MODEL_BY_RESOURCE_TYPE[resource_type]
        # Raises if invalid; this is the parse check.
        model.model_validate(raw)
        checked += 1
    assert checked == len(files)


def test_no_medication_request_fixture_exists():
    """A5: MedicationRequest search returns 0 results; there is no fixture file."""
    matches = list(FHIR_DIR.glob("MedicationRequest*.json"))
    assert matches == []


# ---------------------------------------------------------------------------
# Patient
# ---------------------------------------------------------------------------


def test_patient_0042_mrn():
    raw = _load_raw("Patient-patient-0042.json")
    patient = Patient.model_validate(raw)
    assert patient.id == "patient-0042"
    mrn_identifiers = [i for i in patient.identifier if i.value == "MRN-0042"]
    assert len(mrn_identifiers) == 1
    assert mrn_identifiers[0].type.coding[0].code == "MR"
    assert patient.birthDate.isoformat() == "1980-02-14"
    assert patient.name[0].family == "Rivera"
    assert patient.name[0].given == ["Jordan"]


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------


def test_coverage_0042_values():
    raw = _load_raw("Coverage-coverage-0042.json")
    coverage = Coverage.model_validate(raw)
    assert coverage.id == "coverage-0042"
    assert coverage.status == "active"
    assert coverage.beneficiary.reference == "Patient/patient-0042"
    assert coverage.subscriberId == "MEMBER-448820"

    payor_identifiers = [p.identifier.value for p in coverage.payor if p.identifier]
    assert "NSTHLTH01" in payor_identifiers

    plan_classes = [c for c in coverage.class_fhir if c.type.coding[0].code == "plan"]
    assert len(plan_classes) == 1
    assert plan_classes[0].name == "Commercial PPO"

    group_classes = [c for c in coverage.class_fhir if c.type.coding[0].code == "group"]
    assert len(group_classes) == 1
    assert group_classes[0].name == "NST-PPO-GRP-01"


# ---------------------------------------------------------------------------
# Practitioner / Organization
# ---------------------------------------------------------------------------


def test_practitioner_lee_npi():
    raw = _load_raw("Practitioner-practitioner-lee.json")
    practitioner = Practitioner.model_validate(raw)
    assert practitioner.id == "practitioner-lee"
    npi_values = [i.value for i in practitioner.identifier]
    assert "1234567893" in npi_values


def test_organization_mock_hospital_npi_and_state():
    raw = _load_raw("Organization-mock-hospital.json")
    org = Organization.model_validate(raw)
    assert org.id == "mock-hospital"
    npi_values = [i.value for i in org.identifier]
    assert "1245319599" in npi_values
    assert org.address[0].state == "WA"


# ---------------------------------------------------------------------------
# Encounter
# ---------------------------------------------------------------------------


def test_encounter_20260810_42_period_and_subject():
    raw = _load_raw("Encounter-encounter-20260810-42.json")
    encounter = Encounter.model_validate(raw)
    assert encounter.id == "encounter-20260810-42"
    assert encounter.status == "finished"
    assert str(encounter.period.start) == "2026-08-10 09:00:00+00:00"
    assert encounter.period.start.isoformat().startswith("2026-08-10T09:00:00")
    assert encounter.subject.reference == "Patient/patient-0042"
    assert encounter.serviceProvider.reference == "Organization/mock-hospital"


# ---------------------------------------------------------------------------
# Condition
# ---------------------------------------------------------------------------


def test_condition_100_icd10_and_recorded_date():
    raw = _load_raw("Condition-condition-100.json")
    condition = Condition.model_validate(raw)
    assert condition.id == "condition-100"
    codes = [c.code for c in condition.code.coding]
    assert "M54.16" in codes
    assert condition.recordedDate.isoformat() == "2026-05-28"


# ---------------------------------------------------------------------------
# DiagnosticReport / Observation
# ---------------------------------------------------------------------------


def test_diagnostic_report_subject_and_date():
    raw = _load_raw("DiagnosticReport-report-xr-555.json")
    report = DiagnosticReport.model_validate(raw)
    assert report.id == "report-xr-555"
    assert report.subject.reference == "Patient/patient-0042"
    assert report.effectiveDateTime.isoformat() == "2026-05-28"


def test_observation_pain_loinc_value_and_subject():
    raw = _load_raw("Observation-obs-pain-7781.json")
    obs = Observation.model_validate(raw)
    assert obs.id == "obs-pain-7781"
    assert obs.subject.reference == "Patient/patient-0042"
    codes = [c.code for c in obs.code.coding]
    assert "72514-3" in codes
    assert obs.valueQuantity.value == 8
    assert obs.effectiveDateTime.isoformat() == "2026-08-10"


# ---------------------------------------------------------------------------
# ServiceRequest / Procedure
# ---------------------------------------------------------------------------


def test_service_request_order_901():
    raw = _load_raw("ServiceRequest-order-901.json")
    sr = ServiceRequest.model_validate(raw)
    assert sr.id == "order-901"
    codes = [c.code for c in sr.code.coding]
    assert "72148" in codes
    assert sr.authoredOn.isoformat() == "2026-08-10"
    assert sr.reasonReference[0].reference == "Condition/condition-100"
    assert sr.note is not None and len(sr.note) == 1
    assert sr.note[0].text.strip() != ""


def test_procedure_902_based_on_order_901():
    raw = _load_raw("Procedure-procedure-902.json")
    proc = Procedure.model_validate(raw)
    assert proc.id == "procedure-902"
    assert proc.basedOn[0].reference == "ServiceRequest/order-901"
    assert proc.performedDateTime.isoformat() == "2026-08-10"


# ---------------------------------------------------------------------------
# DocumentReference / Binary trio
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "doc_id,expected_date",
    [
        ("note-progress-031", "2026-08-10"),
        ("treatment-note-022", "2026-07-14"),
        ("note-ortho-2019-004", "2019-03-02"),
    ],
)
def test_document_reference_date_and_binary_url(doc_id, expected_date):
    raw = _load_raw(f"DocumentReference-{doc_id}.json")
    doc_ref = DocumentReference.model_validate(raw)
    assert doc_ref.id == doc_id
    assert doc_ref.date.isoformat().startswith(expected_date)
    assert doc_ref.content[0].attachment.url == f"Binary/{doc_id}"


@pytest.mark.parametrize(
    "doc_id",
    ["note-progress-031", "treatment-note-022", "note-ortho-2019-004"],
)
def test_binary_is_text_plain_and_base64_decodes(doc_id):
    raw = _load_raw(f"Binary-{doc_id}.json")
    binary = Binary.model_validate(raw)
    assert binary.id == doc_id
    assert binary.contentType == "text/plain"
    # fhir.resources' base64Binary field decodes `data` to raw bytes on
    # validation, which is itself proof the raw JSON value was valid base64.
    # Also re-decode the raw JSON string ourselves as a belt-and-suspenders
    # check that it's valid, standard base64.
    decoded_by_model = binary.data
    assert isinstance(decoded_by_model, bytes)
    decoded_from_raw_json = base64.b64decode(raw["data"], validate=True)
    assert decoded_by_model == decoded_from_raw_json
    text = decoded_from_raw_json.decode("utf-8")
    assert text.strip() != ""


def _decoded_binary_text(doc_id: str) -> str:
    raw = _load_raw(f"Binary-{doc_id}.json")
    return base64.b64decode(raw["data"]).decode("utf-8")


def test_treatment_note_022_contains_required_substrings():
    text = _decoded_binary_text("treatment-note-022")
    for substring in ("6 weeks", "2026-06-02", "2026-07-14", "home exercise program"):
        assert substring in text, substring


def test_note_progress_031_does_not_mention_prior_treatment():
    """A1: the progress note must not describe prior treatment, so R2 depends
    only on treatment-note-022."""
    text = _decoded_binary_text("note-progress-031")
    for phrase in ("physical therapy", "conservative treatment", "prior treatment"):
        assert phrase not in text.lower()


def test_note_ortho_2019_004_contains_none_of_the_four_forbidden_words():
    """Per Appendix A: the unrelated 2019 ankle-sprain note (not the progress
    note) must contain none of these words, so it can never be mistaken for
    conservative-treatment evidence."""
    text = _decoded_binary_text("note-ortho-2019-004").lower()
    for word in ("therapy", "conservative", "medication", "exercise"):
        assert word not in text, word


@pytest.mark.parametrize(
    "doc_id",
    ["note-progress-031", "treatment-note-022"],
)
def test_synthetic_demo_data_label_present_in_note_binaries(doc_id):
    text = _decoded_binary_text(doc_id)
    assert "SYNTHETIC DEMO DATA" in text
