{%- set src_response = source("alchemer", "src_alchemer__survey_response") -%}

with
    parse_partition_key as (
        select
            *,
            safe_cast(
                regexp_extract(
                    safe_cast(_dagster_partition_key as string), r'\d+', 1, 1
                ) as int
            ) as survey_id,
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
    )

select
    survey_id,
    safe_cast(id as int) as id,
    safe_cast(link_id as int) as link_id,
    safe_cast(contact_id as int) as contact_id,
    safe_cast(
        left(date_started, length(date_started) - 4)
        as timestamp format 'YYYY-MM-DD HH24:MI:SS' at time zone '{{ var("local_timezone") }}'
    ) as date_started,
    safe_cast(
        left(date_submitted, length(date_submitted) - 4)
        as timestamp format 'YYYY-MM-DD HH24:MI:SS' at time zone '{{ var("local_timezone") }}'
    ) as date_submitted,

    {{
        dbt_utils.star(
            from=src_response,
            except=[
                "_dagster_partition_key",
                "id",
                "link_id",
                "contact_id",
                "date_started",
                "date_submitted",
            ],
        )
    }},
from deduplicate
