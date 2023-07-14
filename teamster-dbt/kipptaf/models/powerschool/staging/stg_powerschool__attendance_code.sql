{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__attendance_code"),
            source("kippcamden_powerschool", "stg_powerschool__attendance_code"),
            source("kippmiami_powerschool", "stg_powerschool__attendance_code"),
        ]
    )
}}
