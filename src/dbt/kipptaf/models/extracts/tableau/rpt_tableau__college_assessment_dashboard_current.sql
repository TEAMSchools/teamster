-- participation redo
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

            act_1_attempt_min_score,
            psat10_1_attempt_min_score,
            psat89_1_attempt_min_score,
            psatnmsqt_1_attempt_min_score,
            sat_1_attempt_min_score,
            act_2_plus_attempts_min_score,
            psat10_2_plus_attempts_min_score,
            psat89_2_plus_attempts_min_score,
            psatnmsqt_2_plus_attempts_min_score,
            sat_2_plus_attempts_min_score,
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
        select
            s.student_number,
            s.test_type,
            s.scope,
            s.score_type,

            e.salesforce_id,
            e.grade_level,

        from {{ ref("int_assessments__college_assessment") }} as s
        inner join
            {{ ref("int_extracts__student_enrollments") }} as e
            on s.academic_year = e.academic_year
            and s.student_number = e.student_number
            and e.school_level = 'HS'
            and e.rn_year = 1
        where
            s.score_type in (
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
    ),

    ytd_counts as (
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
    ),

    part_redo as (
        select
            *,

            max(psat89_count_ytd) over (
                partition by student_number
            ) as psat89_count_lifetime,
            max(psat10_count_ytd) over (
                partition by student_number
            ) as psat10_count_lifetime,
            max(psatnmsqt_count_ytd) over (
                partition by student_number
            ) as psatnmsqt_count_lifetime,
            max(sat_count_ytd) over (partition by student_number) as sat_count_lifetime,
            max(act_count_ytd) over (partition by student_number) as act_count_lifetime,

            row_number() over (partition by student_number) as rn_lifetime,

        from ytd_counts
    ),

    attempts as (
        select
            student_number,

            attempt_count_lifetime,

            case
                scope
                when 'act_count_ytd'
                then 'ACT'
                when 'sat_count_ytd'
                then 'SAT'
                when 'psatnmsqt_count_ytd'
                then 'PSAT NMSQT'
                when 'psat10_count_ytd'
                then 'PSAT10'
                when 'psat89_count_ytd'
                then 'PSAT 8/9'
            end as scope,

        from
            part_redo unpivot (
                attempt_count_lifetime for scope in (
                    psat89_count_lifetime,
                    psat10_count_lifetime,
                    psatnmsqt_count_lifetime,
                    sat_count_lifetime,
                    act_count_lifetime
                )
            )
        where rn_lifetime = 1
    ),

    -- current redo
    strategy as (
        select
            -- need distinct strategy for expected tests
            distinct
            s.test_type as expected_test_type,
            s.scope as expected_scope,
            s.subject_area as expected_subject_area,
            s.score_type as expected_score_type,

            g.expected_goal_type,
            g.expected_goal_subtype,
            g.expected_metric_name,
            g.expected_metric_label,
            g.min_score as expected_metric_min_score,
            g.pct_goal as expected_metric_pct_goal,

            b1.min_score as expected_board_min_score_g11,
            b1.pct_goal as expected_board_pct_goal_g11,

            b2.min_score as expected_board_min_score_g12,
            b2.pct_goal as expected_board_pct_goal_g12,

        from {{ ref("int_assessments__college_assessment") }} as s
        inner join
            {{ ref("stg_google_sheets__kippfwd_goals") }} as g
            on s.score_type = g.expected_score_type
            and g.expected_goal_type != 'Board'
        left join
            {{ ref("stg_google_sheets__kippfwd_goals") }} as b1
            on s.score_type = b1.expected_score_type
            and b1.expected_goal_type = 'Board'
            and b1.grade_level = 11
        left join
            {{ ref("stg_google_sheets__kippfwd_goals") }} as b2
            on s.score_type = b2.expected_score_type
            and b2.expected_goal_type = 'Board'
            and b2.grade_level = 12
        where
            s.test_type = 'Official'
            and s.subject_area in ('Composite', 'Combined')
            and s.scope != 'ACT'
    ),

    roster as (
        select
            e.academic_year,
            e.academic_year_display,
            e.state,
            e.region,
            e.schoolid,
            e.school,
            e.student_number,
            e.grade_level,
            e.enroll_status,
            e.iep_status,
            e.is_504,
            e.grad_iep_exempt_status_overall,
            e.lep_status,
            e.ktc_cohort,
            e.graduation_year,
            e.year_in_network,
            e.college_match_gpa,
            e.college_match_gpa_bands,

            r.expected_test_type,
            r.expected_scope,
            r.expected_subject_area,
            r.expected_score_type,
            r.expected_goal_type,
            r.expected_goal_subtype,
            r.expected_metric_name,
            r.expected_metric_label,
            r.expected_metric_min_score,
            r.expected_metric_pct_goal,

            s.test_type,
            s.scope,
            s.subject_area,
            s.score_type,

            min(
                case
                    e.grade_level
                    when 11
                    then r.expected_board_min_score_g11
                    when 12
                    then r.expected_board_min_score_g12
                end
            ) as expected_board_min_score,

            min(
                case
                    e.grade_level
                    when 11
                    then r.expected_board_pct_goal_g11
                    when 12
                    then r.expected_board_pct_goal_g12
                end
            ) as expected_board_min_pct_goal,

            avg(
                if(
                    r.expected_metric_name in ('HS-Ready', 'College-Ready'),
                    s.max_scale_score,
                    p.attempt_count_lifetime
                )
            ) as score,

        from {{ ref("int_extracts__student_enrollments") }} as e
        cross join strategy as r
        left join
            {{ ref("int_assessments__college_assessment") }} as s
            on e.student_number = s.student_number
            and r.expected_scope = s.scope
            and s.subject_area = 'Combined'
        left join
            attempts as p
            on e.student_number = p.student_number
            and r.expected_scope = p.scope
        where e.academic_year = 2025 and e.school_level = 'HS' and e.rn_year = 1
        group by
            e.academic_year,
            e.academic_year_display,
            e.state,
            e.region,
            e.schoolid,
            e.school,
            e.student_number,
            e.grade_level,
            e.enroll_status,
            e.iep_status,
            e.is_504,
            e.grad_iep_exempt_status_overall,
            e.lep_status,
            e.ktc_cohort,
            e.graduation_year,
            e.year_in_network,
            e.college_match_gpa,
            e.college_match_gpa_bands,
            r.expected_test_type,
            r.expected_scope,
            r.expected_subject_area,
            r.expected_score_type,
            r.expected_goal_type,
            r.expected_goal_subtype,
            r.expected_metric_name,
            r.expected_metric_label,
            r.expected_metric_min_score,
            r.expected_metric_pct_goal,
            s.test_type,
            s.scope,
            s.subject_area,
            s.score_type
    )

select
    *,

    if(score >= expected_metric_min_score, 1, 0) as met_min_score_int,
    if(score >= roster.expected_board_min_score, 1, 0) as met_min_board_score_int,

from roster
