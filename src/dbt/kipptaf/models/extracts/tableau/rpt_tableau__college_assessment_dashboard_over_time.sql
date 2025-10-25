with
    attempts as (
        select
            student_number,
            attempt_count_lifetime,

            case
                scope
                when 'act_count_lifetime'
                then 'SAT'
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
    )

select
    s.student_number,
    s.test_type,
    s.scope,
    s.score_type,
    s.subject_area,
    s.aligned_subject_area,
    s.test_date,
    s.scale_score,
    s.rn_highest,
    s.max_scale_score,

    e.iep_status,
    e.is_504,
    e.grad_iep_exempt_status_overall,
    e.lep_status,
    e.ktc_cohort,
    e.graduation_year,
    e.year_in_network,
    e.college_match_gpa,
    e.college_match_gpa_bands,

    g.expected_metric_name,
    g.expected_goal_subtype,
    g.min_score,
    g.pct_goal,

    a.attempt_count_lifetime,

    case
        when
            s.score_type in (
                'act_reading',
                'sat_ebrw',
                'psat10_ebrw',
                'psatnmsqt_ebrw',
                'psat89_ebrw'
            )
        then 'EBRW/Reading'
        when s.aligned_subject_area = 'Total'
        then 'Total'
        else s.subject_area
    end as aligned_subject,

    avg(
        if(
            g.expected_metric_name in ('HS-Ready', 'College-Ready'),
            s.max_scale_score,
            a.attempt_count_lifetime
        )
    ) as score,

from {{ ref("int_assessments__college_assessment") }} as s
inner join
    {{ ref("int_extracts__student_enrollments") }} as e
    on s.student_number = e.student_number
    and e.school_level = 'HS'
    and e.rn_undergrad = 1
    and e.rn_year = 1
left join
    {{ ref("stg_google_sheets__kippfwd_goals") }} as g
    on s.test_type = g.expected_test_type
    and s.score_type = g.expected_score_type
    and g.expected_goal_type != 'Board'
left join attempts as a on s.student_number = a.student_number and s.scope = a.scope
where
    s.score_type not in (
        'act_english',
        'act_science',
        'psat10_math_test',
        'psat10_reading',
        'sat_math_test_score',
        'sat_reading_test_score'
    )
group by
    s.student_number,
    s.test_type,
    s.scope,
    s.score_type,
    s.subject_area,
    s.aligned_subject_area,
    s.test_date,
    s.scale_score,
    s.rn_highest,
    s.max_scale_score,
    e.iep_status,
    e.is_504,
    e.grad_iep_exempt_status_overall,
    e.lep_status,
    e.ktc_cohort,
    e.graduation_year,
    e.year_in_network,
    e.college_match_gpa,
    e.college_match_gpa_bands,
    g.expected_metric_name,
    g.expected_goal_subtype,
    g.min_score,
    g.pct_goal,
    a.attempt_count_lifetime
