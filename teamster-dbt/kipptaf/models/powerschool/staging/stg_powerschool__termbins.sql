{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__termbins"),
            source("kippcamden_powerschool", "stg_powerschool__termbins"),
            source("kippmiami_powerschool", "stg_powerschool__termbins"),
        ]
    )
}}
