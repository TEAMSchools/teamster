{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "int_powerschool__student_contacts"),
            source("kippcamden_powerschool", "int_powerschool__student_contacts"),
            source("kippmiami_powerschool", "int_powerschool__student_contacts"),
            source("kipppaterson_powerschool", "int_powerschool__student_contacts"),
        ]
    )
}}
