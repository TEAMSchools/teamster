with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_deanslist", "stg_deanslist__users"),
                    source("kippcamden_deanslist", "stg_deanslist__users"),
                    source("kippmiami_deanslist", "stg_deanslist__users"),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select *, concat(first_name, ' ', last_name) as user_name,
from union_relations
