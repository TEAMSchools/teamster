select
    id,
    syear,
    school_id,
    grade_id,
    title,
    short_name,
    sort_order,
    rollover_id,
    include_in_optimize,
    created_at,
    updated_at,
from {{ source("focus", "scheduling_teams") }}
