select s.*, p.fefp_label, p.dual_enrollment_indicator_label,
from {{ ref("stg_focus__master_courses") }} as s
left join
    {{ ref("int_focus__master_courses__pivot") }} as p on s.course_id = p.course_id
