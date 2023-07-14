with
    source as (
        select * from {{ source("schoolmint_grow", "src_schoolmint_grow__informals") }}
    ),
    renamed as (
        select
            {{ adapter.quote("_id") }},
            {{ adapter.quote("name") }},
            {{ adapter.quote("district") }},
            {{ adapter.quote("created") }},
            {{ adapter.quote("lastModified") }},
            {{ adapter.quote("archivedAt") }},
            {{ adapter.quote("shared") }},
            {{ adapter.quote("private") }},
            {{ adapter.quote("tags") }},
            {{ adapter.quote("creator") }},
            {{ adapter.quote("user") }},
            {{ adapter.quote("_dagster_partition_key") }}

        from source
    )
select *
from renamed
