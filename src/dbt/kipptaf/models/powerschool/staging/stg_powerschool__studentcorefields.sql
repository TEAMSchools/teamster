{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__studentcorefields"),
            source("kippcamden_powerschool", "stg_powerschool__studentcorefields"),
            source("kippmiami_powerschool", "stg_powerschool__studentcorefields"),
            source("kipppaterson_powerschool", "stg_powerschool__studentcorefields"),
        ]
    )
}}
