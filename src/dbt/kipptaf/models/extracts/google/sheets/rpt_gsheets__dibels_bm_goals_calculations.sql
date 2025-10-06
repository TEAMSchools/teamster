with
    roster as (
        select
            a.academic_year,
            a.region,
            a.assessment_grade,
            a.assessment_grade_int,
            a.period,
            a.benchmark_goal_season,

            e.school,

            f.grade_goal,
            f.grade_range_goal,

            -- school/gl calcs
            count(a.student_number) over (
                partition by a.academic_year, e.school, a.period, a.assessment_grade
            ) as n_admin_season_school_gl_all,

            count(
                if(
                    a.aggregated_measure_standard_level = 'At/Above',
                    a.student_number,
                    null
                )
            ) over (
                partition by
                    a.academic_year,
                    e.school,
                    a.period,
                    a.assessment_grade,
                    a.aggregated_measure_standard_level
            ) as n_admin_season_school_gl_at_above,

            count(
                if(
                    a.aggregated_measure_standard_level = 'Below/Well Below',
                    a.student_number,
                    null
                )
            ) over (
                partition by
                    a.academic_year,
                    e.school,
                    a.period,
                    a.assessment_grade,
                    a.aggregated_measure_standard_level
            ) as n_admin_season_school_gl_bl_wb,

            -- region/gl calcs
            count(a.student_number) over (
                partition by a.academic_year, e.region, a.period, a.assessment_grade
            ) as n_admin_season_region_gl_all,

            count(
                if(
                    a.aggregated_measure_standard_level = 'At/Above',
                    a.student_number,
                    null
                )
            ) over (
                partition by
                    a.academic_year,
                    e.region,
                    a.period,
                    a.assessment_grade,
                    a.aggregated_measure_standard_level
            ) as n_admin_season_region_gl_at_above,

            count(
                if(
                    a.aggregated_measure_standard_level = 'Below/Well Below',
                    a.student_number,
                    null
                )
            ) over (
                partition by
                    a.academic_year,
                    e.region,
                    a.period,
                    a.assessment_grade,
                    a.aggregated_measure_standard_level
            ) as n_admin_season_region_gl_bl_wb,

            -- distinct
            row_number() over (
                partition by
                    a.academic_year,
                    a.region,
                    a.assessment_grade,
                    a.period,
                    a.benchmark_goal_season,
                    a.aggregated_measure_standard_level,
                    e.school
            ) as rn,

        from {{ ref("int_amplify__all_assessments") }} as a
        inner join
            {{ ref("int_extracts__student_enrollments") }} as e
            on a.academic_year = e.academic_year
            and a.region = e.region
            and a.student_number = e.student_number
            and a.assessment_grade_int = e.grade_level
            and a.client_date between e.entrydate and e.exitdate
        left join
            {{ ref("stg_google_sheets__dibels_foundation_goals") }} as f
            on a.academic_year = f.academic_year
            and a.region = f.region
            and a.assessment_grade_int = f.grade_level
            and a.benchmark_goal_season = f.period
            and a.foundation_measure_standard_level = f.grade_goal_type
        where
            a.academic_year = {{ var("current_academic_year") }}
            and a.assessment_type = 'Benchmark'
            and a.measure_standard = 'Composite'
            and a.period != 'EOY'
    ),

    group_rows as (
        select
            academic_year,
            region,
            assessment_grade,
            assessment_grade_int,
            period,
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

        from roster
        where rn = 1
        group by
            academic_year,
            region,
            assessment_grade,
            assessment_grade_int,
            period,
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
