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
    -- we only report on SY 2017+ scores
    a.academic_year >= 2017
    and (e.student_number is null or a.localstudentidentifier is null)
