with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_deanslist", model.name),
                    source("kippcamden_deanslist", model.name),
                    source("kippmiami_deanslist", model.name),
                ]
            )
        }}
    )

select
    *,

    {{
        date_to_fiscal_year(
            date_field="create_ts_date", start_month=7, year_source="start"
        )
    }} as create_ts_academic_year,
from union_relations
