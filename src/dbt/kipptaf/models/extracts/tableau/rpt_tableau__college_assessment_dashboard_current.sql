with
    strategy as (
        -- need a distinct strategy scaffold
        select distinct
            test_type as expected_test_type,
            scope as expected_scope,
            subject_area as expected_subject_area,
            score_type as expected_score_type,

            'foo' as bar,

        from {{ ref("int_assessments__college_assessment") }}
        where test_type = 'Official' and subject_area in ('Composite', 'Combined')
    ),

    max_attempts as (
        select
            student_number,

            max(psat89_count_ytd) as psat89_count_ytd,
            max(psat10_count_ytd) as psat10_count_ytd,
            max(psatnmsqt_count_ytd) as psatnmsqt_count_ytd,
            max(sat_count_ytd) as sat_count_ytd,
            max(act_count_ytd) as act_count_ytd,

        from {{ ref("int_students__college_assessment_participation_roster") }}
        group by student_number
    ),

    attempts as (
        select
            student_number,

            attempt_count_ytd,

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
            max_attempts unpivot (
                attempt_count_ytd for scope in (
                    psat89_count_ytd,
                    psat10_count_ytd,
                    psatnmsqt_count_ytd,
                    sat_count_ytd,
                    act_count_ytd
                )
            )
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

            s.test_type,
            s.scope,
            s.subject_area,
            s.score_type,

            bg.expected_metric_name,
            bg.min_score as expected_metric_min_score,
            bg.pct_goal as expected_metric_pct_goal,

            avg(
                if(
                    bg.expected_metric_name in ('HS-Ready', 'College-Ready'),
                    s.max_scale_score,
                    p.attempt_count_ytd
                )
            ) as score,

        from {{ ref("int_extracts__student_enrollments") }} as e
        inner join strategy as r on 'foo' = r.bar
        left join
            {{ ref("int_students__college_assessment_roster") }} as s
            on e.student_number = s.student_number
            and r.expected_scope = s.scope
            and s.test_type = 'Official'
            and s.subject_area in ('Composite', 'Combined')
        left join
            attempts as p
            on e.student_number = p.student_number
            and r.expected_scope = p.scope
        left join
            {{ ref("stg_google_sheets__kippfwd_goals") }} as bg
            on s.test_type = bg.expected_test_type
            and s.scope = bg.expected_scope
            and s.score_type = bg.expected_score_type
            and bg.expected_goal_type != 'Board'
        where
            e.academic_year = {{ var("current_academic_year") }}
            and e.school_level = 'HS'
            and e.rn_year = 1
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
            s.test_type,
            s.scope,
            s.subject_area,
            s.score_type,
            bg.expected_metric_name,
            bg.min_score,
            bg.pct_goal
    )

select *, if(score >= expected_metric_min_score, 1, 0) as met_min_score_int,

from roster
