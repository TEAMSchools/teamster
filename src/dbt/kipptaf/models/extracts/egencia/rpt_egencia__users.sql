-- trunk-ignore(sqlfluff/ST06)
select
    -- trunk-ignore-begin(sqlfluff/RF05)
    concat(sr.employee_number, '@kippnj.org') as `Username`,

    sr.mail as `Email`,
    sr.user_principal_name as `Single Sign On ID`,
    sr.employee_number as `Employee ID`,

    if(sr.assignment_status = 'Terminated', 'Disabled', 'Active') as `Status`,

    /* legal name */
    regexp_replace(normalize(sr.legal_given_name, nfd), r'\pM', '') as `First name`,
    regexp_replace(normalize(sr.legal_family_name, nfd), r'\pM', '') as `Last name`,

    if(tm.employee_number is not null, 'Travel Manager', 'Traveler') as `Role`,

    /* cascading match on home_work_location_name/dept/job */
    coalesce(
        tgx.traveler_group,
        tg.egencia_traveler_group,
        tg2.egencia_traveler_group,
        tg3.egencia_traveler_group,
        'General Traveler Group'
    ) as `Traveler Group`,
-- trunk-ignore-end(sqlfluff/RF05)
from {{ ref("int_people__staff_roster") }} as sr
left join
    {{ ref("stg_google_sheets__egencia__traveler_groups") }} as tg
    on sr.home_work_location_name = tg.adp_home_work_location_name
    and sr.home_department_name = tg.adp_department_home_name
    and sr.job_title = tg.adp_job_title
left join
    {{ ref("stg_google_sheets__egencia__traveler_groups") }} as tg2
    on sr.home_work_location_name = tg2.adp_home_work_location_name
    and sr.home_department_name = tg2.adp_department_home_name
    and tg2.adp_job_title = 'Default'
left join
    {{ ref("stg_google_sheets__egencia__traveler_groups") }} as tg3
    on sr.home_work_location_name = tg3.adp_home_work_location_name
    and tg3.adp_department_home_name = 'Default'
    and tg3.adp_job_title = 'Default'
left join
    {{ ref("stg_google_sheets__egencia__travel_managers") }} as tm
    on sr.employee_number = tm.employee_number
left join
    {{ ref("stg_google_sheets__egencia__traveler_group_exceptions") }} as tgx
    on sr.employee_number = tgx.employee_number
where
    sr.mail is not null
    and coalesce(sr.worker_type_code, '') not in ('Intern', 'Part Time')
    and coalesce(
        sr.worker_termination_date, current_date('{{ var("local_timezone") }}')
    )
    >= '{{ var("current_academic_year") }}-07-01'
