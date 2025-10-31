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
    lg.*,

    g.name as logtype_name,

    {{
        date_to_fiscal_year(
            date_field="lg.entry_date", start_month=7, year_source="start"
        )
    }} as academic_year,
from union_relations as lg
left join
    {{ ref("stg_powerschool__gen") }} as g on lg.logtypeid = g.id and g.cat = 'logtype'
