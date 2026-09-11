with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool",
                        "int_powerschool__section_teachers",
                    ),
                    source(
                        "kippcamden_powerschool",
                        "int_powerschool__section_teachers",
                    ),
                    source(
                        "kipppaterson_powerschool",
                        "int_powerschool__section_teachers",
                    ),
                ]
            )
        }}
    )

select *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations
