with
    goals_distinct as (
        select
            expected_test_type,
            expected_score_type,
            expected_metric_name,

            avg(min_score) as min_score,

        from {{ ref("stg_google_sheets__kippfwd_goals") }}
        where expected_goal_type = 'Benchmark' and region is null and schoolid is null
        group by expected_test_type, expected_score_type, expected_metric_name
    ),

    final as (
        select
            e.region,
            e.schoolid,
            e.school,
            e.student_number,
            e.salesforce_id,
            e.student_name,
            e.student_first_name,
            e.student_last_name,
            e.grade_level,
            e.student_email,
            e.enroll_status,
            e.ktc_cohort,
            e.graduation_year,
            e.year_in_network,
            e.iep_status,
            e.grad_iep_exempt_status_overall,
            e.cumulative_y1_gpa,
            e.cumulative_y1_gpa_projected,
            e.college_match_gpa,
            e.college_match_gpa_bands,

            sc.scope,
            sc.subject_area,
            sc.test_date,
            sc.score_type,
            sc.scale_score,

            g.min_score,
            g.expected_metric_name,

            ss.superscore as sat_total_superscore,

            he.max_scale_score as sat_ebrw_highest,

            hm.max_scale_score as sat_math_highest,

            coalesce(c.courses_course_name, 'No Data') as ccr_course,
            coalesce(c.teacher_lastfirst, 'No Data') as ccr_teacher_name,
            coalesce(c.sections_external_expression, 'No Data') as ccr_section,

            if(sc.scale_score >= g.min_score, 'Yes', 'No') as met_minimum,
            if(sc.rn_highest = 1, 'Yes', 'No') as highest_score_by_test,

        from {{ ref("int_extracts__student_enrollments") }} as e
        left join
            {{ ref("int_assessments__college_assessment") }} as sc
            on e.student_number = sc.student_number
        left join
            goals_distinct as g
            on sc.test_type = g.expected_test_type
            and sc.score_type = g.expected_score_type
        left join
            {{ ref("int_assessments__college_assessment") }} as ss
            on e.student_number = ss.student_number
            and ss.scope = 'SAT'
            and ss.aligned_subject_area = 'Total'
            and ss.rn_highest = 1
        left join
            {{ ref("int_assessments__college_assessment") }} as he
            on e.student_number = he.student_number
            and he.scope = 'SAT'
            and he.aligned_subject_area = 'EBRW'
            and he.rn_highest = 1
        left join
            {{ ref("int_assessments__college_assessment") }} as hm
            on e.student_number = hm.student_number
            and hm.scope = 'SAT'
            and hm.aligned_subject_area = 'Math'
            and hm.rn_highest = 1
        left join
            {{ ref("base_powerschool__course_enrollments") }} as c
            on e.student_number = c.students_student_number
            and e.academic_year = c.cc_academic_year
            and c.rn_course_number_year = 1
            and not c.is_dropped_section
            and c.courses_course_name in (
                'College and Career IV',
                'College and Career I',
                'College and Career III',
                'College and Career II'
            )
        where
            e.academic_year = {{ var("current_academic_year") }}
            and e.graduation_year >= {{ var("current_academic_year") + 1 }}
            and e.school_level = 'HS'
            and e.rn_year = 1
    )

select
    region,
    schoolid,
    school,
    student_number,
    salesforce_id,
    student_name,
    student_first_name,
    student_last_name,
    grade_level,
    student_email,
    enroll_status,
    ktc_cohort,
    graduation_year,
    year_in_network,
    iep_status,
    grad_iep_exempt_status_overall,
    cumulative_y1_gpa,
    cumulative_y1_gpa_projected,
    college_match_gpa,
    college_match_gpa_bands,
    ccr_course,
    ccr_teacher_name,
    ccr_section,

    sat_total_superscore,
    sat_ebrw_highest,
    sat_math_highest,

    scope as test_type,
    test_date,
    subject_area as test_subject,
    scale_score,
    highest_score_by_test,
    min_score,

    coalesce(hs_grad_ready, 'NA') as hs_grad_ready,
    coalesce(college_ready, 'NA') as college_ready,

from
    final pivot (
        any_value(met_minimum) for expected_metric_name
        in ('HS-Grad Ready' as hs_grad_ready, 'College-Ready' as college_ready)
    )
where
    score_type not in (
        'act_science',
        'act_english',
        'psat10_reading',
        'psat10_math_test',
        'sat_reading_test_score',
        'sat_math_test_score'
    )
