select
    e.academic_year,
    e.region,
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

    s.test_type,
    s.scope,
    s.score_type,
    s.subject_area,
    s.test_date,
    s.max_scale_score,
    s.scale_score,

    ce.teacher_lastfirst as ccr_teacher,
    ce.sections_external_expression as ccr_period,

from {{ ref("int_extracts__student_enrollments") }} as e
inner join
    {{ ref("int_assessments__college_assessment") }} as s
    on e.student_number = s.student_number
    and e.academic_year = s.academic_year
    and s.scope != 'ACT'
    and s.score_type not in (
        'psat10_math_test',
        'psat10_reading',
        'sat_math_test_score',
        'sat_reading_test_score'
    )
left join
    {{ ref("base_powerschool__course_enrollments") }} as ce
    on e.student_number = ce.students_student_number
    and e.academic_year = ce.cc_academic_year
    and ce.courses_course_name like 'College and Career%'
    and ce.rn_course_number_year = 1
    and not ce.is_dropped_section
where
    e.school_level = 'HS'
    and e.rn_undergrad = 1
    and e.rn_year = 1
    and not e.is_out_of_district
