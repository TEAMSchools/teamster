with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "stg_powerschool__calendar_day"),
                    source("kippcamden_powerschool", "stg_powerschool__calendar_day"),
                    source("kippmiami_powerschool", "stg_powerschool__calendar_day"),
                    source(
                        "kipppaterson_powerschool", "stg_powerschool__calendar_day"
                    ),
                ]
            )
        }}
    )

select
    * except (date_value),

    if(date_value < date '2000-01-01', null, date_value) as date_value,
    regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,
from union_relations
