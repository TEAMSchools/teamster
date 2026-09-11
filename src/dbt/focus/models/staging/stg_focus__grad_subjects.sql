select
    id,
    title,
    short_name,
    rollover_id,
    request_group,
    ahs_subject,
    min_syear,
    max_syear,
    district_id,
    created_at,
    updated_at,

    cast(credits as numeric) as credits,
    cast(sort_order as numeric) as sort_order,
from {{ source("focus", "grad_subjects") }}
