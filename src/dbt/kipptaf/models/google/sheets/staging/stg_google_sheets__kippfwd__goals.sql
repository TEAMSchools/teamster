with
    goals_long as (
        select
            academic_year,
            test_type,
            grade_level,
            cohort,
            score_type,
            expected_metric_goal,

            ends_with(expected_metric_column, '_over_time') as is_over_time_goal,

            regexp_replace(
                expected_metric_column, r'_over_time$', ''
            ) as expected_metric_type,

        from
            {{ source("google_sheets", "src_google_sheets__kippfwd__goals") }} unpivot (
                expected_metric_goal
                for
                expected_metric_column in (
                    pct_1_attempt,
                    pct_2_plus_attempts,
                    pct_hs_ready,
                    pct_college_ready,
                    pct_hs_ready_over_time,
                    pct_college_ready_over_time
                )
            )
    )

select
    academic_year,
    test_type,
    grade_level,
    cohort,
    score_type,
    expected_metric_type,
    expected_metric_goal,
    is_over_time_goal,

    case
        when expected_metric_type in ('pct_1_attempt', 'pct_2_plus_attempts')
        then 'Attempts'
        when expected_metric_type in ('pct_hs_ready', 'pct_college_ready')
        then 'Benchmark'
    end as expected_goal_type,

    case
        expected_metric_type
        when 'pct_hs_ready'
        then 'HS-Ready'
        when 'pct_college_ready'
        then 'College-Ready'
        when 'pct_1_attempt'
        then '1 Attempt'
        when 'pct_2_plus_attempts'
        then '2+ Attempts'
    end as expected_goal_subtype,

from goals_long
