with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[source("kippmiami_fldoe", "int_fldoe__fte_pivot")]
            )
        }}
    )

select ur.*, {{ extract_source_project("ur") }} as _dbt_source_project,
from union_relations as ur
