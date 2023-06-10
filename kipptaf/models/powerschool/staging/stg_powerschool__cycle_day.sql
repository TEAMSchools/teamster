{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__cycle_day"),
            source("kippcamden_powerschool", "stg_powerschool__cycle_day"),
            source("kippmiami_powerschool", "stg_powerschool__cycle_day"),
        ]
    )
}}
