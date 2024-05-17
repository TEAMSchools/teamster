with
    assignment_group as (
        select
            employee_number,
            if
            (
                job_title in (
                    'Assistant School Leader',
                    'Assistant School Leader, SPED',
                    'Assistant School Leader, School Culture',
                    'School Leader',
                    'School Leader in Residence',
                    'Head of Schools',
                    'Head of Schools in Residence',
                    'Director School Operations',
                    'Director Campus Operations',
                    'Managing Director of School Operations'
                ),
                job_title,
                'CMO and Other Leaders'
            ) as route,
        from {{ ref("base_people__staff_roster") }}
        where assignment_status in ('Active', 'Leave')
    )
select

    sr.home_work_location_name as location,
    sr.business_unit_home_name as region,
    sr.department_home_name as department,
    sr.job_title,
    sr.preferred_name_lastfirst,
    sr.employee_number,
    sr.sam_account_name,
    sr.google_email,

    sr2.google_email as google_email_manager,

    ldm.academic_year,
    ldm.role as assignment_group,
    ldm.region as assignment_region,
    ldm.metric_id,
    ldm.bucket,
    ldm.type,
    ldm.description,

    ag.route,

    concat(sr.employee_number, ldm.metric_id) as assignment_id,

from {{ ref("base_people__staff_roster") }} as sr
cross join
    {{ ref("stg_performance_management__leadership_development_metrics") }} as ldm
where
    ag.route = ldm.role
    and (sr.business_unit_home_name = ldm.region or ldm.region = 'All')
    and sr.assignment_status in ('Active', 'Leave')
    and ldm.active = true
order by sr.employee_number
