"""Contract tests for adapters/fhir.py::HttpEhrClient against the real mock-hospital ASGI app."""

from __future__ import annotations

import httpx
import pytest

from mocks.hospital import app as hospital_app
from reclaim.adapters.fhir import HttpEhrClient
from reclaim.adapters.protocols import EhrNotFound
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
def ehr_client(settings: Settings) -> HttpEhrClient:
    transport = httpx.ASGITransport(app=hospital_app.app)
    return HttpEhrClient(
        base_url=f"{BASE_URL}/fhir/R4", token_url=f"{BASE_URL}/auth/token",
        client_id=settings.hospital_client_id, client_secret=settings.hospital_client_secret,
        transport=transport,
    )


async def test_token_fetched_once_and_reused(ehr_client: HttpEhrClient):
    await ehr_client.read("Patient", "patient-0042")
    await ehr_client.search("Condition", "patient-0042")
    assert len(hospital_app.issued_tokens) == 1


async def test_requests_made_records_exact_paths(ehr_client: HttpEhrClient):
    await ehr_client.read("Encounter", "encounter-20260810-42")
    await ehr_client.search("Coverage", "patient-0042")
    assert ehr_client.requests_made == [
        "GET /fhir/R4/Encounter/encounter-20260810-42",
        "GET /fhir/R4/Coverage?patient=patient-0042",
    ]


async def test_search_medication_request_returns_empty(ehr_client: HttpEhrClient):
    results = await ehr_client.search("MedicationRequest", "patient-0042")
    assert results == []


async def test_search_condition_returns_resources(ehr_client: HttpEhrClient):
    results = await ehr_client.search("Condition", "patient-0042")
    assert len(results) == 1
    assert results[0]["id"] == "condition-100"


async def test_read_binary_decodes_bytes(ehr_client: HttpEhrClient):
    binary = await ehr_client.read_binary("note-progress-031")
    assert binary.content_type == "text/plain"
    assert b"SYNTHETIC DEMO DATA" in binary.data


async def test_read_unknown_resource_raises_ehr_not_found(ehr_client: HttpEhrClient):
    with pytest.raises(EhrNotFound):
        await ehr_client.read("Patient", "patient-nonexistent")


async def test_read_binary_unknown_raises_ehr_not_found(ehr_client: HttpEhrClient):
    with pytest.raises(EhrNotFound):
        await ehr_client.read_binary("binary-nonexistent")
