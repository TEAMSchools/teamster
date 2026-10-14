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
    and (
        f.free_reduced_meals_program_label is null
        or f.free_reduced_meals_program_label not like 'CEP%'
    )
