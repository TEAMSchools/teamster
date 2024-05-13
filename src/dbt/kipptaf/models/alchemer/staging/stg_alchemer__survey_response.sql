{%- set src_response = source("alchemer", "src_alchemer__survey_response") -%}

with
    parse_partition_key as (  -- noqa: ST03
        select
            id,
            session_id,
            contact_id,
            status,
            date_started,
            date_submitted,
            response_time,
            survey_data,
            _dagster_partition_key,

            regexp_extract(_dagster_partition_key, r'\d+', 1, 1) as survey_id,
        from {{ src_response }}
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="parse_partition_key",
                partition_by="survey_id, id",
                order_by="_dagster_partition_key desc",
            )
        }}
    ),

    transformed as (
        select
            session_id,
            status,
            response_time,
            survey_data,

            safe_cast(survey_id as int) as survey_id,
            safe_cast(id as int) as id,
            safe_cast(contact_id as int) as contact_id,

            concat(survey_id, '_', id) as surrogate_key,

            safe_cast(
                left(
                    date_started, length(date_started) - 4
                ) as timestamp format 'YYYY-MM-DD HH24:MI:SS'
                at time zone '{{ var("local_timezone") }}'
            ) as date_started,

            safe_cast(
                left(
                    date_submitted, length(date_submitted) - 4
                ) as timestamp format 'YYYY-MM-DD HH24:MI:SS'
                at time zone '{{ var("local_timezone") }}'
            ) as date_submitted,
            {{
                teamster_utils.date_to_fiscal_year(
                    date_field="timestamp(date_submitted)",
                    start_month=7,
                    year_source="start",
                )
            }} as academic_year,

        from deduplicate
    )

select *,
from transformed
where
    surrogate_key not in (
        select surrogate_key,
        from {{ ref("stg_alchemer__survey_response_disqualified") }}
    )
