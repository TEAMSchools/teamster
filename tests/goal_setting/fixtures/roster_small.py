"""Synthetic student rows for rule tests. No real students."""

from teamster.goal_setting.records import StudentRecord

_NEXT = iter(range(100001, 200000))


def student(**overrides) -> StudentRecord:
    base = StudentRecord(
        region="Newark",
        student_number=next(_NEXT),
        school="TEAM",
        school_id=133570965,
        grade_level=1,
        subject="Math",
        is_tested=True,
        projected_level=4,
        projected_score=405.0,
        stretch_level=4,
        assessment="i-Ready BOY",
    )
    return base.with_(**overrides)


def untested(**overrides) -> StudentRecord:
    return student(
        is_tested=False,
        projected_level=None,
        projected_score=None,
        stretch_level=None,
        **overrides,
    )
