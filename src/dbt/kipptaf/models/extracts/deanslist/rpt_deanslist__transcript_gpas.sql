select
    e.student_number,
    e.academic_year,

    g.gpa_y1 as `GPA_Y1_weighted`,
    g.gpa_y1_unweighted as `GPA_Y1_unweighted`,
from {{ ref("base_powerschool__student_enrollments") }} as e
inner join
    {{ ref("int_powerschool__gpa_term") }} as g
    on e.studentid = g.studentid
    and e.yearid = g.yearid
    and e.schoolid = g.schoolid
    and {{ union_dataset_join_clause(left_alias="e", right_alias="g") }}
    and g.is_current
where e.rn_year = 1

union all

select
    e.student_number,
    null as academic_year,

    c.cumulative_y1_gpa as `GPA_Y1_weighted`,
    c.cumulative_y1_gpa_unweighted as `GPA_Y1_unweighted`,
from {{ ref("int_extracts__student_enrollments") }} as e
inner join
    {{ ref("int_powerschool__gpa_cumulative") }} as c
    on e.studentid = c.studentid
    and e.schoolid = c.schoolid
    and {{ union_dataset_join_clause(left_alias="e", right_alias="c") }}
where e.rn_undergrad = 1
