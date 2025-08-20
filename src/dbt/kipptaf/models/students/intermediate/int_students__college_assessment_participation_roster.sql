select
    e._dbt_source_relation,
    e.student_number,
    e.salesforce_id,
    e.grade_level,

    a.test_month,
    a.score_type,

from {{ ref("int_extracts__student_enrollments") }} as e
inner join
    {{ ref("int_assessments__college_assessment") }} as a
    on e.academic_year = a.academic_year
    and e.student_number = a.student_number
where e.school_level = 'HS' and e.rn_year = 1
