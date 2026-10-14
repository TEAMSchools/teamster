select s.student_number,
from {{ ref("int_students__students") }} as s
left join
    {{ ref("int_focus__students") }} as f
    on s.student_number = f.student_number
    and s._dbt_source_project = f._dbt_source_project
where
    s._dbt_source_project = 'kippmiami'
    and s.enroll_status = 0
    and s.lunchstatus is null
    and f.meal_c is null
