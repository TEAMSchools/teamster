from teamster.libraries.finalsite.api.assets import get_finalsite_since


def test_since_subtracts_the_safety_day():
    assert get_finalsite_since("2026-08-11") == "2026-08-10"


def test_since_crosses_a_month_boundary():
    assert get_finalsite_since("2026-08-01") == "2026-07-31"


def test_since_crosses_a_year_boundary():
    assert get_finalsite_since("2026-01-01") == "2025-12-31"
