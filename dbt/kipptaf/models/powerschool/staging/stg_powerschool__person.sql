{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__person"),
            source("kippcamden_powerschool", "stg_powerschool__person"),
            source("kippmiami_powerschool", "stg_powerschool__person"),
        ]
    )
}}
