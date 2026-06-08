with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", model.name),
                    source("kippcamden_powerschool", model.name),
                    source("kippmiami_powerschool", model.name),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    ur.*, regexp_extract(ur._dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,
from union_relations as ur
