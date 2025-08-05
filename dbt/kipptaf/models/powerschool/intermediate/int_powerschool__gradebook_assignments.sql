{{
    dbt_utils.union_relations(
        relations=[
            source(
                "kippnewark_powerschool", "int_powerschool__gradebook_assignments"
            ),
            source(
                "kippcamden_powerschool", "int_powerschool__gradebook_assignments"
            ),
            source("kippmiami_powerschool", "int_powerschool__gradebook_assignments"),
        ]
    )
}}
