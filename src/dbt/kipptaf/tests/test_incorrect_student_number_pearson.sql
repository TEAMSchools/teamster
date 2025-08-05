{{
    config(
        severity="warn", store_failures=true, store_failures_as="view", enabled=false
    )
}}

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
    {{ ref("base_powerschool__student_enrollments") }} as e
    on a.localstudentidentifier = e.student_number
    and a.academic_year = e.academic_year
    and {{ union_dataset_join_clause(left_alias="a", right_alias="e") }}
    and e.rn_year = 1
where
    /* we only report on SY 2017+ scores */
    a.academic_year >= 2017
    and (e.student_number is null or a.localstudentidentifier is null)
