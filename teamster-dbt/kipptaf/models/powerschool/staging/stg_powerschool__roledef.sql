{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__roledef"),
            source("kippcamden_powerschool", "stg_powerschool__roledef"),
            source("kippmiami_powerschool", "stg_powerschool__roledef"),
        ]
    )
}}
