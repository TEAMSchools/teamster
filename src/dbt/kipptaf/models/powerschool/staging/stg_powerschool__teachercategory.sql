{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__teachercategory"),
            source("kippcamden_powerschool", "stg_powerschool__teachercategory"),
            source("kippmiami_powerschool", "stg_powerschool__teachercategory"),
        ]
    )
}}
