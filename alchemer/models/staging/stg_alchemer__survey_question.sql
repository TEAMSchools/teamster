{{ config(schema="alchemer") }}

{%- set source_model_ref = source("alchemer", model.name | replace("stg", "src")) -%}

{{ alchemer.dedupe_source_model(model_ref=source_model_ref) }}

select
    nullif(shortname, '') as shortname,

    survey_id,
    {{
        dbt_utils.star(
            from=source_model_ref,
            except=[
                "_dagster_partition_key",
                "shortname",
            ],
        )
    }}
from deduplicate
