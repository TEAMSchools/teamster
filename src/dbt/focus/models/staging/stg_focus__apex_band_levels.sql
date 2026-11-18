select
    id,
    band_set_id,
    label,
    color,
    created_at,
    updated_at,

    cast(min_score as numeric) as min_score,
    cast(max_score as numeric) as max_score,
from {{ source("focus", "apex_band_levels") }}
where deleted is not true
