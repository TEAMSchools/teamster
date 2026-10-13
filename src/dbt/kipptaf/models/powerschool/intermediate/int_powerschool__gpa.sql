with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "int_powerschool__gpa"),
                    source("kippcamden_powerschool", "int_powerschool__gpa"),
                    source("kippmiami_powerschool", "int_powerschool__gpa"),
                    source("kipppaterson_powerschool", "int_powerschool__gpa"),
                ]
            )
        }}
    )

select ur.*, {{ extract_source_project("ur") }} as _dbt_source_project,
from union_relations as ur
