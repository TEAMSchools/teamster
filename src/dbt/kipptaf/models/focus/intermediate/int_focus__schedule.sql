with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippmiami_focus", "int_focus__schedule"),
                ]
            )
        }}
    )

-- columns come from the package model's relation at compile time
-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations
