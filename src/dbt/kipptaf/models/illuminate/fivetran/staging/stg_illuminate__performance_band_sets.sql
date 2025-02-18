select
    performance_band_set_id,
    description,
    district_default,
    hidden,
    user_id,
    created_at,
    updated_at,
    deleted_at,
from {{ source("illuminate", "performance_band_sets") }}
where not _fivetran_deleted and deleted_at is null
