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

-- trunk-ignore(sqlfluff/AM04)
select
    * except (
        enrollment_teacher_staff_id_teachernumber,
        official_teacher_staff_id,
        enrollment_teacher_name,
        official_teacher_name,
        device_date,
        client_date
    ),

    coalesce(
        enrollment_teacher_staff_id_teachernumber, official_teacher_staff_id
    ) as official_teacher_staff_id,
    coalesce(enrollment_teacher_name, official_teacher_name) as official_teacher_name,
    coalesce(device_date, client_date) as client_date,

from union_relations
