select
    a.student_test_uuid,
    a.student_number,
    a.state_student_id,
    a.first_name,
    a.last_or_surname,
    a.academic_year,
    a.test_code,

    e.student_number as enrollment_student_number,
from {{ ref("int_assessments__state_nj_scores") }} as a
left join
    {{ ref("base_powerschool__student_enrollments") }} as e
    on a.student_number = e.student_number
    and a.academic_year = e.academic_year
    and a._dbt_source_project = e._dbt_source_project
    and e.rn_year = 1
where
    /* we only report on SY 2017+ scores */
    a.academic_year >= 2017 and (e.student_number is null or a.student_number is null)
