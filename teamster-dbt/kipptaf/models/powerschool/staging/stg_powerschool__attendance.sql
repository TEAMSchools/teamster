{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__attendance"),
            source("kippcamden_powerschool", "stg_powerschool__attendance"),
            source("kippmiami_powerschool", "stg_powerschool__attendance"),
        ]
    )
}}
