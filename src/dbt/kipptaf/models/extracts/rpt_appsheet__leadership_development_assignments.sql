with
    leadership_development_metrics as (
        select *,
        from {{ ref("stg_performance_management__leadership_development_metrics") }}
        /*
            Need '2024' to make visible before start of next academic year will switch
            after 7/1/2024
        */
        where academic_year = 2024
    ),

    assignment_group as (
        select
            sr.employee_number,
            sr.business_unit_home_name,
            sr.preferred_name_lastfirst,
            sr.google_email,
            sr.assignment_status,
            sr.report_to_google_email,

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
        where sr.assignment_status in ('Active', 'Leave')
    )

select
    ag.employee_number,
    ag.google_email,
    ag.report_to_google_email,
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
inner join
    leadership_development_metrics as ldm
    on ag.route = ldm.role
    and ag.business_unit_home_name = ldm.region

union all

select
    ag.employee_number,
    ag.google_email,
    ag.report_to_google_email,
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
inner join
    leadership_development_metrics as ldm on ag.route = ldm.role and ldm.region = 'All'
