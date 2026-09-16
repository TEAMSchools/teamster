import csv
import json
from pathlib import Path

import pytest

from teamster.goal_setting.config import load_crosswalk, load_rules
from teamster.goal_setting.manifest import build
from teamster.goal_setting.outputs import summary_tables, write_run
from teamster.goal_setting.pipeline import FreshnessError, run_group

from .fixtures.roster_small import student, untested

REPO = Path(__file__).resolve().parents[2]
RULES = load_rules(REPO / "config/goal_setting/ay2026.yaml")
XW = load_crosswalk(REPO / "config/goal_setting/ps_programs.yaml")
GROUP = RULES.group("nj_math_1_2")
TARGETS = {("Newark", 1): 0.50}


def roster():
    # 10 students, one school, grade 1: 3 proficient, 4 approaching, 2 below, 1 untested
    return (
        [student(projected_level=5, projected_score=430 + i) for i in range(3)]
        + [
            student(
                projected_level=4,
                projected_score=400 + i,
                stretch_level=5 if i == 0 else 4,
            )
            for i in range(4)
        ]
        + [
            student(projected_level=3, projected_score=380, stretch_level=5),
            student(projected_level=2, projected_score=350, stretch_level=3),
        ]
        + [untested()]
    )


def test_run_group_assigns_every_student_once():
    p = run_group(GROUP, 2026, roster(), TARGETS, baseline=None)
    assert len(p.records) == 10
    assert all(r.bucket for r in p.records)
    # target 0.50 of 9 tested = 4.5 -> bp = (4.5 - 3) / 4 = 0.38 -> ceil(4 * 0.38) = 2
    assert sum(r.bucket == "Bucket 1" for r in p.records) == 3
    assert sum(r.bucket == "Bucket 2" for r in p.records) == 2
    # stretch reachers only: the left-out approaching student at 400 and the
    # below student at 380, both of whom reach level 5 with stretch growth
    assert sum(r.bucket == "Bucket 3" for r in p.records) == 2
    assert sum(r.bucket == "Bucket 4" for r in p.records) == 3
    assert {r.bucket4_outcome for r in p.records if r.bucket == "Bucket 4"} == {
        "below",
        "untested",
    }
    (g,) = p.goals
    assert g.bubble_parameter == 0.38 and g.n_to_move == 2 and g.goal == 0.56


def test_freshness_error_stops_before_compute():
    recs = [untested() for _ in range(10)]
    with pytest.raises(FreshnessError) as e:
        run_group(GROUP, 2026, recs, TARGETS, baseline=None)
    assert "tested share 0.00" in str(e.value)


def test_force_stale_records_override():
    recs = [untested() for _ in range(10)]
    p = run_group(GROUP, 2026, recs, TARGETS, baseline=None, force_stale=True)
    assert p.gate.errors and all(r.bucket == "Bucket 4" for r in p.records)


def test_unimplemented_strategy_raises_naming_it():
    g = GROUP.model_copy(update={"school_goal": "flat"})
    with pytest.raises(NotImplementedError) as e:
        run_group(g, 2026, roster(), TARGETS, baseline=None)
    assert "flat" in str(e.value)


def test_manifest_has_no_student_identifiers_and_counts_bucket4_outcomes():
    p = run_group(GROUP, 2026, roster(), TARGETS, baseline=None)
    m = build(
        p,
        rules_sha="r" * 40,
        crosswalk_sha="c" * 40,
        inputs=[],
        diff=None,
        force_stale=False,
    )
    text = json.dumps(m)
    for r in p.records:
        assert str(r.student_number) not in text
    outcomes = {(b["bucket"], b["bucket4_outcome"]): b["n"] for b in m["bucket_counts"]}
    assert (
        outcomes[("Bucket 4", "untested")] == 1 and outcomes[("Bucket 4", "below")] == 2
    )
    assert m["bubble_parameters"] == [
        {"region": "Newark", "grade_level": 1, "bubble_parameter": 0.38}
    ]
    assert m["group"] == "nj_math_1_2" and m["rollout_date"] == "2026-10-15"


def test_write_run_writes_five_files_in_expected_shapes(tmp_path):
    p = run_group(GROUP, 2026, roster(), TARGETS, baseline=None)
    m = build(p, "r" * 40, "c" * 40, [], None, False)
    written = write_run(tmp_path, p, m, XW)
    names = sorted(f.name for f in written)
    assert names == [
        "explain.csv",
        "manifest.json",
        "ps_programs.csv",
        "school_goals.csv",
        "student_buckets.csv",
    ]

    goals = list(csv.DictReader((tmp_path / "school_goals.csv").open()))
    assert list(goals[0]) == [
        "Academic_Year",
        "School_ID",
        "Grade_Level",
        "Illuminate_Subject_Area",
        "School_Goal",
        "Grade_Band_Goal",
    ]
    assert (
        goals[0]["Illuminate_Subject_Area"] == "Mathematics"
        and goals[0]["School_Goal"] == "0.56"
    )

    programs = list(csv.DictReader((tmp_path / "ps_programs.csv").open()))
    assert list(programs[0]) == [
        "region",
        "student_number",
        "programid",
        "enter_date",
        "exit_date",
    ]
    assert len(programs) == 7  # buckets 1-3 only
    assert {p_["programid"] for p_ in programs} == {"7577", "7375", "7574"}
    assert (
        programs[0]["enter_date"] == "2026-07-01"
        and programs[0]["exit_date"] == "2027-06-30"
    )

    explain = list(csv.DictReader((tmp_path / "explain.csv").open()))
    assert list(explain[0]) == [
        "region",
        "student_number",
        "subject",
        "bucket",
        "reason",
    ]
    assert all(e["reason"] for e in explain)

    sb = list(csv.DictReader((tmp_path / "student_buckets.csv").open()))
    assert "bucket4_outcome" in sb[0] and "rank" in sb[0] and "projected_score" in sb[0]


def test_summary_tables_mention_school_and_untested_count():
    p = run_group(GROUP, 2026, roster(), TARGETS, baseline=None)
    text = summary_tables(p)
    assert "TEAM" in text and "untested" in text and "0.38" in text
