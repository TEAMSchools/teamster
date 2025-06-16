with
    supervisors as (
        select distinct reports_to_position_id,
        from {{ ref("int_people__staff_roster") }}
        where reports_to_position_id is not null
    )

select
    -- trunk-ignore-begin(sqlfluff/RF05)
    sr.worker_id as `Employee ID`,
    sr.position_id as `Position ID`,
    sr.employee_number as `Badge`,
    sr.mail as `Work E-mail`,
    sr.reports_to_position_id as `Supervisorid`,
    sr.employee_number as `CDF Value`,
    null as `Payclass`,

    sr.custom_field__employee_number as adp__custom_field__employee_number,
    sr.work_email as adp__work_email,
    null as adp__badge,

    'Employment Custom Fields' as `CDF Category`,
    'Employee Number' as `CDF Label`,
    'EST' as `TimeZone`,
    'W' as `E-Mail to Use For Notification`,
    'Y' as `Position Uses Time`,
    'Y' as `Transfertopayroll`,

    format_date(
        '%m/%d/%Y', current_date('{{ var("local_timezone") }}')
    ) as `Change Effective On`,

    if(s.reports_to_position_id is not null, 'Y', 'N') as `Supervisorflag`,
-- trunk-ignore-end(sqlfluff/RF05)
from {{ ref("int_people__staff_roster") }} as sr
left join supervisors as s on sr.position_id = s.reports_to_position_id
