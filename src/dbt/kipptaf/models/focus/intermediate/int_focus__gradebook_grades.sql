-- passes through the package's assignment_course_period_id (int_focus,
-- #5010) so int_students__gradebook_assignments_scores no longer re-joins
-- stg_focus__gradebook_assignments_join_course_periods for it.
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippmiami_focus", "int_focus__gradebook_grades"),
                ]
            )
        }}
    )

select *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations
