from datetime import date

from reclaim.adapters.policy import FilePolicyStore


def store(fixtures_dir):
    return FilePolicyStore(fixtures_dir / "policies")


def test_selects_matching_policy(fixtures_dir):
    s = store(fixtures_dir)
    selection = s.select(
        payer_id="NSTHLTH01", plan_type="Commercial PPO", state="WA",
        procedure_code="72148", date_of_service=date(2026, 8, 10),
    )
    assert selection.policy is not None
    assert selection.policy.policyId == "NST-IMG-2026-04"
    assert selection.policy.version == "2026.04"
    assert selection.failed_selector is None


def test_wrong_payer_fails(fixtures_dir):
    s = store(fixtures_dir)
    selection = s.select(
        payer_id="OTHER01", plan_type="Commercial PPO", state="WA",
        procedure_code="72148", date_of_service=date(2026, 8, 10),
    )
    assert selection.policy is None
    assert selection.failed_selector == "payerId"


def test_wrong_plan_fails(fixtures_dir):
    s = store(fixtures_dir)
    selection = s.select(
        payer_id="NSTHLTH01", plan_type="Commercial HMO", state="WA",
        procedure_code="72148", date_of_service=date(2026, 8, 10),
    )
    assert selection.failed_selector == "planType"


def test_wrong_state_fails(fixtures_dir):
    s = store(fixtures_dir)
    selection = s.select(
        payer_id="NSTHLTH01", plan_type="Commercial PPO", state="OR",
        procedure_code="72148", date_of_service=date(2026, 8, 10),
    )
    assert selection.failed_selector == "state"


def test_wrong_procedure_fails(fixtures_dir):
    s = store(fixtures_dir)
    selection = s.select(
        payer_id="NSTHLTH01", plan_type="Commercial PPO", state="WA",
        procedure_code="72149", date_of_service=date(2026, 8, 10),
    )
    assert selection.failed_selector == "procedureCode"


def test_wrong_date_fails(fixtures_dir):
    s = store(fixtures_dir)
    selection = s.select(
        payer_id="NSTHLTH01", plan_type="Commercial PPO", state="WA",
        procedure_code="72148", date_of_service=date(2025, 12, 31),
    )
    assert selection.failed_selector == "dateOfService"


def test_snapshot_bytes_stable_sorted_json(fixtures_dir):
    s = store(fixtures_dir)
    a = s.snapshot_bytes("NST-IMG-2026-04", "2026.04")
    b = s.snapshot_bytes("NST-IMG-2026-04", "2026.04")
    assert a == b
    assert a.startswith(b'{"')
