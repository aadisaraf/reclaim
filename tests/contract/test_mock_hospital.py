"""Contract tests for mocks/hospital/app.py, per specs/001-denial-recovery/contracts/mock-hospital-fhir.md.

Runs the real ASGI app in-process via httpx.ASGITransport -- no real network, no real
FHIR server.
"""

from __future__ import annotations

import httpx
import pytest

from mocks.hospital import app as hospital_app
from reclaim.config import Settings

BASE_URL = "http://mock-hospital.example"


@pytest.fixture(autouse=True)
def _reset_hospital_state():
    hospital_app.reset_state()
    yield
    hospital_app.reset_state()


@pytest.fixture
def settings() -> Settings:
    return Settings.from_env()


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=hospital_app.app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as c:
        yield c


async def _get_token(client: httpx.AsyncClient, settings: Settings) -> str:
    resp = await client.post(
        "/auth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": settings.hospital_client_id,
            "client_secret": settings.hospital_client_secret,
        },
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/fhir+json"}


# --- discovery + auth ----------------------------------------------------------------------


async def test_smart_configuration(client: httpx.AsyncClient):
    resp = await client.get("/fhir/R4/.well-known/smart-configuration")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/fhir+json")
    assert resp.headers["X-Synthetic-Data"] == "true"
    body = resp.json()
    assert body["token_endpoint"].endswith("/auth/token")
    assert body["grant_types_supported"] == ["client_credentials"]
    assert body["token_endpoint_auth_methods_supported"] == ["client_secret_post"]
    assert "system/Encounter.rs" in body["scopes_supported"]


async def test_token_good_credentials(client: httpx.AsyncClient, settings: Settings):
    resp = await client.post(
        "/auth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": settings.hospital_client_id,
            "client_secret": settings.hospital_client_secret,
        },
    )
    assert resp.status_code == 200
    assert resp.headers["X-Synthetic-Data"] == "true"
    body = resp.json()
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == 3600
    assert "system/Encounter.rs" in body["scope"]
    assert "system/Binary.r" in body["scope"]
    assert body["access_token"]


async def test_token_bad_credentials(client: httpx.AsyncClient):
    resp = await client.post(
        "/auth/token",
        data={"grant_type": "client_credentials", "client_id": "wrong", "client_secret": "wrong"},
    )
    assert resp.status_code == 401
    assert resp.json() == {"error": "invalid_client"}


async def test_missing_token_returns_login_operation_outcome(client: httpx.AsyncClient):
    resp = await client.get("/fhir/R4/Patient/patient-0042")
    assert resp.status_code == 401
    assert resp.headers["content-type"].startswith("application/fhir+json")
    body = resp.json()
    assert body["resourceType"] == "OperationOutcome"
    assert body["issue"][0]["code"] == "login"


async def test_invalid_token_returns_login_operation_outcome(client: httpx.AsyncClient):
    resp = await client.get("/fhir/R4/Patient/patient-0042", headers=_auth_headers("not-a-real-token"))
    assert resp.status_code == 401
    assert resp.json()["issue"][0]["code"] == "login"


# --- reads -----------------------------------------------------------------------------------


async def test_read_encounter(client: httpx.AsyncClient, settings: Settings):
    token = await _get_token(client, settings)
    resp = await client.get("/fhir/R4/Encounter/encounter-20260810-42", headers=_auth_headers(token))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/fhir+json")
    assert resp.headers["X-Synthetic-Data"] == "true"
    body = resp.json()
    assert body["resourceType"] == "Encounter"
    assert body["subject"]["reference"] == "Patient/patient-0042"


async def test_read_patient(client: httpx.AsyncClient, settings: Settings):
    token = await _get_token(client, settings)
    resp = await client.get("/fhir/R4/Patient/patient-0042", headers=_auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["resourceType"] == "Patient"
    assert body["identifier"][0]["value"] == "MRN-0042"


async def test_read_unknown_id_returns_404(client: httpx.AsyncClient, settings: Settings):
    token = await _get_token(client, settings)
    resp = await client.get("/fhir/R4/Patient/does-not-exist", headers=_auth_headers(token))
    assert resp.status_code == 404
    body = resp.json()
    assert body["resourceType"] == "OperationOutcome"
    assert body["issue"][0]["code"] == "not-found"


async def test_read_binary_is_text_plain(client: httpx.AsyncClient, settings: Settings):
    token = await _get_token(client, settings)
    resp = await client.get("/fhir/R4/Binary/note-progress-031", headers=_auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["resourceType"] == "Binary"
    assert body["contentType"] == "text/plain"
    assert body["data"]


# --- searches --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "resource_type,expected_total",
    [
        ("Coverage", 1),
        ("Condition", 1),
        ("ServiceRequest", 1),
        ("Procedure", 1),
        ("DiagnosticReport", 1),
        ("Observation", 1),
        ("DocumentReference", 3),
    ],
)
async def test_search_totals(client: httpx.AsyncClient, settings: Settings, resource_type: str, expected_total: int):
    token = await _get_token(client, settings)
    resp = await client.get(
        f"/fhir/R4/{resource_type}", params={"patient": "patient-0042"}, headers=_auth_headers(token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["resourceType"] == "Bundle"
    assert body["type"] == "searchset"
    assert body["total"] == expected_total
    assert len(body.get("entry", [])) == expected_total


async def test_search_medication_request_is_empty_with_no_entry_key(client: httpx.AsyncClient, settings: Settings):
    token = await _get_token(client, settings)
    resp = await client.get(
        "/fhir/R4/MedicationRequest", params={"patient": "patient-0042"}, headers=_auth_headers(token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert "entry" not in body


async def test_search_accepts_patient_reference_form(client: httpx.AsyncClient, settings: Settings):
    token = await _get_token(client, settings)
    resp = await client.get(
        "/fhir/R4/Condition", params={"patient": "Patient/patient-0042"}, headers=_auth_headers(token)
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


async def test_search_unsupported_param_returns_400(client: httpx.AsyncClient, settings: Settings):
    token = await _get_token(client, settings)
    resp = await client.get("/fhir/R4/Condition", params={"foo": "bar"}, headers=_auth_headers(token))
    assert resp.status_code == 400
    body = resp.json()
    assert body["resourceType"] == "OperationOutcome"
    assert body["issue"][0]["code"] == "not-supported"


async def test_search_missing_patient_param_returns_400(client: httpx.AsyncClient, settings: Settings):
    token = await _get_token(client, settings)
    resp = await client.get("/fhir/R4/Condition", headers=_auth_headers(token))
    assert resp.status_code == 400
    assert resp.json()["issue"][0]["code"] == "not-supported"


# --- missing-evidence toggle -------------------------------------------------------------------


async def test_missing_evidence_toggle_hides_and_reset_restores(client: httpx.AsyncClient, settings: Settings):
    token = await _get_token(client, settings)
    headers = _auth_headers(token)

    resp = await client.get("/fhir/R4/DocumentReference/treatment-note-022", headers=headers)
    assert resp.status_code == 200

    toggle_resp = await client.put("/_control/missing-evidence", json={"enabled": True}, headers=headers)
    assert toggle_resp.status_code == 200
    assert toggle_resp.json() == {"enabled": True}

    state_resp = await client.get("/_control/state", headers=headers)
    assert state_resp.json() == {"missingEvidence": True}

    search_resp = await client.get(
        "/fhir/R4/DocumentReference", params={"patient": "patient-0042"}, headers=headers
    )
    assert search_resp.json()["total"] == 2
    ids = {entry["resource"]["id"] for entry in search_resp.json()["entry"]}
    assert "treatment-note-022" not in ids

    doc_ref_resp = await client.get("/fhir/R4/DocumentReference/treatment-note-022", headers=headers)
    assert doc_ref_resp.status_code == 404
    assert doc_ref_resp.json()["issue"][0]["code"] == "not-found"

    binary_resp = await client.get("/fhir/R4/Binary/treatment-note-022", headers=headers)
    assert binary_resp.status_code == 404

    reset_resp = await client.post("/_control/reset", headers=headers)
    assert reset_resp.status_code == 200

    # reset() clears issued tokens too, so a fresh token is required after resetting.
    new_token = await _get_token(client, settings)
    new_headers = _auth_headers(new_token)

    state_after_reset = await client.get("/_control/state", headers=new_headers)
    assert state_after_reset.json() == {"missingEvidence": False}

    restored_search = await client.get(
        "/fhir/R4/DocumentReference", params={"patient": "patient-0042"}, headers=new_headers
    )
    assert restored_search.json()["total"] == 3

    restored_read = await client.get("/fhir/R4/DocumentReference/treatment-note-022", headers=new_headers)
    assert restored_read.status_code == 200
