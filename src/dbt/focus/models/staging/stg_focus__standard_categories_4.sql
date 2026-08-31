select
    id,
    parent_id,
    syear,
    school_id,
    district_id,
    title,
    short_name,
    rollover_id,
    cte_import,
    cpalms,
    guid,
    created_at,
    updated_at,

    cast(sort_order as numeric) as sort_order,
from {{ source("focus", "standard_categories_4") }}
