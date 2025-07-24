with
    staff_roster as (
        select
            worker_id,
            position_id,
            worker_original_hire_date,
            employee_number,
            mail as work_email,
            badge_id as adp__badge,
            work_email as adp__work_email,
            custom_field__employee_number as adp__employee_number,
            time_service_supervisor_position_id
            as adp__time_service_supervisor_position_id,
            time_and_attendance_indicator as adp__time_and_attendance_indicator,
            worker_time_profile__time_zone_code
            as adp__worker_time_profile__time_zone_code,

            '000' || employee_number as badge,
        from {{ ref("int_people__staff_roster") }}
        where
            primary_indicator
            and employee_number is not null
            and mail is not null
            and worker_status_code = 'Active'
            and time_and_attendance_indicator
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
    wk.worker_id as `Employee ID`,
    wk.position_id as `Position ID`,

    /* required to be after ID */
    format_date('%m/%d/%Y', wk.worker_original_hire_date) as `Change Effective On`,

    /* personal information */
    wk.work_email as `Work E-Mail`,
    'W' as `E-Mail to Use For Notification`,

    /* custom fields */
    'Employment Custom Fields' as `CDF Category`,
    'Employee Number' as `CDF Label`,
    wk.employee_number as `CDF Value`,

    /* time & attendance */
    if(wk.adp__time_and_attendance_indicator, 'Y', 'N') as `Position Uses Time`,
    if(wk.adp__time_and_attendance_indicator, wk.badge, null) as `Badge`,
    if(
        wk.adp__time_and_attendance_indicator,
        wk.adp__time_service_supervisor_position_id,
        null
    ) as `Supervisorid`,
    if(
        wk.adp__time_and_attendance_indicator,
        wk.adp__worker_time_profile__time_zone_code,
        null
    ) as `TimeZone`,
    if(
        wk.adp__time_and_attendance_indicator, tna.transfer_to_payroll, null
    ) as `Transfertopayroll`,
    if(wk.adp__time_and_attendance_indicator, tna.pay_class, null) as `Payclass`,
    if(
        wk.adp__time_and_attendance_indicator, tna.supervisor_flag, null
    ) as `Supervisorflag`,

    /* audit */
    wk.adp__badge,
    wk.adp__work_email,
    wk.adp__employee_number,
-- trunk-ignore-end(sqlfluff/RF05)
from with_key as wk
inner join
    {{ ref("stg_adp_workforce_now__time_and_attendance") }} as tna
    on wk.position_id = tna.position_id
where
    wk.source_surrogate_key != wk.destination_surrogate_key
    or wk.adp__employee_number is null
