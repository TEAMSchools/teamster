select
    performance_band_set_id,
    `description`,
    district_default,
    `hidden`,
    user_id,
    created_at,
    updated_at,
    deleted_at,
from {{ source("illuminate_dna_assessments", "performance_band_sets") }}
where deleted_at is null
