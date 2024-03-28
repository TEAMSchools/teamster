with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", model.name),
                    source("kippcamden_powerschool", model.name),
                    source("kippmiami_powerschool", model.name),
                ]
            )
        }}
    )

select
    *,
    {{
        teamster_utils.date_to_fiscal_year(
            date_field="att_date", start_month=7, year_source="start"
        )
    }} as academic_year,
from union_relations
