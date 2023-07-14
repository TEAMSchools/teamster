with
    source as (
        select *
        from {{ source("schoolmint_grow", "src_schoolmint_grow__measurements") }}
    ),
    renamed as (
        select
            {{ adapter.quote("_id") }},
            {{ adapter.quote("name") }},
            {{ adapter.quote("district") }},
            {{ adapter.quote("created") }},
            {{ adapter.quote("lastModified") }},
            {{ adapter.quote("archivedAt") }},
            {{ adapter.quote("description") }},
            {{ adapter.quote("rowStyle") }},
            {{ adapter.quote("scaleMax") }},
            {{ adapter.quote("scaleMin") }},
            {{ adapter.quote("textBoxes") }},
            {{ adapter.quote("measurementOptions") }},
            {{ adapter.quote("_dagster_partition_key") }}

        from source
    )
select *
from renamed
