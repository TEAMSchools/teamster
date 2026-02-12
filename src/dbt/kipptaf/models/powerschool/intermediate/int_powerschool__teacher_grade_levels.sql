with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool",
                        "int_powerschool__teacher_grade_levels",
                    ),
                    source(
                        "kippcamden_powerschool",
                        "int_powerschool__teacher_grade_levels",
                    ),
                    source(
                        "kippmiami_powerschool",
                        "int_powerschool__teacher_grade_levels",
                    ),
                ]
            )
        }}
    )

select *, {{ extract_code_location("union_relations") }} as _dbt_source_project,
from union_relations
