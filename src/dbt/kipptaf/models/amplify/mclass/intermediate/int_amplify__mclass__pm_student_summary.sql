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
        client_date,
        account_name,
        district_name,
        schoolid,
        school_primary_id,
        student_primary_id,
        student_primary_id_studentnumber,
        student_id_state_id,
        secondary_student_id_stateid,
        primary_school_id
    ),

    coalesce(
        enrollment_teacher_staff_id_teachernumber, official_teacher_staff_id
    ) as official_teacher_staff_id,
    coalesce(enrollment_teacher_name, official_teacher_name) as official_teacher_name,
    coalesce(device_date, client_date) as client_date,
    coalesce(account_name, district_name) as district_name,
    coalesce(schoolid, school_primary_id) as school_primary_id,
    coalesce(
        student_primary_id, student_primary_id_studentnumber
    ) as student_primary_id,
    coalesce(student_id_state_id, secondary_student_id_stateid) as student_id_state_id,

from union_relations
