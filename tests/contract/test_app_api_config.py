"""Contract tests for GET /api/health, GET /api/config, GET /api/personas, and CORS (T042)."""

import json

import httpx

from reclaim.context import AppContext
from reclaim.main import create_app


def _ctx(repo, settings) -> AppContext:
    return AppContext(
        repo=repo, settings=settings, remit_inbox=None, claim_archive=None,
        ehr_client=None, policy_store=None, payer_adapter=None, llm_client=None,
    )


async def test_health_returns_ok(repo, settings):
    app = create_app(settings, _ctx(repo, settings))

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health")

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


async def test_config_matches_schema_with_demo_date_and_replay_mode(repo, settings):
    app = create_app(settings, _ctx(repo, settings))

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/config")

    assert resp.status_code == 200
    body = resp.json()
    assert body["synthetic"] is True
    assert body["demoDate"] == "2026-09-12"
    assert body["aiMode"] == "replay"
    assert body["missingEvidence"] is False
    assert body["baseUrls"]["clearinghouse"] == f"sftp://{settings.sftp_host}:{settings.sftp_port}"
    assert body["baseUrls"]["ehr"] == settings.ehr_base_url
    assert body["baseUrls"]["payer"] == settings.payer_base_url


async def test_config_contains_no_secret_values(repo, settings):
    app = create_app(settings, _ctx(repo, settings))

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/config")

    body_text = json.dumps(resp.json())
    for secret in [
        settings.openai_api_key, settings.payer_token,
        settings.hospital_client_secret, settings.sftp_password,
    ]:
        if secret:
            assert secret not in body_text


async def test_personas_returns_exactly_the_two_demo_personas(repo, settings):
    app = create_app(settings, _ctx(repo, settings))

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/personas")

    assert resp.status_code == 200
    assert resp.json() == [
        {"userId": "billing-approver-01", "role": "authorized-billing-user", "canApprove": True},
        {"userId": "viewer-01", "role": "viewer", "canApprove": False},
    ]


async def test_cors_allows_localhost_3000(repo, settings):
    app = create_app(settings, _ctx(repo, settings))

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health", headers={"Origin": "http://localhost:3000"})

    assert resp.headers["access-control-allow-origin"] == "http://localhost:3000"
