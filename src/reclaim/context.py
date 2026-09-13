from dataclasses import dataclass, field

from reclaim.adapters.protocols import ClaimArchive, EhrClient, LlmClient, PayerAdapter, PolicyStore, RemitInbox
from reclaim.config import Settings
from reclaim.repo import Repo


@dataclass
class AppContext:
    repo: Repo
    settings: Settings
    remit_inbox: RemitInbox
    claim_archive: ClaimArchive
    ehr_client: EhrClient
    policy_store: PolicyStore
    payer_adapter: PayerAdapter
    llm_client: LlmClient
    claim_map_path: str = "fixtures/claim-map.json"
    poller_seen: set = field(default_factory=set)
