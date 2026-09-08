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
    ),

    -- Miami's student_number is the 8400-prefixed Focus id since #5148 and the
    -- frozen archive carries the bare PowerSchool number. Renumbered here, where
    -- the archive first enters kipptaf, so every consumer reads one id space.
    unioned as (
        select ur.*, {{ extract_source_project("ur") }} as _dbt_source_project,
        from union_relations as ur
    )

select
    * except (student_number),

    {{ focus_student_number("student_number", "yearid + 1990", "_dbt_source_project") }}
    as student_number,
from unioned
