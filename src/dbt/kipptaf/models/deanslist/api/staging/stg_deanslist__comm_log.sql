with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_deanslist", "stg_deanslist__comm_log"),
                    source("kippcamden_deanslist", "stg_deanslist__comm_log"),
                    source("kippmiami_deanslist", "stg_deanslist__comm_log"),
                ]
            )
        }}
    )

select
    *,

    cast(call_date_time as date) as call_date_time_date,

    {{
        date_to_fiscal_year(
            date_field="call_date_time", start_month=7, year_source="start"
        )
    }} as academic_year,
from union_relations
