with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool", "int_powerschool__attendance_streak"
                    ),
                    source(
                        "kippcamden_powerschool", "int_powerschool__attendance_streak"
                    ),
                    source(
                        "kippmiami_powerschool", "int_powerschool__attendance_streak"
                    ),
                    source(
                        "kipppaterson_powerschool",
                        "int_powerschool__attendance_streak",
                    ),
                ]
            )
        }}
    )

select ur.*, {{ extract_code_location("ur") }} as _dbt_source_project,
from union_relations as ur
