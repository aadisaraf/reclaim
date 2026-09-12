from pathlib import Path

import httpx
import pytest

from reclaim.adapters.fhir import HttpEhrClient
from reclaim.adapters.payer import NorthstarPayerAdapter
from reclaim.config import Settings
from reclaim.repo import Repo

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def settings() -> Settings:
    return Settings.from_env()


@pytest.fixture
def repo(tmp_path) -> Repo:
    r = Repo(str(tmp_path / "reclaim.db"))
    r.init_schema()
    return r


@pytest.fixture
def fixtures_dir() -> Path:
    return REPO_ROOT / "fixtures"


@pytest.fixture
def fixture_ehr_client(settings: Settings) -> HttpEhrClient:
    from mocks.hospital import app as hospital_app

    hospital_app.reset_state()
    transport = httpx.ASGITransport(app=hospital_app.app)
    base = "http://mock-hospital.example"
    client = HttpEhrClient(
        base_url=f"{base}/fhir/R4", token_url=f"{base}/auth/token",
        client_id=settings.hospital_client_id, client_secret=settings.hospital_client_secret,
        transport=transport,
    )
    yield client
    hospital_app.reset_state()


@pytest.fixture
def fixture_payer_adapter(settings: Settings) -> NorthstarPayerAdapter:
    from mocks.northstar import app as payer_app

    payer_app.reset_state()
    transport = httpx.ASGITransport(app=payer_app.app)
    adapter = NorthstarPayerAdapter(
        base_url="http://mock-northstar-health.example/api/v1",
        token=settings.payer_token, transport=transport,
    )
    yield adapter
    payer_app.reset_state()
