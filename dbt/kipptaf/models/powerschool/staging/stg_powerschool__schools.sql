{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__schools"),
            source("kippcamden_powerschool", "stg_powerschool__schools"),
            source("kippmiami_powerschool", "stg_powerschool__schools"),
        ]
    )
}}
