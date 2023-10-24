select
    -- noqa: disable=RF05
    worker_id as `Associate ID`,
    employee_number as `Position ID`,
    preferred_name_given_name as `First Name`,
    preferred_name_family_name as `Last Name`,
    business_unit_assigned_name as `Company Code`,
    home_work_location_name as `Location Description`,
    department_assigned_name as `Business Unit Description`,
    department_assigned_name as `Home Department Description`,
    job_title as `Job Title Description`,

    null as `Preferred Name`,

    safe_cast(report_to_employee_number as string) as `Business Unit Code`,
    format_date('%m/%d/%Y', worker_rehire_date) as `Rehire Date`,
    format_date('%m/%d/%Y', worker_termination_date) as `Termination Date`,
    format_date('%m/%d/%Y', birth_date) as `Birth Date`,
    if(is_prestart, 'Active', assignment_status) as `Position Status`,
from {{ ref("base_people__staff_roster") }}
where
    coalesce(worker_rehire_date, worker_original_hire_date)
    <= date_add(current_date('{{ var("local_timezone") }}'), interval 10 day)
    and business_unit_assigned_name is not null
    and home_work_location_name is not null
