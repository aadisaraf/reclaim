import os

from reclaim.config import Settings


def test_defaults_match_env_example():
    s = Settings()
    assert s.demo_today == "2026-09-12"
    assert s.llm_mode == "replay"
    assert s.openai_model == "gpt-5.6-luna"
    assert s.effort_build_matrix == "medium"
    assert s.effort_draft_packet == "low"
    assert s.llm_concurrency == 4
    assert s.price_input_per_m == 0.20
    assert s.price_cached_input_per_m == 0.02
    assert s.price_output_per_m == 1.20


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "live")
    monkeypatch.setenv("DEMO_TODAY", "2030-01-01")
    s = Settings.from_env()
    assert s.llm_mode == "live"
    assert s.demo_today == "2030-01-01"


def test_public_excludes_secrets():
    s = Settings(
        openai_api_key="secret-key",
        payer_token="payer-secret",
        hospital_client_secret="hosp-secret",
        sftp_password="sftp-secret",
    )
    public = s.public()
    dump = repr(public)
    for secret in ["secret-key", "payer-secret", "hosp-secret", "sftp-secret"]:
        assert secret not in dump
    assert public["demoDate"] == "2026-09-12"
    assert public["aiMode"] == "replay"
    assert public["model"] == "gpt-5.6-luna"
    assert "baseUrls" in public
