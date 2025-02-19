select
    performance_band_id,
    performance_band_set_id,
    color,
    is_mastery,
    label,
    label_number,
    minimum_value,
from {{ source("illuminate", "performance_bands") }}
where not _fivetran_deleted
