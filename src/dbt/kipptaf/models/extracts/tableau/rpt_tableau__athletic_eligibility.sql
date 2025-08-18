select
    e._dbt_source_relation,
    e.academic_year,
    e.academic_year_display,
    e.region,
    e.schoolid,
    e.school,
    e.student_number,
    e.studentid,
    e.student_last_name,
    e.student_first_name,
    e.student_name,
    e.grade_level,
    e.gender,
    e.ethnicity,
    e.cohort,
    e.student_email,

    a.grade_level_prev,
    a.dob,
    a.cy_unweighted_term_q1,
    a.cy_weighted_term_q1,
    a.cy_unweighted_s1_ada,
    a.cy_weighted_s1_ada,
    a.py_y1_unweighted_ada,
    a.py_y1_weighted_ada,
    a.cy_q1_gpa,
    a.cy_s1_gpa,
    a.py_y1_gpa,
    a.py_credits,
    a.met_py_credits,
    a.met_cy_credits,
    a.is_first_time_ninth,
    a.is_age_eligible,
    a.q1_ae_status,
    a.q2_ae_status,
    a.q3_ae_status,
    a.q4_ae_status,

from {{ ref("int_extracts__student_enrollments") }} as e
left join
    {{ ref("int_students__athletic_eligibility") }} as a
    on e.academic_year = a.academic_year
    and e.student_number = a.student_number
    and {{ union_dataset_join_clause(left_alias="e", right_alias="a") }}
where
    e.academic_year = {{ var("current_academic_year") }}
    and e.grade_level >= 9
    and e.rn_year = 1
    and e.enroll_status = 0
    and not e.is_out_of_district
