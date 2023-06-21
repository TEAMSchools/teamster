{{ config(schema="alchemer") }}

{%- set source_model_ref = source("alchemer", model.name | replace("stg", "src")) -%}

{{ alchemer.dedupe_source_model(model_ref=source_model_ref) }},

campaign_clean as (
    select
        safe_cast(id as int) as id,
        safe_cast(invite_id as int) as invite_id,
        safe_cast(limit_responses as int) as limit_responses,
        safe_cast(`ssl` as boolean) as `ssl`,
        safe_cast(
            date_created
            as timestamp format 'YYYY-MM-DD HH24:MI:SS' at time zone 'America/New_York'
        ) as date_created,
        safe_cast(
            date_modified
            as timestamp format 'YYYY-MM-DD HH24:MI:SS' at time zone 'America/New_York'
        ) as date_modified,
        safe_cast(
            link_open_date
            as timestamp format 'YYYY-MM-DD HH24:MI:SS' at time zone 'America/New_York'
        ) as link_open_date,
        safe_cast(
            link_close_date
            as timestamp format 'YYYY-MM-DD HH24:MI:SS' at time zone 'America/New_York'
        ) as link_close_date,

        survey_id,
        {{
            dbt_utils.star(
                from=source_model_ref,
                except=[
                    "_dagster_partition_key",
                    "id",
                    "invite_id",
                    "limit_responses",
                    "ssl",
                    "date_created",
                    "date_modified",
                    "link_open_date",
                    "link_close_date",
                ],
            )
        }}
    from deduplicate
)

select
    *,
    {{
        teamster_utils.date_to_fiscal_year(
            date_field="link_open_date", start_month=7, year_source="end"
        )
    }} as fiscal_year
from campaign_clean
