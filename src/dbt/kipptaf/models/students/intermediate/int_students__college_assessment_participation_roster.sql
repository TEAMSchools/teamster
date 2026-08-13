with
    attempts as (
        select
            s.academic_year,
            s.student_number,
            s.test_type,
            s.score_type,
            s.attempt_lifetime,
            s.yearly_attempts_totals,

            e.salesforce_id,
            e.grade_level,

        from {{ ref("int_assessments__all_college_assessments") }} as s
        inner join
            {{ ref("int_extracts__student_enrollments") }} as e
            on s.academic_year = e.academic_year
            and s.student_number = e.student_number
            and e.school_level = 'HS'
            and e.rn_year = 1
        where s.is_overall_score = 1
    ),

    /*
        The goal columns have no consumer yet -- all four consumers of this model
        read only the *_count_lifetime columns and rn_lifetime. Kept for the rpt
        views to pick up. See #4658.
    */
    attempt_goals_long as (
        select
            test_type, expected_metric_label, expected_min_score, expected_metric_goal,

        from {{ ref("int_google_sheets__kippfwd__goals_unpivot") }}
        where expected_goal_type = 'Attempts'
    )

select
    a.academic_year,
    a.student_number,
    a.test_type,
    a.salesforce_id,
    a.grade_level,
    a.yearly_psat89 as psat89_count,
    a.yearly_psat10 as psat10_count,
    a.yearly_psatnmsqt as psatnmsqt_count,
    a.yearly_sat as sat_count,
    a.yearly_act as act_count,

    g.min_score_sat_1_attempt,
    g.pct_goal_sat_1_attempt,
    g.min_score_sat_2_plus_attempts,
    g.pct_goal_sat_2_plus_attempts,
    g.min_score_psat89_1_attempt,
    g.pct_goal_psat89_1_attempt,
    g.min_score_psat10_1_attempt,
    g.pct_goal_psat10_1_attempt,
    g.min_score_psatnmsqt_1_attempt,
    g.pct_goal_psatnmsqt_1_attempt,

    /*
        The pivot leaves a lifetime cell null in any year the student did not sit
        that test, so it is spread across every one of their rows here. Without
        it, rn_lifetime = 1 can land on a year with no sitting and report null.
        test_type is in every partition so a practice sitting never inflates an
        official count, and rn_lifetime = 1 yields one row per test type.
    */
    max(a.lifetime_psat89) over (
        partition by a.student_number, a.test_type
    ) as psat89_count_lifetime,
    max(a.lifetime_psat10) over (
        partition by a.student_number, a.test_type
    ) as psat10_count_lifetime,
    max(a.lifetime_psatnmsqt) over (
        partition by a.student_number, a.test_type
    ) as psatnmsqt_count_lifetime,
    max(a.lifetime_sat) over (
        partition by a.student_number, a.test_type
    ) as sat_count_lifetime,
    max(a.lifetime_act) over (
        partition by a.student_number, a.test_type
    ) as act_count_lifetime,

    row_number() over (partition by a.student_number, a.test_type) as rn_lifetime,

from
    attempts pivot (
        max(yearly_attempts_totals) as yearly,
        max(attempt_lifetime) as lifetime
        for score_type in (
            'psat89_total' as psat89,
            'psat10_total' as psat10,
            'psatnmsqt_total' as psatnmsqt,
            'sat_total_score' as sat,
            'act_composite' as act
        )
    ) as a
-- trunk-ignore(sqlfluff/AM08): on clause below; parser misses it across the pivot
inner join
    attempt_goals_long pivot (
        avg(expected_min_score) as min_score,
        avg(expected_metric_goal) as pct_goal
        for expected_metric_label in (
            'sat_1_attempt',
            'sat_2_plus_attempts',
            'psat89_1_attempt',
            'psat10_1_attempt',
            'psatnmsqt_1_attempt'
        )
    ) as g
    on a.test_type = g.test_type
