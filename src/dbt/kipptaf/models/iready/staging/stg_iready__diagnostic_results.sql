with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnj_iready", model.name),
                    source("kippmiami_iready", model.name),
                ]
            )
        }}
    ),

-- trunk-ignore(sqlfluff/AM04)
select
    *,

    case
        when _dbt_source_relation like '%kippnewark%'
        then 'NJSLA'
        when _dbt_source_relation like '%kippmiami%'
        then 'FL'
    end as state_assessment_type,
from union_relations
