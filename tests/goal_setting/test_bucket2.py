from teamster.goal_setting.records import SchoolGoal
from teamster.goal_setting.rules.bucket2 import none, top_approaching_to_move

from .fixtures.roster_small import student


def goal(n_to_move: int, school="TEAM", grade=1) -> SchoolGoal:
    return SchoolGoal(
        region="Newark",
        school=school,
        school_id=1,
        grade_level=grade,
        subject="Math",
        n_roster=0,
        n_tested=0,
        n_proficient=0,
        n_approaching=0,
        n_below=0,
        target=0.35,
        bubble_parameter=0.5,
        n_to_move=n_to_move,
        goal=0.4,
    )


def appr(score: float, **kw):
    return student(is_approaching=True, projected_score=score, **kw)


def test_top_n_by_projected_score_enter_bucket_2():
    recs = [appr(410), appr(405), appr(400), appr(395)]
    out = top_approaching_to_move(recs, [goal(2)], "admit")
    buckets = [r.bucket for r in sorted(out, key=lambda r: -(r.projected_score or 0))]
    assert buckets == ["Bucket 2", "Bucket 2", None, None]


def test_ties_at_cutoff_all_admitted():
    recs = [appr(410), appr(405), appr(405), appr(395)]
    out = top_approaching_to_move(recs, [goal(2)], "admit")
    assert sum(r.bucket == "Bucket 2" for r in out) == 3
    ranks = sorted(r.rank for r in out if r.rank is not None)
    assert ranks == [1, 2, 2, 4]


def test_ties_strict_breaks_by_student_number():
    a = appr(405, student_number=5)
    b = appr(405, student_number=3)
    out = {
        r.student_number: r
        for r in top_approaching_to_move([a, b], [goal(1)], "strict")
    }
    assert out[3].bucket == "Bucket 2" and out[5].bucket is None
    assert (out[3].rank, out[5].rank) == (1, 2)


def test_ranking_is_per_school_and_grade():
    recs = [appr(410), appr(400, school="Rise"), appr(390, grade_level=2)]
    goals = [goal(1), goal(1, school="Rise"), goal(1, grade=2)]
    out = top_approaching_to_move(recs, goals, "admit")
    assert all(r.bucket == "Bucket 2" for r in out)
    assert all(r.rank == 1 for r in out)


def test_non_approaching_students_get_no_rank():
    recs = [student(is_proficient=True, projected_score=430), appr(400)]
    out = {
        r.student_number: r for r in top_approaching_to_move(recs, [goal(5)], "admit")
    }
    prof = next(r for r in out.values() if r.is_proficient)
    assert prof.rank is None and prof.bucket is None


def test_zero_to_move_admits_nobody_but_still_ranks():
    out = top_approaching_to_move([appr(410), appr(400)], [goal(0)], "admit")
    assert all(r.bucket is None for r in out)
    assert sorted(r.rank for r in out if r.rank is not None) == [1, 2]


def test_reason_names_rank_and_n_to_move():
    (r,) = top_approaching_to_move([appr(409)], [goal(12)], "admit")
    assert r.reason == "approaching, projected 409, rank 1 of 12 to move"


def test_same_student_number_in_two_schools_is_ranked_independently():
    team = appr(500, school="TEAM", student_number=42)
    rise = appr(300, school="Rise", student_number=42)
    out = top_approaching_to_move(
        [team, rise], [goal(1, school="TEAM"), goal(5, school="Rise")], "admit"
    )
    by_school = {r.school: r for r in out}
    assert by_school["TEAM"].reason.endswith("rank 1 of 1 to move")
    assert by_school["Rise"].reason.endswith("rank 1 of 5 to move")
    assert by_school["TEAM"].bucket == "Bucket 2"
    assert by_school["Rise"].bucket == "Bucket 2"


def test_none_strategy_is_identity():
    recs = [appr(410)]
    assert none(recs, [goal(3)], "admit") == recs
