{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__sections"),
            source("kippcamden_powerschool", "stg_powerschool__sections"),
            source("kippmiami_powerschool", "stg_powerschool__sections"),
        ]
    )
}}
