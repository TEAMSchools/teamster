with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_deanslist", "int_deanslist__roster_assignments"
                    ),
                    source(
                        "kippcamden_deanslist", "int_deanslist__roster_assignments"
                    ),
                    source(
                        "kippmiami_deanslist", "int_deanslist__roster_assignments"
                    ),
                    source(
                        "kipppaterson_deanslist", "int_deanslist__roster_assignments"
                    ),
                ]
            )
        }}
    )

select ur.*, {{ extract_code_location("ur") }} as _dbt_source_project,
from union_relations as ur
