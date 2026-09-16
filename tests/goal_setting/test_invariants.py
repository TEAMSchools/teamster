from dataclasses import replace

import pytest

from teamster.goal_setting.records import SchoolGoal
from teamster.goal_setting.rules.invariants import InvariantError, check

from .fixtures.roster_small import student

_DEFAULT_GOAL = SchoolGoal(
    region="Newark",
    school="TEAM",
    school_id=1,
    grade_level=1,
    subject="Math",
    n_roster=2,
    n_tested=2,
    n_proficient=1,
    n_approaching=1,
    n_below=0,
    target=0.5,
    bubble_parameter=0.0,
    n_to_move=0,
    goal=0.5,
)


def goal(**kw) -> SchoolGoal:
    return replace(_DEFAULT_GOAL, **kw)


def test_clean_proposal_passes():
    recs = [
        student(bucket="Bucket 1"),
        student(bucket="Bucket 4", bucket4_outcome="below"),
    ]
    check(recs, [goal()], {("Newark", 1): 0.5}, "bubble_parameter")


def test_duplicate_student_year_subject_aborts_naming_school():
    a = student(bucket="Bucket 1", student_number=7)
    b = a.with_(bucket="Bucket 2")
    with pytest.raises(InvariantError) as e:
        check([a, b], [goal()], {("Newark", 1): 0.5}, "bubble_parameter")
    msg = str(e.value)
    assert "Newark" in msg and "TEAM" in msg and "grade 1" in msg and "Math" in msg
    assert "2 rows" in msg and "Bucket 1, Bucket 2" in msg


def test_duplicate_rows_with_one_bucket_do_not_report_1_buckets():
    a = student(bucket="Bucket 1", student_number=7)
    with pytest.raises(InvariantError) as e:
        check([a, a], [goal()], {("Newark", 1): 0.5}, "bubble_parameter")
    msg = str(e.value)
    assert "1 buckets" not in msg
    assert "2 rows" in msg and "bucket(s) Bucket 1" in msg


def test_student_without_bucket_fails():
    with pytest.raises(InvariantError) as e:
        check(
            [student(bucket=None)], [goal()], {("Newark", 1): 0.5}, "bubble_parameter"
        )
    assert "no bucket" in str(e.value)


def test_missing_goal_row_for_a_school_grade_fails():
    recs = [student(bucket="Bucket 1"), student(bucket="Bucket 1", school="Rise")]
    with pytest.raises(InvariantError) as e:
        check(recs, [goal()], {("Newark", 1): 0.5}, "bubble_parameter")
    assert "Rise" in str(e.value) and "no goal row" in str(e.value)


def test_region_rollup_far_from_target_fails_for_bubble_parameter():
    recs = [
        student(bucket="Bucket 1"),
        student(bucket="Bucket 4", bucket4_outcome="below"),
    ]
    g = goal(n_proficient=1, n_to_move=0, n_tested=2)  # implied 0.50 vs target 0.80
    with pytest.raises(InvariantError) as e:
        check(recs, [g], {("Newark", 1): 0.80}, "bubble_parameter")
    assert "roll-up" in str(e.value) and "Newark" in str(e.value)


def test_region_rollup_check_skipped_for_blanket():
    recs = [
        student(bucket="Bucket 1"),
        student(bucket="Bucket 4", bucket4_outcome="below"),
    ]
    g = goal(n_proficient=1, n_to_move=0, n_tested=2)
    check(recs, [g], {("Newark", 1): 0.80}, "blanket")


def test_all_failures_are_reported_together():
    a = student(bucket=None, student_number=7)
    b = a.with_(bucket="Bucket 2")
    with pytest.raises(InvariantError) as e:
        check([a, b], [], {("Newark", 1): 0.5}, "blanket")
    assert len(e.value.failures) >= 3
