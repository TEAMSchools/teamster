with
    union_relations as (
        {{
            dbt_utils.union_relations(
                source_column_name="_dbt_source_relation_2",
                relations=[
                    source("kippnewark_pearson", "int_pearson__all_assessments"),
                    source("kippcamden_pearson", "int_pearson__all_assessments"),
                    source("kipppaterson_pearson", "int_pearson__all_assessments"),
                ],
            )
        }}
    )

select
    * except (_dbt_source_relation_2),
    {{ extract_source_project() }} as _dbt_source_project,
from union_relations
