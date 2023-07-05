{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "int_powerschool__person_contacts"),
            source("kippcamden_powerschool", "int_powerschool__person_contacts"),
            source("kippmiami_powerschool", "int_powerschool__person_contacts"),
        ]
    )
}}
