with
    expected_rounds as (
        select
            *,

            lag(round_number) over (
                partition by
                    academic_year,
                    region,
                    grade,
                    admin_season,
                    measure_standard_level,
                    expected_measure_standard
                order by round_number
            ) as previous_expected_round,

        from {{ ref("int_google_sheets__dibels__expected_assessments_by_levels") }}
        -- filtered before the window deliberately: a cancelled or scaffold round
        -- is not one anyone was expected to sit, so it must not break a streak
        where assessment_include is null and pm_goal_include is null
    ),

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
            a.aimline_season_student_goal,
            a.aimline_value_by_date,
            a.met_measure_standard_goal,
            a.period as admin_season,
            a.overall_probe_eligible as measure_standard_level,

            e.pm_goal_criteria,
            e.start_date,
            e.end_date,
            e.benchmark_goal,
            e.previous_expected_round,

            p.completed_test_round,
            p.completed_test_round_int,

        from {{ ref("int_amplify__all_assessments") }} as a
        inner join
            expected_rounds as e
            on a.academic_year = e.academic_year
            and a.region = e.region
            and a.assessment_grade_int = e.grade
            and a.period = e.admin_season
            and a.round_number = e.round_number
            and a.measure_standard = e.expected_measure_standard
            and a.overall_probe_eligible = e.measure_standard_level
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

    with_previous as (
        select
            c.*,

            p.met_measure_standard_goal as previous_expected_met_aimline_goal,

            lag(c.met_measure_standard_goal) over (
                partition by
                    c.academic_year,
                    c.student_number,
                    c.admin_season,
                    c.measure_standard
                order by c.round_number
            ) as previous_sat_met_aimline_goal,

        from aimline_scores as c
        left join
            aimline_scores as p
            on c.academic_year = p.academic_year
            and c.student_number = p.student_number
            and c.admin_season = p.admin_season
            and c.measure_standard = p.measure_standard
            and c.previous_expected_round = p.round_number
    ),

    previous_verdict as (
        select
            *,

            coalesce(
                previous_expected_met_aimline_goal, previous_sat_met_aimline_goal
            ) as previous_met_aimline_goal,

        from with_previous
    ),

    measure_flags as (
        select
            *,

            case
                when benchmark_goal is null
                then null
                when measure_standard_score >= benchmark_goal
                then 1
                else 0
            end as met_admin_benchmark_goal,

            countif(met_measure_standard_goal is null) over (
                partition by
                    academic_year,
                    admin_season,
                    round_number,
                    measure_name_code,
                    student_number
            ) as n_code_unpublished,

            min(met_measure_standard_goal) over (
                partition by
                    academic_year,
                    admin_season,
                    round_number,
                    measure_name_code,
                    student_number
            ) as code_min_met,

        from previous_verdict
    ),

    code_goal as (
        select
            *,

            case
                when code_min_met = 0
                then 0
                when n_code_unpublished > 0
                then null
                else 1
            end as met_measure_name_code_goal,

            countif(met_admin_benchmark_goal is null) over (
                partition by
                    academic_year,
                    admin_season,
                    round_number,
                    measure_name_code,
                    student_number
            ) as n_code_bm_unpublished,

            min(met_admin_benchmark_goal) over (
                partition by
                    academic_year,
                    admin_season,
                    round_number,
                    measure_name_code,
                    student_number
            ) as code_bm_min_met,

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

            countif(met_admin_benchmark_goal is null) over (
                partition by academic_year, admin_season, round_number, student_number
            ) as n_round_bm_unpublished,

            min(met_admin_benchmark_goal) over (
                partition by academic_year, admin_season, round_number, student_number
            ) as round_bm_min_met,

        from code_goal
    ),

    round_criteria as (
        select
            *,

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

        from round_criteria
    ),

    measure_category as (
        select
            *,

            case
                when not completed_test_round
                then 'Round Incomplete'
                when
                    met_admin_benchmark_goal = 1
                    and met_measure_standard_goal is not null
                then 'Meeting Aimline, On-Track'
                when met_measure_standard_goal = 1
                then 'Meeting Aimline, Off-Track'
                when met_measure_standard_goal = 0
                then 'Below Aimline'
                when met_admin_benchmark_goal = 1
                then 'No Aimline Data, On-Track'
                else 'No Aimline Data, Off-Track'
            end as aimline_category,

            case
                when met_measure_standard_goal is null
                then 'No Aimline Data'
                when met_measure_standard_goal = 0
                then 'Below Aimline'
                when met_admin_benchmark_goal = 1
                then 'On Track to Benchmark'
                else 'On Aimline, Below Benchmark'
            end as trajectory_row,

        from round_overall
    ),

    round_category as (
        select
            *,

            countif(aimline_category = 'Round Incomplete') over (
                partition by academic_year, admin_season, round_number, student_number
            ) as n_round_incomplete,

            countif(aimline_category = 'Below Aimline') over (
                partition by academic_year, admin_season, round_number, student_number
            ) as n_round_below,

            countif(aimline_category like 'No Aimline Data%') over (
                partition by academic_year, admin_season, round_number, student_number
            ) as n_round_no_aimline,

            countif(aimline_category = 'Meeting Aimline, Off-Track') over (
                partition by academic_year, admin_season, round_number, student_number
            ) as n_round_off_track,

            countif(aimline_category = 'Round Incomplete') over (
                partition by
                    academic_year,
                    admin_season,
                    round_number,
                    measure_name_code,
                    student_number
            ) as n_code_incomplete,

            countif(aimline_category = 'Below Aimline') over (
                partition by
                    academic_year,
                    admin_season,
                    round_number,
                    measure_name_code,
                    student_number
            ) as n_code_below,

            countif(aimline_category like 'No Aimline Data%') over (
                partition by
                    academic_year,
                    admin_season,
                    round_number,
                    measure_name_code,
                    student_number
            ) as n_code_no_aimline,

            countif(aimline_category = 'Meeting Aimline, Off-Track') over (
                partition by
                    academic_year,
                    admin_season,
                    round_number,
                    measure_name_code,
                    student_number
            ) as n_code_off_track,

            countif(trajectory_row = 'Below Aimline') over (
                partition by
                    academic_year,
                    admin_season,
                    round_number,
                    measure_name_code,
                    student_number
            ) as n_code_traj_below,

            countif(trajectory_row = 'No Aimline Data') over (
                partition by
                    academic_year,
                    admin_season,
                    round_number,
                    measure_name_code,
                    student_number
            ) as n_code_traj_no_data,

            countif(trajectory_row = 'On Aimline, Below Benchmark') over (
                partition by
                    academic_year,
                    admin_season,
                    round_number,
                    measure_name_code,
                    student_number
            ) as n_code_traj_off,

            countif(trajectory_row = 'Below Aimline') over (
                partition by academic_year, admin_season, round_number, student_number
            ) as n_round_traj_below,

            countif(trajectory_row = 'No Aimline Data') over (
                partition by academic_year, admin_season, round_number, student_number
            ) as n_round_traj_no_data,

            countif(trajectory_row = 'On Aimline, Below Benchmark') over (
                partition by academic_year, admin_season, round_number, student_number
            ) as n_round_traj_off,

        from measure_category
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
    aimline_season_student_goal,
    aimline_value_by_date,
    pm_goal_criteria,
    student_number,
    measure_name_code,
    measure_standard_score,
    `start_date`,
    end_date,
    completed_test_round,
    completed_test_round_int,
    aimline_status,
    met_measure_standard_goal,
    met_admin_benchmark_goal,
    met_measure_name_code_goal,
    met_pm_round_criteria,
    met_pm_round_overall_criteria,
    previous_expected_round,
    previous_met_aimline_goal,
    aimline_category,

    if(
        met_measure_standard_goal = 0 and previous_met_aimline_goal = 0, 1, 0
    ) as missed_aimline_consecutive,

    case
        when met_admin_benchmark_goal = 1
        then 'Met Benchmark'
        when met_admin_benchmark_goal = 0
        then 'Did Not Meet Benchmark'
    end as admin_benchmark_goal_status,

    case
        when met_measure_standard_goal = 1
        then 'Meeting Aimline'
        when met_measure_standard_goal = 0
        then 'Below Aimline'
        else 'No Aimline Data'
    end as measure_standard_goal_status,

    case
        when met_measure_name_code_goal = 1
        then 'Meeting Aimline'
        when met_measure_name_code_goal = 0
        then 'Below Aimline'
        else 'No Aimline Data'
    end as measure_name_code_goal_status,

    case
        when met_pm_round_overall_criteria = 1
        then 'Meeting Aimline'
        when met_pm_round_criteria = 0 and pm_goal_criteria = 'AND'
        then 'Below Aimline'
        when met_pm_round_criteria = 0 and completed_test_round
        then 'Below Aimline'
        when not completed_test_round
        then 'Round Incomplete'
        when met_pm_round_criteria is null
        then 'No Aimline Data'
        else 'Below Aimline'
    end as pm_round_status,

    case
        when code_bm_min_met = 0
        then 'Did Not Meet Benchmark'
        when n_code_bm_unpublished > 0
        then null
        else 'Met Benchmark'
    end as measure_name_code_benchmark_status,

    case
        when round_bm_min_met = 0
        then 'Did Not Meet Benchmark'
        when n_round_bm_unpublished > 0
        then null
        else 'Met Benchmark'
    end as round_benchmark_status,

    case
        when n_code_incomplete > 0
        then 'Round Incomplete'
        when n_code_below > 0
        then 'Below Aimline'
        when n_code_no_aimline > 0
        then 'No Aimline Data'
        when n_code_off_track > 0
        then 'Meeting Aimline, Off-Track'
        else 'Meeting Aimline, On-Track'
    end as measure_name_code_aimline_benchmark_status,

    case
        when n_code_traj_below > 0
        then 'Below Aimline'
        when n_code_traj_no_data > 0
        then 'No Aimline Data'
        when n_code_traj_off > 0
        then 'On Aimline, Below Benchmark'
        else 'On Track to Benchmark'
    end as measure_name_code_trajectory_status,

    case
        when n_round_traj_below > 0
        then 'Below Aimline'
        when n_round_traj_no_data > 0
        then 'No Aimline Data'
        when n_round_traj_off > 0
        then 'On Aimline, Below Benchmark'
        else 'On Track to Benchmark'
    end as round_trajectory_status,

    case
        when n_round_incomplete > 0
        then 'Round Incomplete'
        when n_round_below > 0
        then 'Below Aimline'
        when n_round_no_aimline > 0
        then 'No Aimline Data'
        when n_round_off_track > 0
        then 'Meeting Aimline, Off-Track'
        else 'Meeting Aimline, On-Track'
    end as aimline_round_category,

from round_category
