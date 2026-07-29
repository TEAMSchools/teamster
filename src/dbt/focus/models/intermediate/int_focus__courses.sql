-- Staging columns plus their decoded custom-field labels. Drives from staging
-- and LEFT JOINs the pivot: BigQuery UNPIVOT drops entities whose unpivoted
-- columns are all null, so the pivot alone is not a complete entity spine.
select s.*, p.course_sequence_label, p.ocp_label,
from {{ ref("stg_focus__courses") }} as s
left join {{ ref("int_focus__courses__pivot") }} as p on s.course_id = p.course_id
