{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__reenrollments"),
            source("kippcamden_powerschool", "stg_powerschool__reenrollments"),
            source("kippmiami_powerschool", "stg_powerschool__reenrollments"),
        ]
    )
}}
