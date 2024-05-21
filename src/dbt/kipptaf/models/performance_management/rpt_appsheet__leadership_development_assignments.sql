with
    assignment_group as (
        select
            sr.employee_number,
            sr.business_unit_home_name,
            sr.preferred_name_lastfirst,
            sr.google_email,
            sr.assignment_status,
            sr2.google_email as google_email_manager,
            if(
                sr.job_title in (
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
                sr.job_title,
                'CMO and Other Leaders'
            ) as route,
        from {{ ref("base_people__staff_roster") }} as sr
        left join
            {{ ref("base_people__staff_roster") }} as sr2
            on sr.report_to_employee_number = sr2.employee_number
        where sr.assignment_status in ('Active', 'Leave')
    )
select
    ag.employee_number,
    ag.google_email,
    ag.google_email_manager,
    ag.route,

    ldm.academic_year,
    ldm.role as assignment_group,
    ldm.region as assignment_region,
    ldm.metric_id,
    ldm.bucket,
    ldm.type,
    ldm.description,

    concat(ag.employee_number, ldm.metric_id) as assignment_id,

from assignment_group as ag
cross join
    {{ ref("stg_performance_management__leadership_development_metrics") }} as ldm
where
    ag.route = ldm.role
    and (ag.business_unit_home_name = ldm.region or ldm.region = 'All')
    and ag.assignment_status in ('Active', 'Leave')
    /* Need '2024' to make visible before start of next academic year,
    will switch after 7/1/2024*/
    and ldm.academic_year = 2024
