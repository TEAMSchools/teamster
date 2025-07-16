with
    staff_roster as (
        select
            position_id,
            worker_original_hire_date,
            employee_number,
            mail as work_email,
            badge_id as adp__badge,
            work_email as adp__work_email,
            custom_field__employee_number as adp__employee_number,

            '000' || employee_number as badge,
        from {{ ref("int_people__staff_roster") }}
        where
            primary_indicator
            and employee_number is not null
            and mail is not null
            and worker_status_code = 'Active'
    ),

    with_key as (
        select
            *,

            {{ dbt_utils.generate_surrogate_key(["work_email", "badge"]) }}
            as source_surrogate_key,

            {{ dbt_utils.generate_surrogate_key(["adp__work_email", "adp__badge"]) }}
            as destination_surrogate_key,
        from staff_roster
    )

-- trunk-ignore(sqlfluff/ST06)
select
    -- trunk-ignore-begin(sqlfluff/RF05)
    position_id as `Position ID`,

    /* required to be after ID */
    format_date('%m/%d/%Y', worker_original_hire_date) as `Change Effective On`,

    /* personal information */
    work_email as `Work E-Mail`,
    'W' as `E-Mail to Use For Notification`,

    /* custom fields */
    'Employment Custom Fields' as `CDF Category`,
    'Employee Number' as `CDF Label`,
    employee_number as `CDF Value`,

    /* time & attendance */
    badge as `Badge`,

    /* comparison */
    adp__badge,
    adp__work_email,
    adp__employee_number,
-- trunk-ignore-end(sqlfluff/RF05)
from with_key
where source_surrogate_key != destination_surrogate_key or adp__employee_number is null
