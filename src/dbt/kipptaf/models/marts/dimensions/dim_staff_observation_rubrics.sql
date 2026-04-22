with
    -- trunk-ignore(sqlfluff/ST03): referenced by string in dbt_utils.deduplicate
    rubric_rows as (
        select
            rubric_id,
            `name`,
            scale_min,
            scale_max,
            is_private,
            is_published,
            archived_at,
            created,
            last_modified,
        from {{ ref("stg_schoolmint_grow__rubrics__measurement_groups__measurements") }}
        where measurement_group_id is not null
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="rubric_rows",
                partition_by="rubric_id",
                order_by="last_modified desc",
            )
        }}
    )

select
    {{ dbt_utils.generate_surrogate_key(["rubric_id"]) }}
    as staff_observation_rubric_key,

    `name`,
    scale_min,
    scale_max,
    is_private,
    is_published,

    archived_at as archived_timestamp,
    created as created_timestamp,
    last_modified as last_modified_timestamp,
from deduplicate
