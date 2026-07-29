-- Staging columns plus their decoded custom-field labels. Drives from staging
-- and LEFT JOINs the pivot: BigQuery UNPIVOT drops entities whose unpivoted
-- columns are all null, so the pivot alone is not a complete entity spine.
select s.*, p.school_level_label, p.school_type_label, p.technical_center_label,
from {{ ref("stg_focus__schools") }} as s
left join {{ ref("int_focus__schools__pivot") }} as p on s.id = p.id
