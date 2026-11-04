with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_deanslist", "stg_deanslist__users"),
                    source("kippcamden_deanslist", "stg_deanslist__users"),
                    source("kippmiami_deanslist", "stg_deanslist__users"),
                    source("kipppaterson_deanslist", "stg_deanslist__users"),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select *, {{ extract_source_project() }} as _dbt_source_project,
from union_relations
