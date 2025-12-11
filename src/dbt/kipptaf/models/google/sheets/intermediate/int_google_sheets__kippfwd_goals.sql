with
    goals_unpivot as (
        select
            expected_test_type,

            `value`,

            concat(
                expected_metric_label, '_', value_type
            ) as expected_metric_label_type,
        from
            {{ ref("stg_google_sheets__kippfwd__goals") }}
            unpivot (`value` for value_type in (min_score, pct_goal))
        where
            expected_test_type = 'Official'
            and expected_goal_type = 'Attempts'
            and expected_subject_area in ('Composite', 'Combined')
    )

select
    expected_test_type,

    act_1_attempt_min_score,
    act_2_plus_attempts_min_score,
    psat10_1_attempt_min_score,
    psat10_2_plus_attempts_min_score,
    psat89_1_attempt_min_score,
    psat89_2_plus_attempts_min_score,
    psatnmsqt_1_attempt_min_score,
    psatnmsqt_2_plus_attempts_min_score,
    sat_1_attempt_min_score,
    sat_1_attempt_pct_goal,
    sat_2_plus_attempts_min_score,
    sat_2_plus_attempts_pct_goal,
from
    goals_unpivot pivot (
        avg(`value`) for expected_metric_label_type in (
            'act_1_attempt_min_score',
            'act_2_plus_attempts_min_score',
            'psat10_1_attempt_min_score',
            'psat10_2_plus_attempts_min_score',
            'psat89_1_attempt_min_score',
            'psat89_2_plus_attempts_min_score',
            'psatnmsqt_1_attempt_min_score',
            'psatnmsqt_2_plus_attempts_min_score',
            'sat_1_attempt_min_score',
            'sat_1_attempt_pct_goal',
            'sat_2_plus_attempts_min_score',
            'sat_2_plus_attempts_pct_goal'
        )
    )
