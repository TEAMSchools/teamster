select
    jg.id,
    jg.group_id,
    jg.student_id,
    jg.syear,
    jg.created_at,

    sg.title,
    sg.start_date,
    sg.end_date,
from {{ ref("stg_focus__students_join_groups") }} as jg
inner join {{ ref("stg_focus__student_groups") }} as sg on jg.group_id = sg.id
