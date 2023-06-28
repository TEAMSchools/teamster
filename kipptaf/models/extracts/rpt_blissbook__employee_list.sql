select
    employee_number as `employee id`,
    mail as `email address`,
    business_unit_assigned as `groups`,
    concat(preferred_name_given_name, ' ', preferred_name_family_name) as `name`,
    coalesce(worker_rehire_date, worker_original_hire_date) as `latest hire date`
from {{ ref("base_people__staff_roster") }}
where status_value != 'Terminated' and mail is not null
