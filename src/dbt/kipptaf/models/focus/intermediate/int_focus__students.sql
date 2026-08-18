-- The package model gained homeless_code, is_homeless,
-- homeless_primary_nighttime_residence_code and lunchstatus (#4868). This
-- comment forces state:modified so CI rebuilds the wrapper against the widened
-- staging copy instead of deferring to the narrower Staging environment.
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippmiami_focus", "int_focus__students"),
                ]
            )
        }}
    )

select *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations
