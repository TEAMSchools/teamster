{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__calendar_day"),
            source("kippcamden_powerschool", "stg_powerschool__calendar_day"),
            source("kippmiami_powerschool", "stg_powerschool__calendar_day"),
            source("kipppaterson_powerschool", "stg_powerschool__calendar_day"),
        ]
    )
}}
