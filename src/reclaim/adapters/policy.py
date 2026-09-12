import json
from datetime import date
from pathlib import Path

from reclaim.adapters.protocols import PolicySelection
from reclaim.models import Policy

SELECTOR_ORDER = ["payerId", "planType", "state", "procedureCode", "dateOfService"]


class FilePolicyStore:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self._policies: list[Policy] = []
        for path in sorted(self.directory.glob("*.json")):
            self._policies.append(Policy.model_validate_json(path.read_text()))

    def select(self, *, payer_id: str, plan_type: str, state: str,
               procedure_code: str, date_of_service: date) -> PolicySelection:
        first_failure: str | None = None
        for policy in self._policies:
            failure = self._first_mismatch(policy, payer_id, plan_type, state, procedure_code, date_of_service)
            if failure is None:
                return PolicySelection(policy=policy, failed_selector=None)
            if first_failure is None:
                first_failure = failure
        return PolicySelection(policy=None, failed_selector=first_failure or "payerId")

    @staticmethod
    def _first_mismatch(policy: Policy, payer_id: str, plan_type: str, state: str,
                         procedure_code: str, date_of_service: date) -> str | None:
        if policy.payerId != payer_id:
            return "payerId"
        if policy.planType != plan_type:
            return "planType"
        if state not in policy.states:
            return "state"
        if procedure_code not in policy.procedureCodes:
            return "procedureCode"
        start = date.fromisoformat(policy.effectiveStart)
        end = date.fromisoformat(policy.effectiveEnd) if policy.effectiveEnd else None
        if date_of_service < start or (end is not None and date_of_service > end):
            return "dateOfService"
        return None

    def snapshot_bytes(self, policy_id: str, version: str) -> bytes:
        policy = next(p for p in self._policies if p.policyId == policy_id and p.version == version)
        return json.dumps(policy.model_dump(), sort_keys=True, separators=(",", ":")).encode()
