with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool",
                        "base_powerschool__course_enrollments",
                    ),
                    source(
                        "kippcamden_powerschool",
                        "base_powerschool__course_enrollments",
                    ),
                    source(
                        "kippmiami_powerschool",
                        "base_powerschool__course_enrollments",
                    ),
                    source(
                        "kipppaterson_powerschool",
                        "base_powerschool__course_enrollments",
                    ),
                ]
            )
        }}
    )

select *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations
