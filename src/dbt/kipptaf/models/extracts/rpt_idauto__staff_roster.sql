select
    -- trunk-ignore-begin(sqlfluff/RF05)
    w.worker_id__id_value as `Associate ID`,
    w.given_name as `First Name`,
    w.family_name_1 as `Last Name`,
    w.job_title as `Job Title Description`,
    w.assignment_status__status_code__long_name as `Position Status`,
    w.organizational_unit__assigned__business_unit__name as `Company Code`,
    w.home_work_location_name as `Location Description`,
    w.organizational_unit__assigned__department__name as `Business Unit Description`,
    w.organizational_unit__assigned__department__name as `Home Department Description`,
    w.employee_number as `Position ID`,

    null as `Preferred Name`,

    cast(w.report_to_employee_number as string) as `Business Unit Code`,

    format_date('%m/%d/%Y', w.worker_dates__rehire_date) as `Rehire Date`,
    format_date('%m/%d/%Y', w.worker_dates__termination_date) as `Termination Date`,
    format_date('%m/%d/%Y', w.person__birth_date) as `Birth Date`,
-- trunk-ignore-end(sqlfluff/RF05)
from {{ ref("int_people__staff_roster") }} as w
where
    w.organizational_unit__assigned__business_unit__name is not null
    and w.organizational_unit__assigned__department__name is not null
    and date_diff(
        coalesce(w.worker_dates__rehire_date, w.worker_dates__original_hire_date),
        current_date('{{ var("local_timezone") }}'),
        day
    )
    <= 10
