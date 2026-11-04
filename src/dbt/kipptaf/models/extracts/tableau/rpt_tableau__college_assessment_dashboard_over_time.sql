with
    scores as (
        select
            student_number,
            test_type,
            scope,
            score_type,
            subject_area,
            aligned_subject_area,
            aligned_subject,
            strategy_case,

            max(scale_score) as max_scale_score,
            max(attempt_lifetime) as attempt_count_lifetime,

        from {{ ref("int_assessments__all_college_assessments") }}
        group by
            student_number,
            test_type,
            scope,
            score_type,
            subject_area,
            aligned_subject_area,
            aligned_subject,
            strategy_case
    ),

    goals as (
        select
            test_type as expected_test_type,
            score_type as expected_score_type,
            expected_scope,
            expected_aligned_scope,
            expected_subject_area,
            expected_aligned_subject_area,
            expected_aligned_subject,
            expected_goal_type,
            expected_goal_subtype,
            expected_metric_name,
            expected_metric_goal as pct_goal,

            cast(expected_min_score as float64) as min_score,

        from {{ ref("int_google_sheets__kippfwd__goals_unpivot") }}
        cross join unnest(rpt_consumers) as rpt_consumer
        where rpt_consumer = 'rpt_tableau__college_assessment_dashboard_over_time'
    ),

    roster as (
        select
            e.region,
            e.school,
            e.student_number,
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

            g.expected_test_type,
            g.expected_scope,
            g.expected_aligned_scope,
            g.expected_score_type,
            g.expected_subject_area,
            g.expected_aligned_subject_area,
            g.expected_aligned_subject,
            g.expected_goal_type,
            g.expected_goal_subtype,
            g.expected_metric_name,
            g.min_score,
            g.pct_goal,

            s.test_type,
            s.scope,
            s.score_type,
            s.subject_area,
            s.aligned_subject_area,
            s.aligned_subject,
            s.max_scale_score,

            coalesce(s.strategy_case, 'No testing history') as strategy_case,

            avg(
                if(
                    g.expected_goal_type = 'Attempts',
                    s.attempt_count_lifetime,
                    s.max_scale_score
                )
            ) as score,

        from {{ ref("int_extracts__student_enrollments") }} as e
        cross join goals as g
        left join
            scores as s
            on e.student_number = s.student_number
            and g.expected_test_type = s.test_type
            and g.expected_score_type = s.score_type
        where
            e.school_level = 'HS'
            and e.rn_undergrad = 1
            and e.rn_year = 1
            and not e.is_out_of_district
        group by
            e.region,
            e.school,
            e.student_number,
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
            g.expected_test_type,
            g.expected_scope,
            g.expected_aligned_scope,
            g.expected_score_type,
            g.expected_subject_area,
            g.expected_aligned_subject_area,
            g.expected_aligned_subject,
            g.expected_goal_type,
            g.expected_goal_subtype,
            g.expected_metric_name,
            g.min_score,
            g.pct_goal,
            s.test_type,
            s.scope,
            s.score_type,
            s.subject_area,
            s.aligned_subject_area,
            s.aligned_subject,
            s.max_scale_score,
            s.strategy_case
    )

select
    *,

    if(score >= min_score, 1, 0) as met_min_score_int,

    max(
        if(
            (expected_goal_subtype = '1 Attempt' and score = min_score)
            or (expected_goal_subtype != '1 Attempt' and score >= min_score),
            1,
            0
        )
    ) over (
        partition by
            student_number,
            expected_test_type,
            expected_score_type,
            expected_metric_name
    ) as alt_met_min_score_int_overall_score_type,

    max(
        if(
            (expected_goal_subtype = '1 Attempt' and score = min_score)
            or (expected_goal_subtype != '1 Attempt' and score >= min_score),
            1,
            0
        )
    ) over (
        partition by
            student_number,
            expected_test_type,
            expected_aligned_subject,
            expected_metric_name
    ) as alt_met_min_score_int_overall_aligned_subject,

    max(if(score >= min_score, 1, 0)) over (
        partition by
            student_number,
            expected_test_type,
            expected_score_type,
            expected_metric_name
    ) as met_min_score_int_overall_score_type,

    max(if(score >= min_score, 1, 0)) over (
        partition by
            student_number,
            expected_test_type,
            expected_aligned_subject,
            expected_metric_name
    ) as met_min_score_int_overall_aligned_subject,

    max(if(score >= min_score, 1, 0)) over (
        partition by
            student_number,
            expected_test_type,
            expected_aligned_scope,
            expected_aligned_subject,
            expected_metric_name
    ) as met_min_score_int_overall_aligned_scope_subject,

from roster
