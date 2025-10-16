with
    calcs as (
        select
            region,
            grade_level,
            cohort,
            expected_test_type,
            expected_scope,
            expected_subject_area,
            min_score,
            pct_goal,

            if(
                goal_type = 'Attempts',
                concat(expected_scope, ' ', goal_category),
                goal_subtype
            ) as expected_metric_name,

            if(
                goal_type = 'Attempts', goal_category, goal_subtype
            ) as expected_goal_subtype,

        from {{ source("google_sheets", "src_google_sheets__kippfwd_goals") }}
    )

select
    *,

    case
        expected_metric_name
        when 'ACT 1 Attempt'
        then 'act_1_attempt'
        when 'ACT 2+ Attempts'
        then 'act_2_plus_attempts'
        when 'SAT 1 Attempt'
        then 'sat_1_attempt'
        when 'SAT 2+ Attempts'
        then 'sat_2_plus_attempts'
        when 'PSAT 8/9 1 Attempt'
        then 'psat89_1_attempt'
        when 'PSAT 8/9 2+ Attempts'
        then 'psat89_2_plus_attempts'
        when 'PSAT10 1 Attempt'
        then 'psat10_1_attempt'
        when 'PSAT10 2+ Attempts'
        then 'psat10_2_plus_attempts'
        when 'PSAT NMSQT 1 Attempt'
        then 'psatnmsqt_1_attempt'
        when 'PSAT NMSQT 2+ Attempts'
        then 'psatnmsqt_2_plus_attempts'
        else
            regexp_replace(
                lower(
                    concat(
                        expected_scope,
                        '_',
                        expected_subject_area,
                        '_',
                        expected_metric_name
                    )
                ),
                '-',
                '_'
            )
    end as expected_metric_label,

from calcs
