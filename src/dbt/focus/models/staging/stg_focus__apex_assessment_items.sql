select
    id,
    assessment_id,
    item_id,
    section_id,
    sort_order,
    conditions_json,
    created_at,
    updated_at,

    cast(points as numeric) as points,
from {{ source("focus", "apex_assessment_items") }}
