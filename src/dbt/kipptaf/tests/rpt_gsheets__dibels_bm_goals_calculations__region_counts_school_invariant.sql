with
    region_values as (
        select
            academic_year,
            region,
            assessment_grade,
            `period`,

            count(distinct n_admin_season_region_gl_bl_wb) as n_distinct_bl_wb,
            count(distinct n_admin_season_region_gl_bl_wb_iep) as n_distinct_iep,
            count(distinct n_admin_season_region_gl_bl_wb_mll) as n_distinct_mll,
            countif(n_admin_season_region_gl_bl_wb is null) as n_null_bl_wb,
            countif(n_admin_season_region_gl_bl_wb_iep is null) as n_null_iep,
            countif(n_admin_season_region_gl_bl_wb_mll is null) as n_null_mll,
        from {{ ref("rpt_gsheets__dibels_bm_goals_calculations") }}
        group by academic_year, region, assessment_grade, `period`
    )

select
    academic_year,
    region,
    assessment_grade,
    `period`,
    n_distinct_bl_wb,
    n_distinct_iep,
    n_distinct_mll,
    n_null_bl_wb,
    n_null_iep,
    n_null_mll,
from region_values
-- count(distinct) ignores nulls, so the two halves catch different shapes: a
-- count other than 1 is disagreement between schools or an all-null group, and
-- a non-zero null count is the partial case that would otherwise read as one
-- agreed value.
where
    n_distinct_bl_wb != 1
    or n_distinct_iep != 1
    or n_distinct_mll != 1
    or n_null_bl_wb > 0
    or n_null_iep > 0
    or n_null_mll > 0
