{{- config(enabled=false) -}}

with
    -- trunk-ignore(sqlfluff/ST03)
    observations as (
        select
            _id as observation_id,
            score,

            observationscores as observation_scores,

            rubric.name as rubric_name,

            timestamp(lastmodified) as last_modified_timestamp,
            date(timestamp(lastmodified), 'America/New_York') as last_modified_date,
        from {{ source("schoolmint_grow", "src_schoolmint_grow__observations") }}
        where _dagster_partition_archived = 'f'
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="observations",
                partition_by="observation_id, last_modified_date",
                order_by="last_modified_timestamp desc",
            )
        }}
    )

select
    observation_id,
    rubric_name,
    last_modified_date,
    score,
    observation_scores,

    lead(date_sub(last_modified_date, interval 1 day), 1, date('9999-12-31')) over (
        partition by observation_id order by last_modified_date asc
    ) as last_modified_date_lead,
from deduplicate
