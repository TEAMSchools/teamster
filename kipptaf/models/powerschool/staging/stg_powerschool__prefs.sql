{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__prefs"),
            source("kippcamden_powerschool", "stg_powerschool__prefs"),
            source("kippmiami_powerschool", "stg_powerschool__prefs"),
        ]
    )
}}
