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

-- the package staging model applies this same fallback; it is repeated here so
-- the union never reads a raw district table during the window between a
-- kipptaf deploy and the districts' next materialization
-- trunk-ignore(sqlfluff/AM04)
select * except (device_date), coalesce(device_date, sync_date) as device_date,
from union_relations
