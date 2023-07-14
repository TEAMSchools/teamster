{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "int_powerschool__ps_enrollment_all"),
            source("kippcamden_powerschool", "int_powerschool__ps_enrollment_all"),
            source("kippmiami_powerschool", "int_powerschool__ps_enrollment_all"),
        ]
    )
}}
