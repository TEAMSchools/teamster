with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool", "int_powerschool__category_grades"
                    ),
                    source(
                        "kippcamden_powerschool", "int_powerschool__category_grades"
                    ),
                    source(
                        "kippmiami_powerschool", "int_powerschool__category_grades"
                    ),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    *,

    regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,
    yearid + 1990 as academic_year,

from union_relations
