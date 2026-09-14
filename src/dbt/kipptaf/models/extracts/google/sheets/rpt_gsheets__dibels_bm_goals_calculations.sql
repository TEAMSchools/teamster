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

            f.grade_goal_type,
            f.grade_goal,
            f.grade_range_goal,
            f_iep.grade_goal as grade_goal_iep,
            f_iep.grade_range_goal as grade_range_goal_iep,
            f_mll.grade_goal as grade_goal_mll,
            f_mll.grade_range_goal as grade_range_goal_mll,

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

            count(if(e.iep_status = 'Has IEP', a.student_number, null)) over (
                partition by a.academic_year, e.school, a.period, a.assessment_grade
            ) as n_admin_season_school_gl_all_iep,

            count(
                if(
                    a.aggregated_measure_standard_level = 'At/Above'
                    and e.iep_status = 'Has IEP',
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
            ) as n_admin_season_school_gl_at_above_iep,

            count(
                if(
                    a.aggregated_measure_standard_level = 'Below/Well Below'
                    and e.iep_status = 'Has IEP',
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
            ) as n_admin_season_school_gl_bl_wb_iep,

            count(if(e.iep_status = 'Has IEP', a.student_number, null)) over (
                partition by a.academic_year, e.region, a.period, a.assessment_grade
            ) as n_admin_season_region_gl_all_iep,

            count(
                if(
                    a.aggregated_measure_standard_level = 'At/Above'
                    and e.iep_status = 'Has IEP',
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
            ) as n_admin_season_region_gl_at_above_iep,

            count(
                if(
                    a.aggregated_measure_standard_level = 'Below/Well Below'
                    and e.iep_status = 'Has IEP',
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
            ) as n_admin_season_region_gl_bl_wb_iep,

            count(if(e.lep_status, a.student_number, null)) over (
                partition by a.academic_year, e.school, a.period, a.assessment_grade
            ) as n_admin_season_school_gl_all_mll,

            count(
                if(
                    a.aggregated_measure_standard_level = 'At/Above' and e.lep_status,
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
            ) as n_admin_season_school_gl_at_above_mll,

            count(
                if(
                    a.aggregated_measure_standard_level = 'Below/Well Below'
                    and e.lep_status,
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
            ) as n_admin_season_school_gl_bl_wb_mll,

            count(if(e.lep_status, a.student_number, null)) over (
                partition by a.academic_year, e.region, a.period, a.assessment_grade
            ) as n_admin_season_region_gl_all_mll,

            count(
                if(
                    a.aggregated_measure_standard_level = 'At/Above' and e.lep_status,
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
            ) as n_admin_season_region_gl_at_above_mll,

            count(
                if(
                    a.aggregated_measure_standard_level = 'Below/Well Below'
                    and e.lep_status,
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
            ) as n_admin_season_region_gl_bl_wb_mll,

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
            and f.population = 'All'
        left join
            {{ ref("stg_google_sheets__dibels_foundation_goals") }} as f_iep
            on a.academic_year = f_iep.academic_year
            and a.region = f_iep.region
            and a.assessment_grade_int = f_iep.grade_level
            and a.benchmark_goal_season = f_iep.period
            and a.foundation_measure_standard_level = f_iep.grade_goal_type
            and f_iep.population = 'IEP'
        left join
            {{ ref("stg_google_sheets__dibels_foundation_goals") }} as f_mll
            on a.academic_year = f_mll.academic_year
            and a.region = f_mll.region
            and a.assessment_grade_int = f_mll.grade_level
            and a.benchmark_goal_season = f_mll.period
            and a.foundation_measure_standard_level = f_mll.grade_goal_type
            and f_mll.population = 'MLL'
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
            grade_goal_type,
            school,

            grade_goal,
            grade_range_goal,
            n_admin_season_school_gl_all,
            n_admin_season_school_gl_at_above,
            n_admin_season_school_gl_bl_wb,
            n_admin_season_region_gl_all,
            n_admin_season_region_gl_at_above,
            n_admin_season_region_gl_bl_wb,
            grade_goal_iep,
            grade_range_goal_iep,
            n_admin_season_school_gl_all_iep,
            n_admin_season_school_gl_at_above_iep,
            n_admin_season_school_gl_bl_wb_iep,
            n_admin_season_region_gl_all_iep,
            n_admin_season_region_gl_at_above_iep,
            n_admin_season_region_gl_bl_wb_iep,
            grade_goal_mll,
            grade_range_goal_mll,
            n_admin_season_school_gl_all_mll,
            n_admin_season_school_gl_at_above_mll,
            n_admin_season_school_gl_bl_wb_mll,
            n_admin_season_region_gl_all_mll,
            n_admin_season_region_gl_at_above_mll,
            n_admin_season_region_gl_bl_wb_mll,

        from roster
        where rn = 1
    ),

    needed_count_calcs as (
        select
            *,

            -- T&L planning pads, K-8. BOY is double padded: this +5 and the
            -- 1.5x gap multiplier below. From SY26-27 MOY is single padded --
            -- it keeps the multiplier and drops this one.
            ceiling(n_admin_season_school_gl_all * grade_goal)
            + if(period = 'BOY', 5, 0) as n_admin_season_school_gl_at_above_expected,

            ceiling(n_admin_season_region_gl_all * grade_goal)
            + if(period = 'BOY', 5, 0) as n_admin_season_region_gl_at_above_expected,

            ceiling(n_admin_season_school_gl_all_iep * grade_goal_iep) + if(
                period = 'BOY', 5, 0
            ) as n_admin_season_school_gl_at_above_expected_iep,

            ceiling(n_admin_season_region_gl_all_iep * grade_goal_iep) + if(
                period = 'BOY', 5, 0
            ) as n_admin_season_region_gl_at_above_expected_iep,

            ceiling(n_admin_season_school_gl_all_mll * grade_goal_mll) + if(
                period = 'BOY', 5, 0
            ) as n_admin_season_school_gl_at_above_expected_mll,

            ceiling(n_admin_season_region_gl_all_mll * grade_goal_mll) + if(
                period = 'BOY', 5, 0
            ) as n_admin_season_region_gl_at_above_expected_mll,

        from group_rows
    )

select
    c.academic_year,
    c.region,
    c.assessment_grade,
    c.assessment_grade_int,
    c.period,
    c.benchmark_goal_season,
    c.school,
    c.grade_goal,
    c.grade_range_goal,
    c.n_admin_season_school_gl_all,
    c.n_admin_season_school_gl_at_above,
    c.n_admin_season_region_gl_all,
    c.n_admin_season_region_gl_at_above,
    c.n_admin_season_school_gl_at_above_expected,
    c.n_admin_season_region_gl_at_above_expected,
    c.grade_goal_iep,
    c.grade_range_goal_iep,
    c.n_admin_season_school_gl_all_iep,
    c.n_admin_season_school_gl_at_above_iep,
    c.n_admin_season_region_gl_all_iep,
    c.n_admin_season_region_gl_at_above_iep,
    c.n_admin_season_school_gl_at_above_expected_iep,
    c.n_admin_season_region_gl_at_above_expected_iep,
    c.grade_goal_mll,
    c.grade_range_goal_mll,
    c.n_admin_season_school_gl_all_mll,
    c.n_admin_season_school_gl_at_above_mll,
    c.n_admin_season_region_gl_all_mll,
    c.n_admin_season_region_gl_at_above_mll,
    c.n_admin_season_school_gl_at_above_expected_mll,
    c.n_admin_season_region_gl_at_above_expected_mll,

    b.n_admin_season_school_gl_bl_wb,
    b.n_admin_season_school_gl_bl_wb_iep,
    b.n_admin_season_school_gl_bl_wb_mll,
    b.n_admin_season_region_gl_bl_wb,
    b.n_admin_season_region_gl_bl_wb_iep,
    b.n_admin_season_region_gl_bl_wb_mll,

    (c.n_admin_season_school_gl_at_above_expected - c.n_admin_season_school_gl_at_above)
    * 1.5 as n_admin_season_school_gl_at_above_gap,

    (c.n_admin_season_region_gl_at_above_expected - c.n_admin_season_region_gl_at_above)
    * 1.5 as n_admin_season_region_gl_at_above_gap,

    (
        c.n_admin_season_school_gl_at_above_expected_iep
        - c.n_admin_season_school_gl_at_above_iep
    )
    * 1.5 as n_admin_season_school_gl_at_above_gap_iep,

    (
        c.n_admin_season_region_gl_at_above_expected_iep
        - c.n_admin_season_region_gl_at_above_iep
    )
    * 1.5 as n_admin_season_region_gl_at_above_gap_iep,

    (
        c.n_admin_season_school_gl_at_above_expected_mll
        - c.n_admin_season_school_gl_at_above_mll
    )
    * 1.5 as n_admin_season_school_gl_at_above_gap_mll,

    (
        c.n_admin_season_region_gl_at_above_expected_mll
        - c.n_admin_season_region_gl_at_above_mll
    )
    * 1.5 as n_admin_season_region_gl_at_above_gap_mll,

from needed_count_calcs as c
left join
    needed_count_calcs as b
    on c.academic_year = b.academic_year
    and c.region = b.region
    and c.assessment_grade = b.assessment_grade
    and c.period = b.period
    and c.benchmark_goal_season = b.benchmark_goal_season
    and c.school = b.school
    and b.grade_goal_type = 'Well Below'
where c.grade_goal_type = 'At/Above'
