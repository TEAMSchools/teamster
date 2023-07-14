{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__personaddress"),
            source("kippcamden_powerschool", "stg_powerschool__personaddress"),
            source("kippmiami_powerschool", "stg_powerschool__personaddress"),
        ]
    )
}}
