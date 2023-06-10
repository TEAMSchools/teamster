{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__cc"),
            source("kippcamden_powerschool", "stg_powerschool__cc"),
            source("kippmiami_powerschool", "stg_powerschool__cc"),
        ]
    )
}}
