select
    home_work_location_powerschool_school_id as school_id,
    powerschool_teacher_number as teacher_id,
    powerschool_teacher_number as teacher_number,
    employee_number as state_teacher_id,
    user_principal_name as teacher_email,
    given_name as first_name,

    null as middle_name,

    family_name_1 as last_name,
    job_title as title,
    sam_account_name as username,

    null as `password`,
from {{ ref("int_people__staff_roster") }}
where
    uac_account_disable = 0
    and not is_prestart
    and employee_number is not null
    and home_work_location_powerschool_school_id is not null
