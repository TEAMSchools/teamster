{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__codeset"),
            source("kippcamden_powerschool", "stg_powerschool__codeset"),
            source("kippmiami_powerschool", "stg_powerschool__codeset"),
        ]
    )
}}
