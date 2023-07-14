{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "int_powerschool__ps_attendance_daily"),
            source("kippcamden_powerschool", "int_powerschool__ps_attendance_daily"),
            source("kippmiami_powerschool", "int_powerschool__ps_attendance_daily"),
        ]
    )
}}
