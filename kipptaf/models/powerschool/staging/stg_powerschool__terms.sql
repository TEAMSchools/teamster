{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__terms"),
            source("kippcamden_powerschool", "stg_powerschool__terms"),
            source("kippmiami_powerschool", "stg_powerschool__terms"),
        ]
    )
}}
