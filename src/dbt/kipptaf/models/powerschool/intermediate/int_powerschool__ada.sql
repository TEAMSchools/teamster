with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "int_powerschool__ada"),
                    source("kippcamden_powerschool", "int_powerschool__ada"),
                    source("kippmiami_powerschool", "int_powerschool__ada"),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    *,

    yearid + 1990 as academic_year,

    regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,
from union_relations
