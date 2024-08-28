with
    assignment_group as (
        select
            sr.employee_number,
            sr.home_business_unit_name,

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
                    'Fellow School Operations Director',
                    'Managing Director of School Operations',
                    'Associate Director of School Operations'
                ),
                sr.job_title,
                'CMO and Other Leaders'
            ) as `route`,
        from {{ ref("int_people__staff_roster") }} as sr
        left join
            {{ ref("stg_leadership_development_active_users") }} as au
            on sr.employee_number = au.employee_number
        where au.active_title
    )

select
    ag.employee_number,

    ldm.academic_year,
    ldm.metric_id,

    concat(ag.employee_number, ldm.metric_id) as assignment_id,
from assignment_group as ag
inner join
    {{ ref("stg_performance_management__leadership_development_metrics") }} as ldm
    on ag.route = ldm.role
    and ag.home_business_unit_name = ldm.region

union all

select
    ag.employee_number,

    ldm.academic_year,
    ldm.metric_id,

    concat(ag.employee_number, ldm.metric_id) as assignment_id,
from assignment_group as ag
inner join
    {{ ref("stg_performance_management__leadership_development_metrics") }} as ldm
    on ag.route = ldm.role
    and ldm.region = 'All'
