select
    e._dbt_source_relation,
    e.academic_year,
    e.academic_year_display,
    e.region,
    e.schoolid,
    e.school,
    e.student_number,
    e.studentid,
    e.students_dcid,
    e.student_name,
    e.student_first_name,
    e.student_last_name,
    e.grade_level,
    e.enroll_status,
    e.cohort,
    e.iep_status,
    e.is_504,
    e.grad_iep_exempt_status_overall,
    e.lep_status,
    e.gifted_and_talented,
    e.advisory,
    e.student_email,
    e.rn_undergrad,
    e.salesforce_id,
    e.ktc_cohort,
    e.graduation_year,
    e.year_in_network,
    e.contact_owner_name,
    e.college_match_gpa,
    e.college_match_gpa_bands,
    e.cumulative_y1_gpa,
    e.cumulative_y1_gpa_unweighted,
    e.cumulative_y1_gpa_projected,
    e.cumulative_y1_gpa_projected_s1,
    e.cumulative_y1_gpa_projected_s1_unweighted,
    e.core_cumulative_y1_gpa,

    a.administration_round,
    a.test_type,
    a.test_date,
    a.test_month,
    a.scope,
    a.subject_area,
    a.course_discipline,
    a.score_type,
    a.scale_score,
    a.previous_total_score_change,
    a.rn_highest,
    a.max_scale_score,
    a.superscore,
    a.running_max_scale_score,
    a.running_superscore,

    concat(
        a.administration_round, ' ', a.scope, ' ', a.subject_area, ' ', a.test_type
    ) as test_admin_for_roster,

from {{ ref("int_extracts__student_enrollments") }} as e
inner join
    {{ ref("int_assessments__college_assessment") }} as a
    on e.academic_year = a.academic_year
    and e.student_number = a.student_number
    and a.score_type not in (
        'psat10_reading',
        'psat10_math_test',
        'sat_math_test_score',
        'sat_reading_test_score'
    )
where e.school_level = 'HS' and e.rn_year = 1
