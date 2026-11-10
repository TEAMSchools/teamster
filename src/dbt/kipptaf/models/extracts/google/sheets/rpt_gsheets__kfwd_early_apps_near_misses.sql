select
    c._dbt_source_project,
    c.overgrad_student_id,
    c.criterion_code,
    c.criterion_sort,

    r.student_name,
    r.high_school,
    r.counselor_name,

    c.gpa_band,
    c.criterion_label,
    c.what_they_have,
    c.what_would_close_it,
from {{ ref("int_students__early_application_criteria_scaffold") }} as c
inner join
    {{ ref("int_students__early_applications_rollup") }} as r
    on c.overgrad_student_id = r.overgrad_student_id
    and c._dbt_source_project = r._dbt_source_project
where c.is_near_miss and r.is_ed_ea_flagged
