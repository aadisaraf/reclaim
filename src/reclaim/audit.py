from reclaim.config import Settings
from reclaim.repo import Repo


def _secret_values(settings: Settings) -> list[str]:
    return [v for v in [
        settings.openai_api_key, settings.payer_token,
        settings.hospital_client_secret, settings.sftp_password,
    ] if v]


def write_event(
    repo: Repo, settings: Settings, case_id: str | None, step: str, summary: str,
    detail: dict | None = None, ehr_requests: list[str] | None = None,
    llm_usage: dict | None = None,
) -> None:
    for secret in _secret_values(settings):
        if secret in summary or secret in str(detail or {}):
            raise ValueError("audit event must not contain a secret value")
    repo.insert_audit_event(case_id, step, summary, detail, ehr_requests, llm_usage)


def list_events(repo: Repo, case_id: str | None) -> list[dict]:
    return repo.list_events(case_id)
