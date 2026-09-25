select s.*, p.course_sequence_label, p.ocp_label,
from {{ ref("stg_focus__courses") }} as s
left join {{ ref("int_focus__courses__pivot") }} as p on s.course_id = p.course_id
