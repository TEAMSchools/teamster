with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnj_iready", "stg_iready__diagnostic_results"),
                    source("kippmiami_iready", "stg_iready__diagnostic_results"),
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
