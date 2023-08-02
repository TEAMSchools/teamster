{%- set src_question = source("alchemer", "src_alchemer__survey_question") -%}

with
    parse_partition_key as (
        select
            *,
            safe_cast(
                regexp_extract(
                    safe_cast(_dagster_partition_key as string), r'\d+', 1, 1
                ) as int
            ) as survey_id,
        from {{ src_question }}
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
    nullif(shortname, '') as shortname,
    {{
        dbt_utils.star(
            from=src_question, except=["_dagster_partition_key", "shortname"]
        )
    }},
from deduplicate
