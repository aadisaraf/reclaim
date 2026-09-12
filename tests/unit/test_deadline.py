from reclaim.steps.payer_context import compute_deadline, deadline_line


def test_compute_deadline_no_warning():
    d = compute_deadline(
        decision_date="2026-08-20", appeal_deadline="2026-10-19",
        window_days=60, today="2026-09-12",
    )
    assert d.days_left == 37
    assert d.policy_window_date == "2026-10-19"
    assert d.deadline_of_record == "2026-10-19"
    assert d.warning is None


def test_compute_deadline_warns_on_mismatch():
    d = compute_deadline(
        decision_date="2026-08-20", appeal_deadline="2026-10-15",
        window_days=60, today="2026-09-12",
    )
    assert d.deadline_of_record == "2026-10-15"
    assert d.policy_window_date == "2026-10-19"
    assert "October 15, 2026" in d.warning
    assert "October 19, 2026" in d.warning


def test_deadline_line():
    d = compute_deadline(
        decision_date="2026-08-20", appeal_deadline="2026-10-19",
        window_days=60, today="2026-09-12",
    )
    assert deadline_line(d) == "Appeal deadline: October 19, 2026 (37 days left)"
