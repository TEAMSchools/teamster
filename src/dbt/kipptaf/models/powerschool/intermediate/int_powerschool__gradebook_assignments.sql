with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool",
                        "int_powerschool__gradebook_assignments",
                    ),
                    source(
                        "kippcamden_powerschool",
                        "int_powerschool__gradebook_assignments",
                    ),
                    source(
                        "kippmiami_powerschool",
                        "int_powerschool__gradebook_assignments",
                    ),
                    source(
                        "kipppaterson_powerschool",
                        "int_powerschool__gradebook_assignments",
                    ),
                ]
            )
        }}
    )

select ur.*, {{ extract_source_project("ur") }} as _dbt_source_project,

from union_relations as ur
