with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool",
                        "int_powerschool__category_grades_pivot",
                    ),
                    source(
                        "kippcamden_powerschool",
                        "int_powerschool__category_grades_pivot",
                    ),
                    source(
                        "kippmiami_powerschool",
                        "int_powerschool__category_grades_pivot",
                    ),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select *, {{ extract_source_project() }} as _dbt_source_project,
from union_relations
