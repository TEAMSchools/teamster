with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_deanslist", "int_deanslist__incidents__penalties"
                    ),
                    source(
                        "kippcamden_deanslist", "int_deanslist__incidents__penalties"
                    ),
                    source(
                        "kippmiami_deanslist", "int_deanslist__incidents__penalties"
                    ),
                    source(
                        "kipppaterson_deanslist",
                        "int_deanslist__incidents__penalties",
                    ),
                ]
            )
        }}
    )

select ur.*, {{ extract_source_project("ur") }} as _dbt_source_project,
from union_relations as ur
