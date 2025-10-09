select
    _id as measurement_id,
    district,
    `name`,
    `description`,
    rowstyle as row_style,
    scalemax as scale_max,
    scalemin as scale_min,

    cast(created as timestamp) as created,
    cast(lastmodified as timestamp) as last_modified,
    cast(archivedat as timestamp) as archived_at,
from {{ source("schoolmint_grow", "src_schoolmint_grow__measurements") }}
where _dagster_partition_key = 'f'
