select
    id,
    source_class,
    source_id,
    code,
    label,
    min_syear,
    max_syear,
    inactive,
    migrated,
    district_id,
    parent_student_label,
    created_at,
    updated_at,

    cast(sort_order as numeric) as sort_order,
from {{ source("focus", "custom_field_select_options") }}
where deleted is null
