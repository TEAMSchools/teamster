{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "int_powerschool__attendance_streak"),
            source("kippcamden_powerschool", "int_powerschool__attendance_streak"),
            source("kippmiami_powerschool", "int_powerschool__attendance_streak"),
            source("kipppaterson_powerschool", "int_powerschool__attendance_streak"),
        ]
    )
}}
