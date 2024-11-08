{{- config(enabled=false) -}}

select
    -- trunk-ignore-begin(sqlfluff/RF05)
    employee_number as `Employee ID`,
    mail as `Email Address`,
    business_unit_assigned_name as `Groups`,
    concat(preferred_name_given_name, ' ', preferred_name_family_name) as `Name`,
    coalesce(worker_rehire_date, worker_original_hire_date) as `Latest Hire Date`,
-- trunk-ignore-end(sqlfluff/RF05)
from {{ ref("base_people__staff_roster") }}
where status_value != 'Terminated' and mail is not null
