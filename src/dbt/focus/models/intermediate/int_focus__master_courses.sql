-- Staging columns plus their decoded custom-field labels. Drives from staging
-- and LEFT JOINs the pivot: BigQuery UNPIVOT drops entities whose unpivoted
-- columns are all null, so the pivot alone is not a complete entity spine.
select s.*, p.fefp_label, p.dual_enrollment_indicator_label,
from {{ ref("stg_focus__master_courses") }} as s
left join
    {{ ref("int_focus__master_courses__pivot") }} as p on s.course_id = p.course_id
