select
    s.academic_year,
    s.student_number,
    s.test_type,
    s.scope,
    s.subject_area,
    s.course_discipline,
    s.score_type,
    s.administration_round,
    s.test_date,
    s.test_month,
    s.scale_score,
    s.rn_highest,
    s.max_scale_score,
    s.running_max_scale_score,
    s.previous_total_score_change,
    s.superscore,
    s.running_superscore,
    s.field_name,
    s.aligned_subject_area,
    s.surrogate_key,

    e.grade_level,
    e.graduation_year,
    e.salesforce_id,

    concat(s.scope_order, s.date_order, s.subject_area_order) as expected_admin_order,

from {{ ref("int_assessments__college_assessment") }} as s
inner join
    {{ ref("int_extracts__student_enrollments") }} as e
    on s.academic_year = e.academic_year
    and s.student_number = e.student_number
    and e.school_level = 'HS'
    and e.rn_year = 1
where
    s.score_type not in (
        'psat10_reading',
        'psat10_math_test',
        'sat_math_test_score',
        'sat_reading_test_score'
    )
