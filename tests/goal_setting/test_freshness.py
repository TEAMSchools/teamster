from teamster.goal_setting.config import Freshness
from teamster.goal_setting.rules.aggregate import SchoolCounts
from teamster.goal_setting.rules.freshness import check

CFG = Freshness(min_tested_share=0.85, roster_tolerance=0.15)


def counts(n_roster=100, n_tested=95, school="TEAM", grade=1) -> SchoolCounts:
    return SchoolCounts("Newark", school, 1, grade, "Math", n_roster, n_tested, 0, 0, 0)


def test_clean_pass_with_baseline():
    res = check([counts()], CFG, {("Newark", "TEAM", 1): 100})
    assert res.ok and res.errors == [] and res.warnings == []


def test_low_tested_share_is_an_error_naming_school_and_numbers():
    res = check([counts(n_tested=60)], CFG, {("Newark", "TEAM", 1): 100})
    assert not res.ok
    assert "Newark TEAM grade 1 Math" in res.errors[0]
    assert "0.60" in res.errors[0] and "0.85" in res.errors[0]


def test_roster_far_below_baseline_is_an_error():
    res = check([counts(n_roster=50, n_tested=50)], CFG, {("Newark", "TEAM", 1): 100})
    assert not res.ok and "50" in res.errors[0] and "100" in res.errors[0]


def test_roster_above_baseline_is_a_warning_not_an_error():
    res = check([counts(n_roster=130, n_tested=125)], CFG, {("Newark", "TEAM", 1): 100})
    assert res.ok and res.warnings and "130" in res.warnings[0]


def test_school_missing_from_roster_but_in_baseline_is_an_error():
    res = check(
        [counts()], CFG, {("Newark", "TEAM", 1): 100, ("Newark", "Rise", 1): 80}
    )
    assert not res.ok and "Rise" in res.errors[0] and "0 students" in res.errors[0]
    assert "Math" in res.errors[0]


def test_roster_exactly_at_upper_tolerance_is_not_a_warning():
    res = check([counts(n_roster=115, n_tested=110)], CFG, {("Newark", "TEAM", 1): 100})
    assert res.ok and res.warnings == []


def test_roster_exactly_at_lower_tolerance_is_not_an_error():
    res = check([counts(n_roster=85, n_tested=85)], CFG, {("Newark", "TEAM", 1): 100})
    assert res.ok


def test_no_baseline_is_a_single_warning():
    res = check([counts()], CFG, None)
    assert res.ok and len(res.warnings) == 1 and "no baseline" in res.warnings[0]


def test_empty_roster_is_an_error():
    res = check([], CFG, None)
    assert not res.ok and "0 rows" in res.errors[0]
