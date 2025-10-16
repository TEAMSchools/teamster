with
    completion_goals_unpivot as (
        select
            expected_test_type,

            `value`,

            concat(
                expected_metric_label, '_', value_type
            ) as expected_metric_label_type,

        from
            {{ ref("stg_google_sheets__kippfwd_goals") }}
            unpivot (`value` for value_type in (min_score, pct_goal))
        where
            expected_test_type = 'Official'
            and expected_goal_type = 'Attempts'
            and expected_subject_area in ('Composite', 'Combined')
    ),

    completion_goals as (
        select
            expected_test_type,

            psatnmsqt_1_attempt_min_score,
            psat10_1_attempt_min_score,
            psat89_1_attempt_min_score,
            act_1_attempt_min_score,
            sat_1_attempt_min_score,
            psat89_2_plus_attempts_min_score,
            sat_2_plus_attempts_min_score,
            psatnmsqt_2_plus_attempts_min_score,
            psat10_2_plus_attempts_min_score,
            act_2_plus_attempts_min_score,

            sat_1_attempt_pct_goal,
            sat_2_plus_attempts_pct_goal,

        from
            completion_goals_unpivot pivot (
                avg(`value`) for expected_metric_label_type in (
                    'psatnmsqt_1_attempt_min_score',
                    'psat89_1_attempt_min_score',
                    'act_1_attempt_min_score',
                    'sat_1_attempt_min_score',
                    'sat_1_attempt_pct_goal',
                    'psat10_1_attempt_min_score',
                    'psat89_2_plus_attempts_min_score',
                    'sat_2_plus_attempts_min_score',
                    'sat_2_plus_attempts_pct_goal',
                    'psatnmsqt_2_plus_attempts_min_score',
                    'psat10_2_plus_attempts_min_score',
                    'act_2_plus_attempts_min_score'
                )
            )
    ),

    base_rows as (
        select student_number, salesforce_id, grade_level, test_type, scope, score_type,

        from {{ ref("int_students__college_assessment_roster") }}
        where
            score_type in (
                'act_composite',
                'sat_total_score',
                'psat89_total',
                'psatnmsqt_total',
                'psat10_total'
            )
    ),

    yearly_tests as (
        select
            student_number,
            salesforce_id,
            grade_level,

            psat89_count,
            psat10_count,
            psatnmsqt_count,
            sat_count,
            act_count,

        from
            base_rows pivot (
                count(score_type) for scope in (
                    'PSAT 8/9' as psat89_count,
                    'PSAT10' as psat10_count,
                    'PSAT NMSQT' as psatnmsqt_count,
                    'SAT' as sat_count,
                    'ACT' as act_count
                )
            )
    ),

    yearly_test_counts as (
        select
            student_number,
            salesforce_id,
            grade_level,

            sum(psat89_count) as psat89_count,
            sum(psat10_count) as psat10_count,
            sum(psatnmsqt_count) as psatnmsqt_count,
            sum(sat_count) as sat_count,
            sum(act_count) as act_count,

        from yearly_tests
        group by student_number, salesforce_id, grade_level
    )

select
    y.*,

    c.act_1_attempt_min_score,
    c.act_2_plus_attempts_min_score,
    c.sat_1_attempt_min_score,
    c.sat_1_attempt_pct_goal,
    c.sat_2_plus_attempts_min_score,
    c.sat_2_plus_attempts_pct_goal,
    c.psat89_1_attempt_min_score,
    c.psat89_2_plus_attempts_min_score,
    c.psat10_1_attempt_min_score,
    c.psat10_2_plus_attempts_min_score,
    c.psatnmsqt_1_attempt_min_score,
    c.psatnmsqt_2_plus_attempts_min_score,

    sum(y.psat89_count) over (
        partition by y.student_number order by y.grade_level
    ) as psat89_count_ytd,

    sum(y.psat10_count) over (
        partition by y.student_number order by y.grade_level
    ) as psat10_count_ytd,

    sum(y.psatnmsqt_count) over (
        partition by y.student_number order by y.grade_level
    ) as psatnmsqt_count_ytd,

    sum(y.sat_count) over (
        partition by y.student_number order by y.grade_level
    ) as sat_count_ytd,

    sum(y.act_count) over (
        partition by y.student_number order by y.grade_level
    ) as act_count_ytd,

from yearly_test_counts as y
cross join completion_goals as c
