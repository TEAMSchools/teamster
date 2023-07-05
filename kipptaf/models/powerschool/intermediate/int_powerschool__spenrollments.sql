{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "int_powerschool__spenrollments"),
            source("kippcamden_powerschool", "int_powerschool__spenrollments"),
            source("kippmiami_powerschool", "int_powerschool__spenrollments"),
        ]
    )
}}
