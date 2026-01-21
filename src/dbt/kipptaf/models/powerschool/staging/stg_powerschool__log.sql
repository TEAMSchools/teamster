with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "stg_powerschool__log"),
                    source("kippcamden_powerschool", "stg_powerschool__log"),
                    source("kippmiami_powerschool", "stg_powerschool__log"),
                ]
            )
        }}
    )

select
    *,

    {{
        date_to_fiscal_year(
            date_field="entry_date", start_month=7, year_source="start"
        )
    }} as academic_year,
from union_relations
