with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    ref("stg_amplify__pm_student_summary"),
                    ref("stg_amplify__mclass__sftp__pm_student_summary"),
                ]
            )
        }}
    )

select *,
from union_relations
