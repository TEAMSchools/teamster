{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__users"),
            source("kippcamden_powerschool", "stg_powerschool__users"),
            source("kippmiami_powerschool", "stg_powerschool__users"),
        ]
    )
}}
