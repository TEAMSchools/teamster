with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippmiami_finalsite", "stg_finalsite__contacts"),
                ]
            )
        }}
    )

select *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations
