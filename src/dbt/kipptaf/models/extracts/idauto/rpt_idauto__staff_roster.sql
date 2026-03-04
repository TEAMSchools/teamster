select
    -- trunk-ignore-begin(sqlfluff/RF05)
    worker_id as `Associate ID`,
    given_name as `First Name`,
    family_name_1 as `Last Name`,
    job_title as `Job Title Description`,
    assignment_status as `Position Status`,
    assigned_business_unit_name as `Company Code`,
    home_work_location_name as `Location Description`,
    assigned_department_name as `Business Unit Description`,
    assigned_department_name as `Home Department Description`,
    employee_number as `Position ID`,

    null as `Preferred Name`,

    cast(reports_to_employee_number as string) as `Business Unit Code`,

    format_date('%m/%d/%Y', worker_rehire_date) as `Rehire Date`,
    format_date('%m/%d/%Y', worker_termination_date) as `Termination Date`,
    format_date('%m/%d/%Y', birth_date) as `Birth Date`,
-- trunk-ignore-end(sqlfluff/RF05)
from {{ ref("int_people__staff_roster") }}
where
    assigned_business_unit_name is not null
    and assigned_department_name is not null
    and date_diff(
        worker_hire_date_recent, current_date('{{ var("local_timezone") }}'), day
    )
    <= 10
