with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_deanslist", "stg_deanslist__behavior"),
                    source("kippcamden_deanslist", "stg_deanslist__behavior"),
                    source("kippmiami_deanslist", "stg_deanslist__behavior"),
                ]
            )
        }}
    )

select
    *,

    {{
        date_to_fiscal_year(
            date_field="behavior_date", start_month=7, year_source="start"
        )
    }} as academic_year,
from union_relations
