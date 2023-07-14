{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__bell_schedule"),
            source("kippcamden_powerschool", "stg_powerschool__bell_schedule"),
            source("kippmiami_powerschool", "stg_powerschool__bell_schedule"),
        ]
    )
}}
