with
    supervisors as (
        select reports_to_position_id,
        from {{ ref("int_people__staff_roster") }}
        where reports_to_position_id is not null
    ),

    staff_roster as (
        select
            sr.position_id,
            sr.employee_number,
            sr.mail,
            sr.reports_to_position_id,

            sr.custom_field__employee_number as adp__custom_field__employee_number,
            sr.work_email as adp__work_email,

            {# TODO: calculate using ??? #}
            null as pay_class,
            {# TODO: add from API when available #}
            null as adp__badge,
            null as adp__supervisor_id,
            null as adp__supervisor_flag,
            null as adp__pay_class,

            if(s.reports_to_position_id is not null, 'Y', 'N') as supervisor_flag,
        from {{ ref("int_people__staff_roster") }} as sr
        left join supervisors as s on sr.position_id = s.reports_to_position_id
    ),

    surrogate_keys as (
        select
            *,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "employee_number",
                        "mail",
                        "employee_number",
                        "reports_to_position_id",
                        "supervisor_flag",
                        "pay_class",
                    ]
                )
            }} as source_surrogate_key,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "adp__custom_field__employee_number",
                        "adp__work_email",
                        "adp__badge",
                        "adp__supervisor_id",
                        "adp__supervisor_flag",
                        "adp__pay_class",
                    ]
                )
            }} as destination_surrogate_key,
        from staff_roster
    )

select
    -- trunk-ignore-begin(sqlfluff/RF05)
    position_id as `Position ID`,
    mail as `Work E-mail`,
    employee_number as `CDF Value`,
    employee_number as `Badge`,
    reports_to_position_id as `Supervisorid`,
    supervisor_flag as `Supervisorflag`,
    pay_class as `Payclass`,

    'Employment Custom Fields' as `CDF Category`,
    'Employee Number' as `CDF Label`,
    'EST' as `TimeZone`,
    'W' as `E-Mail to Use For Notification`,
    'Y' as `Position Uses Time`,
    'Y' as `Transfertopayroll`,

    format_date(
        '%m/%d/%Y', current_date('{{ var("local_timezone") }}')
    ) as `Change Effective On`,
-- trunk-ignore-end(sqlfluff/RF05)
from surrogate_keys
where source_surrogate_key != destination_surrogate_key
