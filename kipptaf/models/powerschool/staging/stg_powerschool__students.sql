{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__students"),
            source("kippcamden_powerschool", "stg_powerschool__students"),
            source("kippmiami_powerschool", "stg_powerschool__students"),
        ]
    )
}}
