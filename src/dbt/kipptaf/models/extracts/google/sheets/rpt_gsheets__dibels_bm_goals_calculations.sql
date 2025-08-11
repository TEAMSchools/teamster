with
    group_rows as (
        select
            academic_year,
            region,
            assessment_grade,
            assessment_grade_int,
            `period`,
            benchmark_goal_season,
            school,

            max(grade_goal) as grade_goal,

            max(grade_range_goal) as grade_range_goal,

            avg(n_admin_season_school_gl_all) as n_admin_season_school_gl_all,

            sum(n_admin_season_school_gl_at_above) as n_admin_season_school_gl_at_above,

            sum(n_admin_season_school_gl_bl_wb) as n_admin_season_school_gl_bl_wb,

            avg(n_admin_season_region_gl_all) as n_admin_season_region_gl_all,

            sum(n_admin_season_region_gl_at_above) as n_admin_season_region_gl_at_above,

            sum(n_admin_season_region_gl_bl_wb) as n_admin_season_region_gl_bl_wb,

        from {{ ref("int_amplify__all_assessments") }}
        where
            assessment_type = 'Benchmark'
            and measure_standard = 'Composite'
            and rn = 1
            and `period` != 'EOY'
            and academic_year >= 2024
        group by
            academic_year,
            region,
            assessment_grade,
            assessment_grade_int,
            `period`,
            benchmark_goal_season,
            school
    ),

    needed_count_calcs as (
        select
            *,

            ceiling(n_admin_season_school_gl_all * grade_goal)
            + 5 as n_admin_season_school_gl_at_above_expected,

            ceiling(n_admin_season_region_gl_all * grade_goal)
            + 5 as n_admin_season_region_gl_at_above_expected,

        from group_rows
    )

select
    *,

    (n_admin_season_school_gl_at_above_expected - n_admin_season_school_gl_at_above)
    * 1.5 as n_admin_season_school_gl_at_above_gap,

    (n_admin_season_region_gl_at_above_expected - n_admin_season_region_gl_at_above)
    * 1.5 as n_admin_season_region_gl_at_above_gap,

from needed_count_calcs
