"""Region targets from the academic goals sheet, or inline from the rules file."""

from __future__ import annotations

from teamster.goal_setting.adapters import sql_list
from teamster.goal_setting.config import Group

GOALS = "`teamster-332318.kipptaf_assessments.int_assessments__academic_goals`"
ILLUMINATE_AREAS = {
    "Math": ["Mathematics"],
    "Reading": ["Text Study", "English Language Arts"],
}
Targets = dict[tuple[str, int], float]


class MissingTargets(Exception):
    pass


def sql(group: Group, academic_year: int) -> str:
    # Interpolates only pydantic-validated rules-file values (region/grade/
    # subject/column), never external user input.
    # trunk-ignore(bandit/B608): see comment above
    return f"""
    select region, grade_level, max({group.target.column}) as target
    from {GOALS}
    where academic_year = {academic_year}
      and region in ({sql_list(group.regions)})
      and grade_level in ({sql_list(group.grades)})
      and illuminate_subject_area in ({sql_list(ILLUMINATE_AREAS[group.subject])})
    group by region, grade_level
    """


def targets_from_rows(rows: list[dict], group: Group) -> Targets:
    targets = {
        (r["region"], int(r["grade_level"])): float(r["target"])
        for r in rows
        if r["target"] is not None
    }
    missing = [
        f"{region} grade {grade}"
        for region in group.regions
        for grade in group.grades
        if (region, grade) not in targets
    ]
    if missing:
        raise MissingTargets(
            f"goals sheet has no {group.target.column} for {group.subject} in academic_year "
            "rows: "
            + ", ".join(missing)
            + ". Enter the region targets in the goals sheet, or set target.from: inline in "
            "the rules file."
        )
    return targets


def fetch_targets(client, group: Group, academic_year: int) -> Targets:
    rows = [dict(r) for r in client.query(sql(group, academic_year)).result()]
    return targets_from_rows(rows, group)


def inline_targets(group: Group) -> Targets:
    # Invariant already enforced by Target's model_validator (from_ == "inline"
    # requires values); this narrows the type.
    # trunk-ignore(bandit/B101): see comment above
    assert group.target.values is not None
    return {
        (region, int(grade)): float(v)
        for region, grades in group.target.values.items()
        for grade, v in grades.items()
    }
