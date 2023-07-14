{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__studentcontactdetail"),
            source("kippcamden_powerschool", "stg_powerschool__studentcontactdetail"),
            source("kippmiami_powerschool", "stg_powerschool__studentcontactdetail"),
        ]
    )
}}
