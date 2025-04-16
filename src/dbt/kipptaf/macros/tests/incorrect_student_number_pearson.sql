select
    a.academic_year,
    a.localstudentidentifier,
    a.statestudentidentifier,
    a.firstname,
    a.lastorsurname,
    a.testcode,

    e.student_number,

from {{ ref("int_pearson__all_assessments") }} as a
left join
    {{ ref("int_extracts__student_enrollments") }} as e
    on a.academic_year = e.academic_year
    and a.localstudentidentifier = e.student_number
where
    a.academic_year >= 2017
    and (student_number is null or localstudentidentifier is null)
