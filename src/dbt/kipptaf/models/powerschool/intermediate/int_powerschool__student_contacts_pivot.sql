{{
    dbt_utils.union_relations(
        relations=[
            source(
                "kippnewark_powerschool", "int_powerschool__student_contacts_pivot"
            ),
            source(
                "kippcamden_powerschool", "int_powerschool__student_contacts_pivot"
            ),
            source(
                "kippmiami_powerschool", "int_powerschool__student_contacts_pivot"
            ),
        ]
    )
}}
