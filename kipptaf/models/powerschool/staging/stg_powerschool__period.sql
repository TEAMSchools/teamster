{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__period"),
            source("kippcamden_powerschool", "stg_powerschool__period"),
            source("kippmiami_powerschool", "stg_powerschool__period"),
        ]
    )
}}
