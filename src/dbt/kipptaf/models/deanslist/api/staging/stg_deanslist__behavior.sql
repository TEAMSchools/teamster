with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_deanslist", "stg_deanslist__behavior"),
                    source("kippcamden_deanslist", "stg_deanslist__behavior"),
                    source("kippmiami_deanslist", "stg_deanslist__behavior"),
                    source("kipppaterson_deanslist", "stg_deanslist__behavior"),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select *, {{ extract_source_project() }} as _dbt_source_project,
from union_relations
