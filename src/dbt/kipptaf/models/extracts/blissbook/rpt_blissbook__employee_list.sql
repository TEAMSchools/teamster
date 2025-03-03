{{- config(enabled=false) -}}

select
    -- trunk-ignore-begin(sqlfluff/RF05)
    employee_number as `Employee ID`,
    mail as `Email Address`,
    assigned_business_unit_name as `Groups`,
    concat(given_name, ' ', family_name_1) as `Name`,
    coalesce(worker_rehire_date, worker_original_hire_date) as `Latest Hire Date`,
-- trunk-ignore-end(sqlfluff/RF05)
from {{ ref("int_people__staff_roster") }}
where worker_status_code != 'Terminated' and mail is not null
