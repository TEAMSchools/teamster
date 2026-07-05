select
    id,
    source_class,
    source_id,
    code,
    label,
    sort_order,
    min_syear,
    max_syear,
    inactive,
    migrated,
    district_id,
    parent_student_label,
    created_at,
    updated_at,
from {{ source("focus", "custom_field_select_options") }}
where deleted is null
