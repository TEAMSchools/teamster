with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "stg_powerschool__students"),
                    source("kippcamden_powerschool", "stg_powerschool__students"),
                    source("kippmiami_powerschool", "stg_powerschool__students"),
                    source("kipppaterson_powerschool", "stg_powerschool__students"),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04): union_relations produces an unknown column count
select *, regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,
from union_relations
where dcid >= 1
