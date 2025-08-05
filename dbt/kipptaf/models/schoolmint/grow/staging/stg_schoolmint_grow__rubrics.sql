select
    _id as rubric_id,
    `name`,
    district,
    scalemin as scale_min,
    scalemax as scale_max,
    isprivate as is_private,
    ispublished as is_published,
    `order`,

    /* records */
    settings,
    layout,

    /* repeated records*/
    measurementgroups as measurement_groups,

    timestamp(archivedat) as archived_at,
    timestamp(created) as created,
    timestamp(lastmodified) as last_modified,
from {{ source("schoolmint_grow", "src_schoolmint_grow__rubrics") }}
where _dagster_partition_key = 'f'
