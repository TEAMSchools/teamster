with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_pearson", "stg_pearson__njsla"),
                    source("kippcamden_pearson", "stg_pearson__njsla"),
                    source("kipppaterson_pearson", "int_pearson__njsla"),
                ]
            )
        }}
    )

select *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations
