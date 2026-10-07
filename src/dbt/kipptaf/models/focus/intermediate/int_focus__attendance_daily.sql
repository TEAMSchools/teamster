with
    -- One row per student per in-session day. The district roster trims
    -- overlapping stints before the scaffold crosses them with the calendar,
    -- so a student never appears twice on a day here.
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippmiami_focus", "int_focus__attendance_daily"),
                ]
            )
        }}
    )

select *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations
