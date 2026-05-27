with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[source("kippmiami_fldoe", model.name)]
            )
        }}
    )

select
    *,

    {{ extract_code_location("union_relations") }} as _dbt_source_project,

    cast(assessment_grade as int) as grade_level,
from union_relations
