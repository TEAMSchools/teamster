{{ config(enabled=False) }}

select
    concat(sub.employee_number, '@kippnj.org') as `Username`,
    sr.mail as `Email`,
    sr.userprincipalname as `Single Sign On ID`,
    sr.employee_number as `Employee ID`,
    case
        when sr.position_status = 'Terminated' then 'Disabled' else 'Active'
    end as `Status`,
    sr.first_name as `First name`,  /* legal name */
    sr.last_name as `Last name`,  /* legal name */
    case
        when sub.employee_number in (100219, 100412, 100566, 102298)
        then 'Travel Manager'
        else 'Traveler'
    end as `Role`,

    /* cascading match on location/dept/job */
    coalesce(
        tg.egencia_traveler_group,
        tg2.egencia_traveler_group,
        tg3.egencia_traveler_group,
        'General Traveler Group'
    ) as `Traveler Group`,

{# sr.location,
    sr.home_department,
    sr.job_title, #}
from {{ ref("base_people__staff_roster") }} as sr
left join
    egencia.traveler_groups as tg
    on sub.location = tg.location
    and sub.home_department = tg.home_department
    and sub.job_title = tg.job_title
left join
    egencia.traveler_groups as tg2
    on sub.location = tg2.location
    and sub.home_department = tg2.home_department
    and tg2.job_title = 'Default'
left join
    egencia.traveler_groups as tg3
    on sub.location = tg3.location
    and tg3.home_department = 'Default'
    and tg3.job_title = 'Default'
where
    (sr.worker_category not in ('Intern', 'Part Time') or sr.worker_category is null)
    and coalesce(sr.termination_date, current_timestamp)
    >= datefromparts(utilities.global_academic_year(), 7, 1)
