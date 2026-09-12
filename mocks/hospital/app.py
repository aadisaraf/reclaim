"""mock-hospital: a FastAPI FHIR R4 mock of a hospital EHR (SYNTHETIC DEMO DATA).

Loads every fixture in `fixtures/fhir/*.json` into memory at import time and serves them
back over a small slice of the FHIR R4 REST API, gated by a mock of SMART Backend Services
(client_credentials -> bearer token, checked against `Settings.hospital_client_id` /
`hospital_client_secret`, never hard-coded here).

Every `/fhir/R4/*` response (success or error) is `application/fhir+json`, and every
response from this app (including auth and control endpoints) carries
`X-Synthetic-Data: true` so nothing here can be mistaken for a real hospital record.
"""

from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from reclaim.config import Settings

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "fhir"

# Appendix A5: the scopes issued with every token, listing one resource-type scope per
# supported FHIR type plus a read-only scope for Binary.
SCOPES = (
    "system/Encounter.rs system/Patient.rs system/Coverage.rs system/Condition.rs "
    "system/ServiceRequest.rs system/Procedure.rs system/DiagnosticReport.rs "
    "system/Observation.rs system/DocumentReference.rs system/MedicationRequest.rs "
    "system/Binary.r"
)

# The contract supports `?patient=` search for exactly these 8 types. MedicationRequest has
# no fixture file on disk, so it always searches to an empty Bundle (an honest zero).
SEARCHABLE_TYPES = {
    "Coverage",
    "Condition",
    "ServiceRequest",
    "Procedure",
    "DiagnosticReport",
    "Observation",
    "DocumentReference",
    "MedicationRequest",
}

# FHIR fields that can carry a reference to the patient, depending on resource type
# (Coverage uses `beneficiary`, everything else here uses `subject`).
PATIENT_REFERENCE_FIELDS = ("subject", "beneficiary", "patient")

# The one DocumentReference/Binary pair the missing-evidence toggle hides.
HIDDEN_RESOURCE_ID = "treatment-note-022"
HIDDEN_RESOURCE_TYPES = ("DocumentReference", "Binary")


def _load_fixtures() -> dict[str, dict[str, Any]]:
    store: dict[str, dict[str, Any]] = {}
    for path in sorted(FIXTURES_DIR.glob("*.json")):
        resource = json.loads(path.read_text())
        store[f"{resource['resourceType']}/{resource['id']}"] = resource
    return store


def _operation_outcome(code: str, diagnostics: str) -> dict[str, Any]:
    return {
        "resourceType": "OperationOutcome",
        "issue": [{"severity": "error", "code": code, "diagnostics": diagnostics}],
    }


def _fhir_json(payload: dict[str, Any], status_code: int = 200) -> JSONResponse:
    return JSONResponse(content=payload, status_code=status_code, media_type="application/fhir+json")


app = FastAPI(
    title="mock-hospital",
    description="SYNTHETIC DEMO DATA -- mock FHIR R4 hospital EHR for the Reclaim hackathon demo.",
)

settings = Settings.from_env()
resources: dict[str, dict[str, Any]] = _load_fixtures()
issued_tokens: set[str] = set()
missing_evidence: bool = False


def reset_state() -> None:
    """Clears issued tokens and the missing-evidence toggle. Fixtures never need reloading
    since they are static. Used by `POST /_control/reset` and by tests for isolation."""
    global missing_evidence
    issued_tokens.clear()
    missing_evidence = False


@app.middleware("http")
async def add_synthetic_data_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Synthetic-Data"] = "true"
    return response


def _require_token(authorization: str | None) -> JSONResponse | None:
    """Returns a 401 OperationOutcome if the bearer token is missing/unknown, else None."""
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
    if not token or token not in issued_tokens:
        return _fhir_json(_operation_outcome("login", "Missing, invalid, or unknown bearer token"), 401)
    return None


def _is_hidden(resource_type: str, resource_id: str) -> bool:
    return missing_evidence and resource_type in HIDDEN_RESOURCE_TYPES and resource_id == HIDDEN_RESOURCE_ID


def _matches_patient(resource: dict[str, Any], patient_id: str) -> bool:
    target = f"Patient/{patient_id}"
    for field in PATIENT_REFERENCE_FIELDS:
        value = resource.get(field)
        candidates = value if isinstance(value, list) else [value]
        for candidate in candidates:
            if isinstance(candidate, dict) and candidate.get("reference") in (target, patient_id):
                return True
    return False


# --- SMART discovery + auth (unauthenticated) -------------------------------------------


@app.get("/fhir/R4/.well-known/smart-configuration")
async def smart_configuration(request: Request) -> JSONResponse:
    base = str(request.base_url).rstrip("/")
    doc = {
        "issuer": f"{base}/fhir/R4",
        "token_endpoint": f"{base}/auth/token",
        "grant_types_supported": ["client_credentials"],
        "token_endpoint_auth_methods_supported": ["client_secret_post"],
        "scopes_supported": SCOPES.split(" "),
        "capabilities": ["client-confidential-symmetric"],
    }
    return _fhir_json(doc)


@app.post("/auth/token")
async def issue_token(
    grant_type: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(...),
    scope: str | None = Form(None),
) -> JSONResponse:
    if client_id != settings.hospital_client_id or client_secret != settings.hospital_client_secret:
        return JSONResponse(content={"error": "invalid_client"}, status_code=401)
    token = secrets.token_urlsafe(32)
    issued_tokens.add(token)
    return JSONResponse(
        content={
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": SCOPES,
        },
        status_code=200,
    )


# --- FHIR reads and searches (authenticated) --------------------------------------------


@app.get("/fhir/R4/{resource_type}/{resource_id}")
async def read_resource(resource_type: str, resource_id: str, authorization: str | None = Header(None)):
    error = _require_token(authorization)
    if error is not None:
        return error

    if _is_hidden(resource_type, resource_id):
        return _fhir_json(_operation_outcome("not-found", f"Unknown {resource_type}/{resource_id}"), 404)

    resource = resources.get(f"{resource_type}/{resource_id}")
    if resource is None:
        return _fhir_json(_operation_outcome("not-found", f"Unknown {resource_type}/{resource_id}"), 404)
    return _fhir_json(resource)


@app.get("/fhir/R4/{resource_type}")
async def search_resources(resource_type: str, request: Request, authorization: str | None = Header(None)):
    error = _require_token(authorization)
    if error is not None:
        return error

    params = dict(request.query_params)
    extra_params = set(params) - {"patient"}
    if extra_params or "patient" not in params:
        return _fhir_json(
            _operation_outcome("not-supported", "Only the `patient` search parameter is supported"), 400
        )

    # The contract supports search for exactly the 8 listed types. A search on any other
    # resourceType (Patient, Practitioner, Organization, Binary, or an unknown type) is not
    # part of the contract; we treat it the same as an unknown resource -- 404 not-found.
    if resource_type not in SEARCHABLE_TYPES:
        return _fhir_json(_operation_outcome("not-found", f"Search not supported for {resource_type}"), 404)

    patient_id = params["patient"].removeprefix("Patient/")
    matches = [
        resource
        for key, resource in resources.items()
        if key.startswith(f"{resource_type}/")
        and _matches_patient(resource, patient_id)
        and not _is_hidden(resource_type, resource["id"])
    ]

    bundle: dict[str, Any] = {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(matches),
        "link": [{"relation": "self", "url": str(request.url)}],
    }
    if matches:
        bundle["entry"] = [
            {"fullUrl": f"{resource_type}/{resource['id']}", "resource": resource, "search": {"mode": "match"}}
            for resource in matches
        ]
    return _fhir_json(bundle)


# --- Presenter-only control endpoints (not a production FHIR boundary) -------------------
#
# These exist purely to drive the demo's "missing evidence" narrative and are gated by the
# same bearer token as the FHIR routes, per the contract, even though they are not part of
# the FHIR API itself.


class MissingEvidenceToggle(BaseModel):
    enabled: bool


@app.put("/_control/missing-evidence")
async def set_missing_evidence(toggle: MissingEvidenceToggle, authorization: str | None = Header(None)):
    error = _require_token(authorization)
    if error is not None:
        return error
    global missing_evidence
    missing_evidence = toggle.enabled
    return {"enabled": missing_evidence}


@app.get("/_control/state")
async def get_control_state(authorization: str | None = Header(None)):
    error = _require_token(authorization)
    if error is not None:
        return error
    return {"missingEvidence": missing_evidence}


@app.post("/_control/reset")
async def control_reset(authorization: str | None = Header(None)):
    error = _require_token(authorization)
    if error is not None:
        return error
    reset_state()
    return {"enabled": missing_evidence}
