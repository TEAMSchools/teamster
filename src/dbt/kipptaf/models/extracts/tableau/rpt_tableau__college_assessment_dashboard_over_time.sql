with
    attempts as (
        select
            student_number,
            attempt_count_lifetime,

            case
                scope
                when 'act_count_lifetime'
                then 'ACT'
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
                    sat_count_lifetime,
                    act_count_lifetime
                )
            )
        where rn_lifetime = 1
    ),

    alt_attempts as (
        select student_number, scope, count(*) as alt_attempt_count_lifetime,
        from {{ ref("int_assessments__college_assessment") }}
        where aligned_subject_area = 'Total'
        group by student_number, scope
    ),

    alt_max_scale_score as (
        select student_number, score_type, max(scale_score) as alt_max_scale_score,
        from {{ ref("int_assessments__college_assessment") }}
        group by student_number, score_type
    ),

    goals as (
        select *,
        from {{ ref("stg_google_sheets__kippfwd_goals") }}
        where
            region is null
            and schoolid is null
            and (grade_level is null or grade_level = 12)
            and expected_goal_type != 'Board'
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
            s.strategy_case,

            avg(
                case
                    when
                        g.expected_goal_type = 'Benchmark' and s.max_scale_score is null
                    then c.alt_max_scale_score
                    when
                        g.expected_goal_type = 'Benchmark'
                        and s.max_scale_score is not null
                    then s.max_scale_score
                    when
                        g.expected_goal_type = 'Attempts'
                        and a.attempt_count_lifetime is null
                    then b.alt_attempt_count_lifetime
                    when
                        g.expected_goal_type = 'Attempts'
                        and a.attempt_count_lifetime != b.alt_attempt_count_lifetime
                    then b.alt_attempt_count_lifetime
                    else a.attempt_count_lifetime
                end
            ) as score,

        from {{ ref("int_extracts__student_enrollments") }} as e
        cross join goals as g
        left join
            {{ ref("int_assessments__college_assessment") }} as s
            on e.student_number = s.student_number
            and g.expected_score_type = s.score_type
            and s.rn_highest = 1
        left join
            attempts as a on s.student_number = a.student_number and s.scope = a.scope
        left join
            alt_attempts as b
            on s.student_number = b.student_number
            and s.scope = b.scope
        left join
            alt_max_scale_score as c
            on s.student_number = c.student_number
            and s.score_type = c.score_type
        where e.school_level = 'HS' and e.rn_undergrad = 1 and e.rn_year = 1
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
            s.max_scale_score
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

from roster
