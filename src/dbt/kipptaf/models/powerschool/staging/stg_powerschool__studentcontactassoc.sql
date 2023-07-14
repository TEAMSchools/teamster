{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__studentcontactassoc"),
            source("kippcamden_powerschool", "stg_powerschool__studentcontactassoc"),
            source("kippmiami_powerschool", "stg_powerschool__studentcontactassoc"),
        ]
    )
}}
