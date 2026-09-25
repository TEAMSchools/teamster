select s.*, p.active_label,
from {{ ref("stg_focus__users") }} as s
left join {{ ref("int_focus__users__pivot") }} as p on s.staff_id = p.staff_id
