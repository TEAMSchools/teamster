with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_pearson", "stg_pearson__student_list_report"),
                    source("kippcamden_pearson", "stg_pearson__student_list_report"),
                    source(
                        "kipppaterson_pearson", "stg_pearson__student_list_report"
                    ),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select *, {{ extract_source_project() }} as _dbt_source_project,
from union_relations
