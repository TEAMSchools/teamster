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

    with_code_location as (
        select *, regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as code_location,  -- noqa: AM04, LT05
        from union_relations
    )

select
    *,
    case
        code_location when 'kippnewark' then 'NJSLA' when 'kippmiami' then 'FL'
    end as state_assessment_type,
from with_code_location
