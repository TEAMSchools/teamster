-- Staging columns plus their decoded custom-field labels. Drives from staging
-- and LEFT JOINs the pivot: BigQuery UNPIVOT drops entities whose unpivoted
-- columns are all null, so the pivot alone is not a complete entity spine.
select s.*, p.active_label,
from {{ ref("stg_focus__users") }} as s
left join {{ ref("int_focus__users__pivot") }} as p on s.staff_id = p.staff_id
