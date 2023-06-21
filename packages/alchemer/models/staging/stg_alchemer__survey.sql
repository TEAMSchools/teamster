{{ config(schema="alchemer") }}

{%- set source_model_ref = source("alchemer", model.name | replace("stg", "src")) -%}

{{ alchemer.dedupe_source_model(model_ref=source_model_ref) }}

select
    safe_cast(id as int) as id,
    safe_cast(
        created_on
        as timestamp format 'YYYY-MM-DD HH24:MI:SS' at time zone 'America/New_York'
    ) as created_on,
    safe_cast(
        modified_on
        as timestamp format 'YYYY-MM-DD HH24:MI:SS' at time zone 'America/New_York'
    ) as modified_on,

    {{
        dbt_utils.star(
            from=source_model_ref,
            except=["_dagster_partition_key", "id", "created_on", "modified_on"],
        )
    }}
from deduplicate
