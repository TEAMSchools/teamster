select
    -- trunk-ignore-begin(sqlfluff/RF05)
    w.worker_id as `Associate ID`,
    w.given_name as `First Name`,
    w.family_name_1 as `Last Name`,
    w.job_title as `Job Title Description`,
    w.assignment_status as `Position Status`,
    w.assigned_business_unit as `Company Code`,
    w.home_work_location_name as `Location Description`,
    w.assigned_department as `Business Unit Description`,
    w.assigned_department as `Home Department Description`,
    w.employee_number as `Position ID`,

    null as `Preferred Name`,

    cast(w.reports_to_employee_number as string) as `Business Unit Code`,

    format_date('%m/%d/%Y', w.worker_rehire_date) as `Rehire Date`,
    format_date('%m/%d/%Y', w.worker_termination_date) as `Termination Date`,
    format_date('%m/%d/%Y', w.birth_date) as `Birth Date`,
-- trunk-ignore-end(sqlfluff/RF05)
from {{ ref("int_people__staff_roster") }} as w
where
    w.assigned_business_unit is not null
    and w.assigned_department is not null
    and date_diff(
        coalesce(w.worker_rehire_date, w.worker_original_hire_date),
        current_date('{{ var("local_timezone") }}'),
        day
    )
    <= 10
