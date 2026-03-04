with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "stg_powerschool__users"),
                    source("kippcamden_powerschool", "stg_powerschool__users"),
                    source("kippmiami_powerschool", "stg_powerschool__users"),
                    source("kipppaterson_powerschool", "stg_powerschool__users"),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select *, regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as dagster_code_location,
from union_relations
