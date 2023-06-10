{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__fte"),
            source("kippcamden_powerschool", "stg_powerschool__fte"),
            source("kippmiami_powerschool", "stg_powerschool__fte"),
        ]
    )
}}
