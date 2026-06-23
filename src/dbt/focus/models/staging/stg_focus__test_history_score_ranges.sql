select
    id,
    part_id,
    score_type_id,
    legacy,
    title,
    level,
    gradelevel,
    form,
    `min`,
    `max`,
    created_at,
    updated_at,
from {{ source("focus", "test_history_score_ranges") }}
