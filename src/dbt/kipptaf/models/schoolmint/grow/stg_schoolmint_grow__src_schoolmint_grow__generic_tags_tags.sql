with
    source as (
        select *,
        from {{ source("schoolmint_grow", "src_schoolmint_grow__generic_tags_tags") }}
    ),

    renamed as (
        select
            {{ adapter.quote("archivedAt") }},
            {{ adapter.quote("created") }},
            {{ adapter.quote("lastModified") }},
            {{ adapter.quote("name") }},
            {{ adapter.quote("_id") }},
            {{ adapter.quote("url") }},
            {{ adapter.quote("order") }},
            {{ adapter.quote("creator") }},
            {{ adapter.quote("district") }},
            {{ adapter.quote("abbreviation") }},
            {{ adapter.quote("parent") }},
            {{ adapter.quote("color") }},
            {{ adapter.quote("showOnDash") }},
            {{ adapter.quote("__v") }},
            {{ adapter.quote("parents") }},
            {{ adapter.quote("rows") }},
            {{ adapter.quote("tags") }},
            {{ adapter.quote("type") }},
            {{ adapter.quote("_dagster_partition_key") }}

        from source
    )

select *,
from renamed
