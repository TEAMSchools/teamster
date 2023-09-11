{%- set source_model_ref = source("alchemer", model.name | replace("stg", "src")) -%}

with
    parse_partition_key as (
        select
            *,
            safe_cast(
                regexp_extract(
                    safe_cast(_dagster_partition_key as string), r'\d+', 1, 1
                ) as int
            ) as survey_id
        from {{ source_model_ref }}
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
    safe_cast(id as int) as id,
    safe_cast(
        created_on
        as timestamp format 'YYYY-MM-DD HH24:MI:SS' at time zone '{{ var("local_timezone") }}'
    ) as created_on,
    safe_cast(
        modified_on
        as timestamp format 'YYYY-MM-DD HH24:MI:SS' at time zone '{{ var("local_timezone") }}'
    ) as modified_on,
    {{
        dbt_utils.star(
            from=source_model_ref,
            except=["_dagster_partition_key", "id", "created_on", "modified_on"],
        )
    }},
from deduplicate
