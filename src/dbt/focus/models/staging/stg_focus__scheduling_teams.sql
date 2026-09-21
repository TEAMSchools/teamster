select
    id,
    syear,
    school_id,
    grade_id,
    title,
    short_name,
    rollover_id,
    include_in_optimize,
    created_at,
    updated_at,

    cast(sort_order as numeric) as sort_order,
from {{ source("focus", "scheduling_teams") }}
