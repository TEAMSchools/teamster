select
    a.studenttestuuid,
    a.localstudentidentifier,
    a.statestudentidentifier,
    a.firstname,
    a.lastorsurname,
    a.academic_year,
    a.testcode,

    e.student_number,
from {{ ref("int_pearson__all_assessments") }} as a
left join
    {{ ref("base_powerschool__student_enrollments") }} as e
    on a.localstudentidentifier = e.student_number
    and a.academic_year = e.academic_year
    and a._dbt_source_project = e._dbt_source_project
    and e.rn_year = 1
where
    /* we only report on SY 2017+ scores */
    a.academic_year >= 2017
    and (e.student_number is null or a.localstudentidentifier is null)
