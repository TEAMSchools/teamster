{{ config(schema="alchemer") }}

{%- set source_model_ref = source("alchemer", model.name | replace("stg", "src")) -%}

{{ alchemer.dedupe_source_model(model_ref=source_model_ref) }}

select
    safe_cast(id as int) as id,
    safe_cast(link_id as int) as link_id,
    safe_cast(contact_id as int) as contact_id,
    safe_cast(
        left(
            date_submitted, length(date_submitted) - 4
        ) as timestamp format 'YYYY-MM-DD HH24:MI:SS' at time zone 'America/New_York'
    ) as date_submitted,
    safe_cast(
        left(
            date_started, length(date_started) - 4
        ) as timestamp format 'YYYY-MM-DD HH24:MI:SS' at time zone 'America/New_York'
    ) as date_started,

    survey_id,
    {{
        dbt_utils.star(
            from=source_model_ref,
            except=[
                "_dagster_partition_key",
                "id",
                "link_id",
                "contact_id",
                "date_submitted",
                "date_started",
            ],
        )
    }}
from deduplicate
