with
    source as (
        select * from {{ source("schoolmint_grow", "src_schoolmint_grow__rubrics") }}
    ),
    renamed as (
        select
            {{ adapter.quote("_id") }},
            {{ adapter.quote("name") }},
            {{ adapter.quote("district") }},
            {{ adapter.quote("created") }},
            {{ adapter.quote("lastModified") }},
            {{ adapter.quote("archivedAt") }},
            {{ adapter.quote("isPrivate") }},
            {{ adapter.quote("isPublished") }},
            {{ adapter.quote("order") }},
            {{ adapter.quote("scaleMax") }},
            {{ adapter.quote("scaleMin") }},
            {{ adapter.quote("settings") }},
            {{ adapter.quote("layout") }},
            {{ adapter.quote("measurementGroups") }},
            {{ adapter.quote("_dagster_partition_key") }}

        from source
    )
select *
from renamed
