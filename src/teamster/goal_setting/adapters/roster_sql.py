"""Roster and baseline queries shared by source adapters."""

from __future__ import annotations

from datetime import date

from teamster.goal_setting.adapters import QueryClient, sql_list
from teamster.goal_setting.config import Group
from teamster.goal_setting.rules.freshness import Baseline

ROSTER = "`teamster-332318.kipptaf_extracts.int_extracts__student_enrollments_subjects`"
SNAPSHOT = (
    "`teamster-332318.kipptaf_extracts"
    ".int_extracts__student_enrollments_subjects_weeks`"
)


def roster_where(group: Group, academic_year: int) -> str:
    return f"""
        co.academic_year = {academic_year}
        and co.rn_year = 1
        and co.enroll_status = 0
        and not co.is_exempt_state_testing
        and co.grade_level in ({sql_list(group.grades)})
        and co.region in ({sql_list(group.regions)})
        and co.iready_subject = '{group.subject}'
    """


def baseline_sql(group: Group, academic_year: int, as_of: date) -> str:
    """Roster count per school and grade as of a pinned week, for the year-one gate."""
    # Interpolates only pydantic-validated rules-file values (region/grade/
    # subject) and an ISO date, never external user input.
    # trunk-ignore(bandit/B608): see comment above
    return f"""
    select co.region, co.school, co.grade_level, count(distinct co.student_number) as n
    from {SNAPSHOT} as co
    where {roster_where(group, academic_year)}
      and co.week_start_monday <= '{as_of.isoformat()}'
      and co.week_end_sunday >= '{as_of.isoformat()}'
    group by co.region, co.school, co.grade_level
    """


def fetch_baseline(
    client: QueryClient, group: Group, academic_year: int, as_of: date
) -> Baseline:
    rows = client.query(baseline_sql(group, academic_year, as_of)).result()
    return {
        (r["region"], r["school"], int(r["grade_level"])): int(r["n"]) for r in rows
    }
