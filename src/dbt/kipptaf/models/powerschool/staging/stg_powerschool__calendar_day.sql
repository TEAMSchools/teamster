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
    ur.* except (date_value),

    {{ extract_source_project("ur") }} as _dbt_source_project,

    if(ur.date_value < date '2000-01-01', null, ur.date_value) as date_value,

from union_relations as ur
