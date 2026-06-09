with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "int_powerschool__terms"),
                    source("kippcamden_powerschool", "int_powerschool__terms"),
                    source("kippmiami_powerschool", "int_powerschool__terms"),
                    source("kipppaterson_powerschool", "int_powerschool__terms"),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select *, regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,
from union_relations
