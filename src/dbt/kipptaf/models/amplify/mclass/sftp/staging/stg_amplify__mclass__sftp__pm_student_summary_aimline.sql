with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_amplify",
                        "stg_amplify__mclass__sftp__pm_student_summary_aimline",
                    ),
                    source(
                        "kipppaterson_amplify",
                        "stg_amplify__mclass__sftp__pm_student_summary_aimline",
                    ),
                ]
            )
        }}
    )

select *
from union_relations
