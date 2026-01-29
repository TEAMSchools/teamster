with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippmiami_finalsite", "stg_finalsite__status_report"),
                    source("kippnewark_finalsite", "stg_finalsite__status_report"),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select *, initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,
from union_relations
