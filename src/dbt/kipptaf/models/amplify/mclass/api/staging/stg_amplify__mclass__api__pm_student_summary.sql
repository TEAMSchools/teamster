select
    * except (
        account_name,
        client_date,
        district_name,
        official_teacher_name,
        official_teacher_staff_id,
        student_id_state_id,
        student_primary_id,
        surrogate_key
    ),

    client_date as device_date,
    official_teacher_name as enrollment_teacher_name,
    official_teacher_staff_id as enrollment_teacher_staff_id_teachernumber,
    student_id_state_id as secondary_student_id_stateid,
    student_primary_id as student_primary_id_studentnumber,

    coalesce(account_name, district_name) as district_name,
from {{ source("amplify", "stg_amplify__mclass__api__pm_student_summary") }}
