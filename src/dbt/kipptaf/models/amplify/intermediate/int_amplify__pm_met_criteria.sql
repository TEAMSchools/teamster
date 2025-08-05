with
    met_standard_goal as (
        select
            g.academic_year,
            g.region,
            g.admin_season,
            g.assessment_grade,
            g.assessment_grade_int,
            g.measure_standard,
            g.round_number,
            g.benchmark_goal,
            g.round_growth_words_goal,
            g.cumulative_growth_words,
            g.pm_goal_criteria,

            a.student_number,
            a.measure_name_code,
            a.measure_standard_score,
            a.start_date,
            a.end_date,

            p.completed_test_round,

            if(
                a.measure_standard_score >= g.cumulative_growth_words, 1, 0
            ) as met_measure_standard_goal,

            if(
                a.measure_standard_score >= g.benchmark_goal, 1, 0
            ) as met_admin_benchmark_goal,

        from {{ ref("stg_google_sheets__dibels_pm_goals") }} as g
        inner join
            {{ ref("int_amplify__all_assessments") }} as a
            on g.academic_year = a.academic_year
            and g.region = a.region
            and g.assessment_grade_int = a.assessment_grade_int
            and g.admin_season = a.period
            and g.round_number = a.round_number
            and g.measure_standard = a.measure_standard
            and a.assessment_type = 'PM'
            and a.overall_probe_eligible = 'Yes'
        inner join
            {{ ref("int_students__dibels_participation_roster") }} as p
            on a.academic_year = p.academic_year
            and a.region = p.region
            and a.student_number = p.student_number
            and a.assessment_grade_int = p.grade_level
            and a.period = p.admin_season
            and a.round_number = p.round_number
            and p.enrollment_dates_account
        where g.pm_goal_include is null
    ),

    met_measure_code_goal as (
        select
            *,

            if(
                avg(met_measure_standard_goal) over (
                    partition by
                        academic_year,
                        admin_season,
                        round_number,
                        measure_name_code,
                        student_number
                )
                = 1,
                1,
                0
            ) as met_measure_name_code_goal,

        from met_standard_goal
    ),

    met_round_criteria as (
        select
            *,

            case
                pm_goal_criteria
                when 'AND'
                then
                    min(met_measure_name_code_goal) over (
                        partition by
                            academic_year, admin_season, round_number, student_number
                    )
                else
                    max(met_measure_name_code_goal) over (
                        partition by
                            academic_year, admin_season, round_number, student_number
                    )
            end as met_pm_round_criteria,

        from met_measure_code_goal
    )

select
    *,

    case
        when
            pm_goal_criteria = 'AND'
            and met_pm_round_criteria = 1
            and completed_test_round
        then 1
        when pm_goal_criteria is null and met_pm_round_criteria = 1
        then 1
        else 0
    end as met_pm_round_overall_criteria,

from met_round_criteria
