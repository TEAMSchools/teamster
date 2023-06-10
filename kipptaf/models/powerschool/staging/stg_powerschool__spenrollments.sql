{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__spenrollments"),
            source("kippcamden_powerschool", "stg_powerschool__spenrollments"),
            source("kippmiami_powerschool", "stg_powerschool__spenrollments"),
        ]
    )
}}
