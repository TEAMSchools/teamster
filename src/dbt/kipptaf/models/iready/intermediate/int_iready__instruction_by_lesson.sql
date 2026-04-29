with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnj_iready", "stg_iready__instruction_by_lesson"),
                    source("kippmiami_iready", "stg_iready__instruction_by_lesson"),
                ]
            )
        }}
    )

select
    ur.* except (_dbt_source_relation),

    regexp_replace(
        ur._dbt_source_relation,
        r'kipp[a-z]+_',
        lc.location_dagster_code_location || '_'
    ) as _dbt_source_relation,
from union_relations as ur
left join
    {{ ref("int_people__location_crosswalk") }} as lc on ur.school = lc.location_name
