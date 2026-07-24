with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippmiami_focus", "stg_focus__attendance_calendars"),
                ]
            )
        }}
    )

select *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations
