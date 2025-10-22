with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnj_iready", "stg_iready__instructional_usage_data"),
                    source(
                        "kippmiami_iready", "stg_iready__instructional_usage_data"
                    ),
                ]
            )
        }}
    ),

    crosswalk as (
        select
            ur.* except (_dbt_source_relation),

            regexp_replace(
                ur._dbt_source_relation, r'kipp[a-z]+_', lc.dagster_code_location || '_'
            ) as _dbt_source_relation,
        from union_relations as ur
        left join
            {{ ref("stg_google_sheets__people__location_crosswalk") }} as lc
            on ur.school = lc.name
    )

select
    *,

    {{
        dbt_utils.generate_surrogate_key(
            ["student_id", "subject", "last_week_start_date", "_dbt_source_relation"]
        )
    }} as surrogate_key,
from crosswalk
