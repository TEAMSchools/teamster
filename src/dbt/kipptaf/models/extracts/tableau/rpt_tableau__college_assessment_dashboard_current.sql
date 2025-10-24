with
    strategy as (
        -- need distinct strategy for expected tests
        select distinct
            s.test_type as expected_test_type,
            s.scope as expected_scope,
            s.subject_area as expected_subject_area,
            s.score_type as expected_score_type,
            s.test_date as expected_test_date,

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
        where s.subject_area = 'Combined'
    ),

    attempts as (
        select
            student_number,

            attempt_count_lifetime,

            case
                scope
                when 'sat_count_lifetime'
                then 'SAT'
                when 'psatnmsqt_count_lifetime'
                then 'PSAT NMSQT'
                when 'psat10_count_lifetime'
                then 'PSAT10'
                when 'psat89_count_lifetime'
                then 'PSAT 8/9'
            end as scope,

        from
            {{ ref("int_students__college_assessment_participation_roster") }} unpivot (
                attempt_count_lifetime for scope in (
                    psat89_count_lifetime,
                    psat10_count_lifetime,
                    psatnmsqt_count_lifetime,
                    sat_count_lifetime
                )
            )
        where rn_lifetime = 1
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
            r.expected_test_date,
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
            s.test_date,
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
            r.expected_test_date,
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
            s.test_date,
            s.subject_area,
            s.score_type
    )

select
    *,

    if(score >= expected_metric_min_score, 1, 0) as met_min_score_int,
    if(score >= expected_board_min_score, 1, 0) as met_min_board_score_int,

    max(if(score >= expected_metric_min_score, 1, 0)) over (
        partition by
            student_number,
            expected_test_type,
            expected_score_type,
            expected_metric_name
        order by expected_test_date
    ) as met_min_score_int_overall,

    max(if(score >= expected_board_min_score, 1, 0)) over (
        partition by
            student_number,
            expected_test_type,
            expected_score_type,
            expected_metric_name
        order by expected_test_date
    ) as met_min_board_score_int_overall,

from roster
