{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__personaddressassoc"),
            source("kippcamden_powerschool", "stg_powerschool__personaddressassoc"),
            source("kippmiami_powerschool", "stg_powerschool__personaddressassoc"),
        ]
    )
}}
