select
    id,
    part_id,
    score_type_id,
    legacy,
    title,
    level,
    gradelevel,
    form,
    created_at,
    updated_at,

    cast(`min` as numeric) as `min`,
    cast(`max` as numeric) as `max`,
from {{ source("focus", "test_history_score_ranges") }}
