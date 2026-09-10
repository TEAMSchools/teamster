with
    aimline_scores as (
        select
            a.academic_year,
            a.region,
            a.assessment_grade,
            a.assessment_grade_int,
            a.measure_standard,
            a.measure_name_code,
            a.measure_standard_score,
            a.round_number,
            a.student_number,
            a.aimline_status,
            a.goal,

            e.pm_goal_criteria,
            e.start_date,
            e.end_date,

            p.completed_test_round,
            p.completed_test_round_int,

            a.period as admin_season,

            -- on an Aimline row this column carries the composite level, not
            -- 'Yes' -- it is the cohort key the by-levels gate is split on
            a.overall_probe_eligible as measure_standard_level,

            e.benchmark_goal,

            -- padded to match the internal method, whose frozen sheet carries
            -- the pad already. Both methods' met_admin_benchmark_goal therefore
            -- answer the same question.
            e.benchmark_goal + 3 as benchmark_goal_padded,

            -- null is a real third value: Amplify publishes no verdict on about
            -- a sixth of probes, and that is not a miss
            case
                when a.aimline_status = 'At or Above'
                then 1
                when a.aimline_status = 'Below'
                then 0
            end as met_aimline_goal,

        from {{ ref("int_amplify__all_assessments") }} as a
        inner join
            {{ ref("int_google_sheets__dibels__expected_assessments_by_levels") }} as e
            on a.academic_year = e.academic_year
            and a.region = e.region
            and a.assessment_grade_int = e.grade
            and a.period = e.admin_season
            and a.round_number = e.round_number
            and a.measure_standard = e.expected_measure_standard
            and a.overall_probe_eligible = e.measure_standard_level
            and e.assessment_include is null
            and e.pm_goal_include is null
        inner join
            {{ ref("int_students__dibels_participation_roster") }} as p
            on a.academic_year = p.academic_year
            and a.region = p.region
            and a.student_number = p.student_number
            and a.assessment_grade_int = p.grade_level
            and a.period = p.admin_season
            and a.round_number = p.round_number
            and a.model_type = p.model_type
        where a.assessment_type = 'PM' and a.model_type = 'Aimline'
    ),

    measure_flags as (
        select
            *,

            case
                when benchmark_goal_padded is null
                then null
                when measure_standard_score >= benchmark_goal_padded
                then 1
                else 0
            end as met_admin_benchmark_goal,

            countif(met_aimline_goal is null) over (
                partition by
                    academic_year,
                    admin_season,
                    round_number,
                    measure_name_code,
                    student_number
            ) as n_code_unpublished,

            min(met_aimline_goal) over (
                partition by
                    academic_year,
                    admin_season,
                    round_number,
                    measure_name_code,
                    student_number
            ) as code_min_met,

        from aimline_scores
    ),

    code_goal as (
        select
            *,

            -- a missed standard settles the code however many are unpublished;
            -- only an otherwise-clean code is left indeterminate
            case
                when code_min_met = 0
                then 0
                when n_code_unpublished > 0
                then null
                else 1
            end as met_measure_name_code_goal,

        from measure_flags
    ),

    round_windows as (
        select
            *,

            countif(met_measure_name_code_goal is null) over (
                partition by academic_year, admin_season, round_number, student_number
            ) as n_round_unpublished,

            min(met_measure_name_code_goal) over (
                partition by academic_year, admin_season, round_number, student_number
            ) as round_min_met,

            max(met_measure_name_code_goal) over (
                partition by academic_year, admin_season, round_number, student_number
            ) as round_max_met,

        from code_goal
    ),

    round_criteria as (
        select
            *,

            -- the same asymmetry the completion gate rests on, applied to an
            -- unpublished verdict instead of an unsat probe: under AND a single
            -- miss settles the round, under the null (OR) criteria a single pass
            -- does, and only where neither has happened is the round unknown
            case
                when pm_goal_criteria = 'AND' and round_min_met = 0
                then 0
                when pm_goal_criteria = 'AND' and n_round_unpublished > 0
                then null
                when pm_goal_criteria = 'AND'
                then 1
                when round_max_met = 1
                then 1
                when n_round_unpublished > 0
                then null
                else 0
            end as met_pm_round_criteria,

        from round_windows
    ),

    round_overall as (
        select
            *,

            case
                when met_pm_round_criteria is null
                then 0
                when met_pm_round_criteria = 0
                then 0
                when pm_goal_criteria = 'AND' and not completed_test_round
                then 0
                else 1
            end as met_pm_round_overall_criteria,

            -- consecutive among the rounds the student actually sat: a skipped
            -- round is passed over rather than breaking the streak, because a
            -- probe nobody administered is not evidence of improvement
            lag(met_aimline_goal) over (
                partition by
                    academic_year, student_number, admin_season, measure_standard
                order by round_number
            ) as previous_met_aimline_goal,

        from round_criteria
    )

select
    academic_year,
    region,
    admin_season,
    assessment_grade,
    assessment_grade_int,
    measure_standard,
    measure_standard_level,
    round_number,
    benchmark_goal,
    benchmark_goal_padded,
    goal,
    pm_goal_criteria,
    student_number,
    measure_name_code,
    measure_standard_score,
    `start_date`,
    end_date,
    completed_test_round,
    completed_test_round_int,
    aimline_status,
    met_aimline_goal,
    met_admin_benchmark_goal,
    met_measure_name_code_goal,
    met_pm_round_criteria,
    met_pm_round_overall_criteria,
    previous_met_aimline_goal,

    if(
        met_aimline_goal = 0 and previous_met_aimline_goal = 0, 1, 0
    ) as missed_aimline_consecutive,

    case
        when met_pm_round_overall_criteria = 1
        then 'Met'
        when met_pm_round_criteria = 0 and pm_goal_criteria = 'AND'
        then 'Not Met'
        when met_pm_round_criteria = 0 and completed_test_round
        then 'Not Met'
        when not completed_test_round
        then 'Round Incomplete'
        when met_pm_round_criteria is null
        then 'No Aimline Status'
        else 'Not Met'
    end as pm_round_status,

    -- T&L's reporting categories. At grade level outranks the aimline verdict
    -- deliberately: a student who has arrived is On Track whatever their own
    -- trajectory says.
    case
        when met_admin_benchmark_goal = 1
        then 'On Track & Meeting Aimline'
        when met_aimline_goal = 1
        then 'Meeting Aimline, Off-Track'
        when met_aimline_goal = 0
        then 'Below Aimline'
        else 'No Aimline Status'
    end as aimline_category,

from round_overall
