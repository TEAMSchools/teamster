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


SY27_TARGETS = {
    ("Newark", 1): 0.35,
    ("Camden", 1): 0.35,
    ("Paterson", 1): 0.25,
    ("Newark", 2): 0.24,
    ("Camden", 2): 0.22,
    ("Paterson", 2): 0.24,
}

# Rows where the one-off's Bucket 2 count exceeds its own n_bubble_to_move,
# which only happens when students tie at the cutoff and `ties: admit` lets
# them all in. The synthetic roster gives every approaching student a distinct
# score, so it cannot reproduce those ties from the aggregate fixture alone:
# the tied scores are per-student data the fixture does not carry.
FIXTURE_TIE_ROWS = {
    ("Newark", "KURA", 1),
    ("Newark", "Life", 1),
    ("Newark", "Life", 2),
    ("Newark", "SPARK", 2),
    ("Newark", "Seek", 1),
    ("Newark", "THRIVE", 1),
    ("Newark", "THRIVE", 2),
}


def _fixture_rows() -> list[dict]:
    path = Path(__file__).parent / "fixtures" / "nj_math_1_2_ay2026_school_goals.csv"
    with path.open() as fh:
        return list(csv.DictReader(fh))


def _synthetic_roster(rows: list[dict]) -> list:
    """One student per roster seat, built from a fixture row's aggregates."""
    school_ids: dict[tuple[str, str], int] = {}
    out = []
    for r in rows:
        where = dict(
            region=r["region"],
            school=r["school"],
            grade_level=int(r["grade_level"]),
            subject="Math",
            school_id=school_ids.setdefault(
                (r["region"], r["school"]), len(school_ids) + 1
            ),
        )
        n_roster, n_tested = int(r["n_roster"]), int(r["n_tested"])
        n_prof, n_appr = int(r["n_projected_proficient"]), int(r["n_early_on"])
        n_below = n_tested - n_prof - n_appr

        proficient = [
            student(
                **where, projected_level=5, projected_score=500 - i, stretch_level=5
            )
            for i in range(n_prof)
        ]
        # distinct descending scores, so ranking has no ties to resolve
        approaching = [
            student(
                **where, projected_level=4, projected_score=412 - i, stretch_level=4
            )
            for i in range(n_appr)
        ]
        below = [
            student(
                **where, projected_level=3, projected_score=300 - i, stretch_level=4
            )
            for i in range(n_below)
        ]

        # Bucket 3 is the stretch reachers among students Buckets 1 and 2 leave
        # behind: lowest-scoring approaching first, then below.
        n_admitted = min(int(r["n_bubble_to_move"]), n_appr)
        leftover = list(reversed(approaching[n_admitted:])) + below
        for s in leftover[: int(r["bucket_3"])]:
            out.append(s.with_(stretch_level=5))
        out += proficient + approaching[:n_admitted] + leftover[int(r["bucket_3"]) :]
        out += [untested(**where) for _ in range(n_roster - n_tested)]
    return out


def test_pipeline_reproduces_sy27_bucket_counts_from_synthetic_roster():
    rows = _fixture_rows()
    p = run_group(GROUP, 2026, _synthetic_roster(rows), SY27_TARGETS, baseline=None)

    goals = {(g.region, g.school, g.grade_level): g for g in p.goals}
    counts: dict[tuple, dict[str, int]] = {}
    for rec in p.records:
        by_bucket = counts.setdefault((rec.region, rec.school, rec.grade_level), {})
        by_bucket[rec.bucket] = by_bucket.get(rec.bucket, 0) + 1

    assert len(goals) == len(rows) == 16
    ties = set()
    for r in rows:
        key = (r["region"], r["school"], int(r["grade_level"]))
        g = goals[key]
        assert g.bubble_parameter == float(r["bubble_parameter"]), key
        assert g.n_to_move == int(r["n_bubble_to_move"]), key
        assert g.goal == float(r["school_goal"]), key

        c = counts[key]
        expected_b2 = min(int(r["n_bubble_to_move"]), int(r["n_early_on"]))
        assert c.get("Bucket 1", 0) == int(r["bucket_1"]), key
        assert c.get("Bucket 2", 0) == expected_b2, key
        assert c.get("Bucket 3", 0) == int(r["bucket_3"]), key
        assert c.get("Bucket 4", 0) == int(r["n_roster"]) - sum(
            (
                int(r["bucket_1"]),
                expected_b2,
                int(r["bucket_3"]),
            )
        ), key
        if expected_b2 != int(r["bucket_2"]):
            ties.add(key)

    # Every row the synthetic roster cannot match is a row the one-off admitted
    # extra students into on a tie. If this set changes, the rules changed.
    assert ties == FIXTURE_TIE_ROWS


def test_write_run_writes_nothing_when_a_program_id_is_missing(tmp_path):
    from teamster.goal_setting.config import ConfigError, Crosswalk

    p = run_group(GROUP, 2026, roster(), TARGETS, baseline=None)
    m = build(p, "r" * 40, "c" * 40, [], None, False)
    empty = Crosswalk(programs=[])
    with pytest.raises(ConfigError) as e:
        write_run(tmp_path / "run", p, m, empty)
    assert "Newark Math Bucket 1" in str(e.value)
    assert not (tmp_path / "run").exists()


def test_summary_tables_mention_school_and_untested_count():
    p = run_group(GROUP, 2026, roster(), TARGETS, baseline=None)
    text = summary_tables(p)
    assert "TEAM" in text and "untested" in text and "0.38" in text
