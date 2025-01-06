with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "stg_powerschool__termbins"),
                    source("kippcamden_powerschool", "stg_powerschool__termbins"),
                    source("kippmiami_powerschool", "stg_powerschool__termbins"),
                ]
            )
        }}
    )

select
    *,

    if(
        current_date('{{ var("local_timezone") }}') between date1 and date2, true, false
    ) as is_current_term,

    if(
        current_date('{{ var("local_timezone") }}')
        between (date2 - 3) and (date1 + 14),
        true,
        false
    ) as is_quarter_end_date_range,

    case
        when storecode in ('Q1', 'Q2')
        then 'S1'
        when storecode in ('Q3', 'Q4')
        then 'S2'
    end as semester,
from union_relations
