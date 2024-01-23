select
    _dagster_partition_date as last_modified,
    _id as `observation_id`,
    score as `score`,

    observationscores as `observation_scores`,

    rubric.name as `rubric_name`,

    safe_cast(created as timestamp) as `created`,
    safe_cast(observedat as timestamp) as `observed_at`,
    safe_cast(firstpublished as timestamp) as `first_published`,
    safe_cast(lastpublished as timestamp) as `last_published`,
from {{ source("schoolmint_grow", "src_schoolmint_grow__observations") }}
where _dagster_partition_archived = 'f'
