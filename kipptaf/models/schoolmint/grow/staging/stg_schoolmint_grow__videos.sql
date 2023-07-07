with
    source as (
        select * from {{ source("schoolmint_grow", "src_schoolmint_grow__videos") }}
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
            {{ adapter.quote("fileName") }},
            {{ adapter.quote("isCollaboration") }},
            {{ adapter.quote("key") }},
            {{ adapter.quote("parent") }},
            {{ adapter.quote("status") }},
            {{ adapter.quote("style") }},
            {{ adapter.quote("thumbnail") }},
            {{ adapter.quote("url") }},
            {{ adapter.quote("zencoderJobId") }},
            {{ adapter.quote("observations") }},
            {{ adapter.quote("comments") }},
            {{ adapter.quote("tags") }},
            {{ adapter.quote("editors") }},
            {{ adapter.quote("commenters") }},
            {{ adapter.quote("creator") }},
            {{ adapter.quote("videoNotes") }},
            {{ adapter.quote("users") }},
            {{ adapter.quote("_dagster_partition_key") }}

        from source
    )
select *
from renamed
