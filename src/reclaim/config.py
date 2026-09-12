import os
from dataclasses import dataclass, field
from typing import Literal

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    llm_mode: Literal["live", "replay"] = "replay"
    openai_model: str = "gpt-5.6-luna"
    openai_api_key: str = ""
    effort_build_matrix: Literal["low", "medium", "high"] = "medium"
    effort_draft_packet: Literal["low", "medium", "high"] = "low"
    llm_concurrency: int = 4

    price_input_per_m: float = 0.20
    price_cached_input_per_m: float = 0.02
    price_output_per_m: float = 1.20

    demo_today: str = "2026-09-12"

    ehr_base_url: str = "http://mock-hospital.example/fhir/R4"
    payer_base_url: str = "http://mock-northstar-health.example/api/v1"

    sftp_host: str = "mock-clearinghouse"
    sftp_port: int = 22
    sftp_user: str = "reclaim"
    sftp_password: str = ""

    hospital_client_id: str = "reclaim"
    hospital_client_secret: str = ""
    payer_token: str = ""

    database_path: str = ".local/reclaim.db"
    next_public_api_base: str = "http://localhost:8000"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            llm_mode=_env("LLM_MODE", "replay"),  # type: ignore[arg-type]
            openai_model=_env("OPENAI_MODEL", "gpt-5.6-luna"),
            openai_api_key=_env("OPENAI_API_KEY", ""),
            effort_build_matrix=_env("EFFORT_BUILD_MATRIX", "medium"),  # type: ignore[arg-type]
            effort_draft_packet=_env("EFFORT_DRAFT_PACKET", "low"),  # type: ignore[arg-type]
            llm_concurrency=int(_env("LLM_CONCURRENCY", "4")),
            price_input_per_m=float(_env("PRICE_INPUT_PER_M", "0.20")),
            price_cached_input_per_m=float(_env("PRICE_CACHED_INPUT_PER_M", "0.02")),
            price_output_per_m=float(_env("PRICE_OUTPUT_PER_M", "1.20")),
            demo_today=_env("DEMO_TODAY", "2026-09-12"),
            ehr_base_url=_env("EHR_BASE_URL", "http://mock-hospital.example/fhir/R4"),
            payer_base_url=_env("PAYER_BASE_URL", "http://mock-northstar-health.example/api/v1"),
            sftp_host=_env("SFTP_HOST", "mock-clearinghouse"),
            sftp_port=int(_env("SFTP_PORT", "22")),
            sftp_user=_env("SFTP_USER", "reclaim"),
            sftp_password=_env("SFTP_PASSWORD", ""),
            hospital_client_id=_env("HOSPITAL_CLIENT_ID", "reclaim"),
            hospital_client_secret=_env("HOSPITAL_CLIENT_SECRET", ""),
            payer_token=_env("PAYER_TOKEN", ""),
            database_path=_env("DATABASE_PATH", ".local/reclaim.db"),
            next_public_api_base=_env("NEXT_PUBLIC_API_BASE", "http://localhost:8000"),
        )

    def public(self) -> dict:
        return {
            "demoDate": self.demo_today,
            "aiMode": self.llm_mode,
            "model": self.openai_model,
            "baseUrls": {
                "ehr": self.ehr_base_url,
                "payer": self.payer_base_url,
                "app": self.next_public_api_base,
            },
        }
