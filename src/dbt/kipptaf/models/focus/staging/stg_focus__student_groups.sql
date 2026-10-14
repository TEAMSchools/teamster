with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[source("kippmiami_focus", "stg_focus__student_groups")]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select *, regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,
from union_relations
