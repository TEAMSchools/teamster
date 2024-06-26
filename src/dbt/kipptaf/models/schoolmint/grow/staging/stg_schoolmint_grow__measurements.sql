with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source(
                    "schoolmint_grow", "src_schoolmint_grow__measurements"
                ),
                partition_by="_id",
                order_by="_file_name desc",
            )
        }}
    )

select
    _id as measurement_id,
    district,
    `name`,
    `description`,
    rowstyle as row_style,
    scalemax as scale_max,
    scalemin as scale_min,

    /* repeated records */
    textboxes as text_boxes,
    measurementoptions as measurement_options,

    timestamp(created) as created,
    timestamp(lastmodified) as last_modified,
    timestamp(archivedat) as archived_at,
from deduplicate
where _dagster_partition_key = 'f'
