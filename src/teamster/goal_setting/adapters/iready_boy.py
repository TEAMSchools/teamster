"""i-Ready BOY diagnostic, projected with typical and stretch growth.

Adds annual_typical_growth_measure directly to the BOY scale score. That is
exact for a baseline diagnostic (gain is 0 by definition) and sidesteps the
null diagnostic_gain in staging for AY2026.

Rows with a NULL i-Ready region (124 in AY2026) will not match any roster
student under IREADY_REGION and so are correctly excluded from is_tested; the
real plan run compares the resulting tested count against the SY27 one-off
(1,522 tested for NJ grades 1-2 math) to quantify that loss.
"""

from __future__ import annotations

from teamster.goal_setting.adapters import sql_list
from teamster.goal_setting.adapters.roster_sql import ROSTER, roster_where
from teamster.goal_setting.config import ConfigError, Group
from teamster.goal_setting.records import StudentRecord

IREADY = "`teamster-332318.kipptaf_iready.int_iready__diagnostic_results`"
CROSSWALK = (
    "`teamster-332318.kipptaf_google_sheets.stg_google_sheets__iready__crosswalk`"
)
ASSESSMENT = "i-Ready BOY"

# Roster region (config.Group.regions) -> the district label carried by
# int_iready__diagnostic_results.region. Verified 2026-09-16 by an aggregate
# query (no student rows): the value set does NOT follow a "KIPP <Region>"
# pattern (Newark and Camden carry legal-entity names), so this is an
# explicit mapping, not a derived one.
IREADY_REGION = {
    "Newark": "TEAM Academy Charter School",
    "Camden": "KIPP Cooper Norcross Academy",
    "Paterson": "KIPP Paterson",
    "Miami": "KIPP Miami",
}


def _region_case(group: Group) -> str:
    whens = " ".join(
        f"when '{region}' then '{IREADY_REGION[region]}'" for region in group.regions
    )
    return f"case co.region {whens} end"


def sql(group: Group, academic_year: int) -> str:
    unknown = [r for r in group.regions if r not in IREADY_REGION]
    if unknown:
        raise ConfigError(
            f"iready_boy has no IREADY_REGION mapping for: {', '.join(unknown)}"
        )

    # Interpolates only pydantic-validated rules-file values (region/grade/
    # subject) and the IREADY_REGION constant above, never external user input.
    # trunk-ignore(bandit/B608): see comment above
    return f"""
    with
        xw as (
            select grade_level, `level`, scale_low, scale_high
            from {CROSSWALK}
            where destination_system = 'i-Ready'
              and test_name = '{group.subject}'
              and grade_level in ({sql_list(group.grades)})
        ),
        ir as (
            select
                student_id as student_number,
                student_grade_int as grade_level,
                region,
                overall_scale_score,
                -- TODO(#5317): switch to level_number_with_typical once typical growth is non-null in staging
                overall_scale_score + annual_typical_growth_measure as scale_plus_typical,
                overall_scale_score + annual_stretch_growth_measure as scale_plus_stretch
            from {IREADY}
            where academic_year_int = {academic_year}
              and subject = '{group.subject}'
              and test_round = 'BOY'
              and rn_subj_round = 1
              and student_grade_int in ({sql_list(group.grades)})
              and region in ({sql_list(IREADY_REGION[r] for r in group.regions)})
        ),
        ir_lvl as (
            select
                ir.student_number,
                ir.region,
                ir.scale_plus_typical,
                xt.`level` as level_typical,
                xs.`level` as level_stretch
            from ir
            left join xw as xt
                on ir.grade_level = xt.grade_level
                and ir.scale_plus_typical between xt.scale_low and xt.scale_high
            left join xw as xs
                on ir.grade_level = xs.grade_level
                and ir.scale_plus_stretch between xs.scale_low and xs.scale_high
        )
    select
        co.region,
        co.student_number,
        co.school,
        co.schoolid as school_id,
        co.grade_level,
        co.iready_subject as subject,
        ir.scale_plus_typical is not null as is_tested,
        ir.level_typical as projected_level,
        ir.scale_plus_typical as projected_score,
        ir.level_stretch as stretch_level
    from {ROSTER} as co
    left join ir_lvl as ir
        on co.student_number = ir.student_number
        and ir.region = {_region_case(group)}
    where {roster_where(group, academic_year)}
    """


def fetch(client, group: Group, academic_year: int) -> list[StudentRecord]:
    rows = client.query(sql(group, academic_year)).result()
    return [
        StudentRecord(
            region=r["region"],
            student_number=int(r["student_number"]),
            school=r["school"],
            school_id=int(r["school_id"]),
            grade_level=int(r["grade_level"]),
            subject=r["subject"],
            is_tested=bool(r["is_tested"]),
            projected_level=None
            if r["projected_level"] is None
            else int(r["projected_level"]),
            projected_score=(
                None if r["projected_score"] is None else float(r["projected_score"])
            ),
            stretch_level=None
            if r["stretch_level"] is None
            else int(r["stretch_level"]),
            assessment=ASSESSMENT,
        )
        for r in rows
    ]
