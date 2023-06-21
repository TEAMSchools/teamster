{%- macro dedupe_source_model(model_ref) -%}
    with
        using_clause as (
            select
                *,
                safe_cast(
                    regexp_extract(
                        safe_cast(_dagster_partition_key as string), r'\d+', 1, 1
                    ) as int
                ) as survey_id
            from {{ model_ref }}
        ),

        deduplicate as (
            {{
                dbt_utils.deduplicate(
                    relation="using_clause",
                    partition_by="survey_id, id",
                    order_by="_dagster_partition_key desc",
                )
            }}
        )
{%- endmacro -%}
