from datetime import date

from reclaim.steps.gather_evidence import lookback_window, resource_date


def test_lookback_window_hero_date():
    assert lookback_window(date(2026, 8, 10), 6) == (date(2026, 2, 10), date(2026, 8, 10))


def test_lookback_window_clamps_to_end_of_month():
    start, end = lookback_window(date(2026, 8, 31), 6)
    assert start == date(2026, 2, 28)
    assert end == date(2026, 8, 31)


def test_resource_date_per_type():
    assert resource_date("Condition", {"recordedDate": "2026-05-28", "onsetDateTime": "2026-05-20"}) == "2026-05-28"
    assert resource_date("Condition", {"onsetDateTime": "2026-05-20"}) == "2026-05-20"
    assert resource_date("DiagnosticReport", {"effectiveDateTime": "2026-05-28"}) == "2026-05-28"
    assert resource_date("DiagnosticReport", {"issued": "2026-05-28"}) == "2026-05-28"
    assert resource_date("Observation", {"effectiveDateTime": "2026-08-10"}) == "2026-08-10"
    assert resource_date("ServiceRequest", {"authoredOn": "2026-08-10"}) == "2026-08-10"
    assert resource_date("Procedure", {"performedDateTime": "2026-08-10"}) == "2026-08-10"
    assert resource_date("Procedure", {"performedPeriod": {"start": "2026-08-10"}}) == "2026-08-10"
    assert resource_date("DocumentReference", {"date": "2026-08-10T00:00:00Z"}) == "2026-08-10"
    assert resource_date("MedicationRequest", {"authoredOn": "2026-08-10"}) == "2026-08-10"


def test_resource_date_missing_returns_none():
    assert resource_date("Condition", {}) is None


def test_edge_of_window_included():
    start, end = lookback_window(date(2026, 8, 10), 6)
    assert start <= date(2026, 2, 10) <= end
    assert start <= date(2026, 8, 10) <= end


def test_outside_window_excluded():
    start, end = lookback_window(date(2026, 8, 10), 6)
    assert not (start <= date(2019, 3, 2) <= end)
