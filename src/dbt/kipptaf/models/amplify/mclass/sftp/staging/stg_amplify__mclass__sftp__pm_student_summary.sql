with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_amplify",
                        "stg_amplify__mclass__sftp__pm_student_summary",
                    ),
                    source(
                        "kipppaterson_amplify",
                        "stg_amplify__mclass__sftp__pm_student_summary",
                    ),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select * except (device_date), coalesce(device_date, sync_date) as device_date,
from union_relations
