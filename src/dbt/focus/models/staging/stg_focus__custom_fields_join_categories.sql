select
    id,
    field_id,
    category_id,
    sort_order,
    imported,
    field_class,
    district_id,
    created_at,
    updated_at,
from {{ source("focus", "custom_fields_join_categories") }}
where deleted is null
