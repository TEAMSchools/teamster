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

-- trunk-ignore(sqlfluff/AM04): union_relations produces dynamic columns
select *,
from union_relations
