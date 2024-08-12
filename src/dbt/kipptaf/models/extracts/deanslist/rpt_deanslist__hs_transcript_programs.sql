select
    s.student_number,

    cast(sp.academic_year as string)
    || '-'
    || right(cast(sp.academic_year + 1 as string), 2) as academic_year_display,

    regexp_replace(sp.specprog_name, r'^High School ', '') as program_name,
from {{ ref("stg_powerschool__students") }} as s
inner join
    {{ ref("int_powerschool__spenrollments") }} as sp
    on s.id = sp.studentid
    and {{ union_dataset_join_clause(left_alias="s", right_alias="sp") }}
    and sp.specprog_name like 'High School%'
where s.grade_level >= 9  /* needs to include grade_level = 99 */
