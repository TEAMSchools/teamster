with
    staff_roster as (
        select
            position_id,
            effective_date_start,
            employee_number,
            worker_original_hire_date,
            reports_to_position_id,
            time_service_supervisor_position_id as adp__supervisor_id,

            coalesce(badge_id, '') as adp__badge,
            '000' || employee_number as badge,
        from {{ ref("int_people__staff_roster_history") }}
        where
            primary_indicator
            and worker_original_hire_date
            between effective_date_start and effective_date_end
            and worker_original_hire_date >= '2025-07-01'  /* beginning of T&A usage */
    ),

    with_tna as (
        select
            sr.position_id,
            sr.worker_original_hire_date,
            sr.reports_to_position_id,
            sr.badge,
            sr.adp__badge,
            sr.adp__supervisor_id,

            tna.supervisor_flag as adp__supervisor_flag,
            tna.pay_class,

            if(
                sr.position_id in (
                    select rt.reports_to_position_id,
                    from staff_roster as rt
                    where rt.reports_to_position_id is not null
                ),
                'Y',
                'N'
            ) as supervisor_flag,
        from staff_roster as sr
        inner join
            {{ ref("stg_adp_workforce_now__time_and_attendance") }} as tna
            on sr.position_id = tna.position_id
            and tna.pay_class != 'NON-TIME'
    )

-- trunk-ignore(sqlfluff/ST06)
select
    -- trunk-ignore-begin(sqlfluff/RF05)
    position_id as `Position ID`,

    /* required to be after ID */
    format_date('%m/%d/%Y', worker_original_hire_date) as `Change Effective On`,

    /* time & attendance */
    badge as `Badge`,
    reports_to_position_id as `Supervisorid`,
    supervisor_flag as `Supervisorflag`,
    pay_class as `Payclass`,
    'EST' as `TimeZone`,
    'Y' as `Position Uses Time`,
    'Y' as `Transfertopayroll`,

    /* comparison */
    adp__badge,
-- trunk-ignore-end(sqlfluff/RF05)
from with_tna
where badge != adp__badge
