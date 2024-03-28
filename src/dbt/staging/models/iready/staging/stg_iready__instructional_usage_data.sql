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
    )

select
    *,
    {{
        dbt_utils.generate_surrogate_key(
            ["student_id", "subject", "last_week_start_date", "_dbt_source_relation"]
        )
    }} as surrogate_key,
from union_relations
