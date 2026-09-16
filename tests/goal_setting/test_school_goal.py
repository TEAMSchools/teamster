import csv
from pathlib import Path

from teamster.goal_setting.rules.aggregate import SchoolCounts, count_by_school
from teamster.goal_setting.rules.school_goal import (
    blanket,
    bubble_parameter,
    region_parameters,
)

from .fixtures.roster_small import student, untested

FIX = Path(__file__).parent / "fixtures"

SY27_TARGETS = {
    ("Newark", 1): 0.35,
    ("Camden", 1): 0.35,
    ("Paterson", 1): 0.25,
    ("Newark", 2): 0.24,
    ("Camden", 2): 0.22,
    ("Paterson", 2): 0.24,
}


def _fixture_counts() -> list[SchoolCounts]:
    rows = list(csv.DictReader((FIX / "nj_math_1_2_ay2026_school_goals.csv").open()))
    out = []
    for r in rows:
        n_tested = int(r["n_tested"])
        n_prof = int(r["n_projected_proficient"])
        n_appr = int(r["n_early_on"])
        out.append(
            SchoolCounts(
                region=r["region"],
                school=r["school"],
                school_id=0,
                grade_level=int(r["grade_level"]),
                subject="Math",
                n_roster=int(r["n_roster"]),
                n_tested=n_tested,
                n_proficient=n_prof,
                n_approaching=n_appr,
                n_below=n_tested - n_prof - n_appr,
            )
        )
    return out


def test_count_by_school_groups_by_school_subject_grade():
    recs = [
        student(is_proficient=True),
        student(is_approaching=True),
        student(is_below=True),
        untested(),
        student(school="Rise", is_proficient=True),
    ]
    counts = {c.school: c for c in count_by_school(recs)}
    assert counts["TEAM"].n_roster == 4
    assert counts["TEAM"].n_tested == 3
    assert (
        counts["TEAM"].n_proficient,
        counts["TEAM"].n_approaching,
        counts["TEAM"].n_below,
    ) == (1, 1, 1)
    assert counts["Rise"].n_roster == 1


def test_region_parameters_reproduce_sy27():
    params = region_parameters(_fixture_counts(), SY27_TARGETS)
    rollup = list(csv.DictReader((FIX / "nj_math_1_2_ay2026_region_rollup.csv").open()))
    for r in rollup:
        assert params[(r["region"], int(r["grade_level"]))] == float(
            r["bubble_parameter"]
        ), r


def test_bubble_parameter_reproduces_sy27_school_goals_to_the_cent():
    goals = {
        (g.school, g.grade_level): g
        for g in bubble_parameter(_fixture_counts(), SY27_TARGETS)
    }
    rows = list(csv.DictReader((FIX / "nj_math_1_2_ay2026_school_goals.csv").open()))
    assert len(goals) == len(rows) == 16
    for r in rows:
        g = goals[(r["school"], int(r["grade_level"]))]
        assert g.bubble_parameter == float(r["bubble_parameter"]), r
        assert g.n_to_move == int(r["n_bubble_to_move"]), r
        assert g.goal == float(r["school_goal"]), r
        assert g.target == float(r["region_goal"]), r


def test_region_rollup_lands_within_a_point_of_target():
    goals = bubble_parameter(_fixture_counts(), SY27_TARGETS)
    by_region: dict[tuple[str, int], list] = {}
    for g in goals:
        by_region.setdefault((g.region, g.grade_level), []).append(g)
    for key, gs in by_region.items():
        implied = sum(g.n_proficient + g.n_to_move for g in gs) / sum(
            g.n_tested for g in gs
        )
        assert implied >= SY27_TARGETS[key] - 0.01
        assert implied <= SY27_TARGETS[key] + 0.03  # per-school ceiling overshoots


def test_bubble_parameter_zero_approaching_gives_none_and_zero_to_move():
    counts = [SchoolCounts("Newark", "TEAM", 1, 1, "Math", 10, 10, 2, 0, 8)]
    (g,) = bubble_parameter(counts, {("Newark", 1): 0.5})
    assert g.bubble_parameter is None and g.n_to_move == 0 and g.goal == 0.2


def test_blanket_sets_every_school_to_the_region_target():
    counts = [
        SchoolCounts("Newark", "TEAM", 1, 0, "Math", 20, 20, 6, 8, 6),
        SchoolCounts("Newark", "Rise", 2, 0, "Math", 10, 10, 8, 1, 1),
    ]
    goals = {g.school: g for g in blanket(counts, {("Newark", 0): 0.55})}
    # 0.55 * 20 - 6 is 5.000000000000002 in float64; the answer is 5, not 6
    assert goals["TEAM"].goal == 0.55 and goals["TEAM"].n_to_move == 5
    assert goals["Rise"].goal == 0.55 and goals["Rise"].n_to_move == 0
    assert goals["TEAM"].bubble_parameter is None
