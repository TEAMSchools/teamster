{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__gradescaleitem"),
            source("kippcamden_powerschool", "stg_powerschool__gradescaleitem"),
            source("kippmiami_powerschool", "stg_powerschool__gradescaleitem"),
        ]
    )
}}
