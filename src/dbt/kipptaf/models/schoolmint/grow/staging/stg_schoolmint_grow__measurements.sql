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
    `name`,
    district,
    created,
    lastmodified as last_modified,
    archivedat as archived_at,
    `description`,
    rowstyle as row_style,
    scalemax as scale_max,
    scalemin as scale_min,
    textboxes as text_boxes,
    measurementoptions as measurement_options,

    regexp_extract(lower(`name`), r'(^.*?)\-') as `type`,
    regexp_extract(lower(`name`), r'(^.*?):') as short_name,
from deduplicate
