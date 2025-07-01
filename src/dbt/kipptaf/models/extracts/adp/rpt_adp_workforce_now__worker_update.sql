select
    associate_oid,
    employee_number,
    custom_field__employee_number as adp__custom_field__employee_number,
    mail,
    work_email as adp__work_email,
from {{ ref("int_people__staff_roster") }}
where
    mail is not null
    and (
        employee_number != coalesce(custom_field__employee_number, -1)
        or mail != coalesce(work_email, '')
    )
