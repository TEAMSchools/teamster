select
    worker_id as `Associate ID`,
    employee_number as `Position ID`,
    preferred_name_given_name as `First Name`,
    preferred_name_family_name as `Last Name`,
    business_unit_assigned as `Company Code`,
    home_work_location_name as `Location Description`,
    department_assigned as `Business Unit Description`,
    department_assigned as `Home Department Description`,
    job_title as `Job Title Description`,
    report_to_employee_number as `Business Unit Code`,
    format_date('%m/%d/%Y', worker_rehire_date) as `Rehire Date`,
    format_date('%m/%d/%Y', worker_termination_date) as `Termination Date`,
    format_date('%m/%d/%Y', birth_date) as `Birth Date`,
    if(
        assignment_status = 'Pre-Start', 'Active', assignment_status
    ) as `Position Status`,
    null as `Preferred Name`,
from {{ ref("base_people__staff_roster") }}
where
    coalesce(worker_rehire_date, worker_original_hire_date)
    <= date_add(current_date('America/New_York'), interval 10 day)
    and business_unit_assigned is not null
    and home_work_location_name is not null
