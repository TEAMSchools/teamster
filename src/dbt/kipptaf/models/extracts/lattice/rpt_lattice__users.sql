with
    staff as (
        select *,
        from {{ ref("int_people__staff_roster") }}
        where
            job_title <> 'Intern'
            -- exclude temps and part-timers: worker_type_code is the primary
            -- signal (nulls kept -- they are legitimate full-time staff); the
            -- job_title checks are a fallback for HR mislabeling of the type
            and (
                worker_type_code is null
                or not (
                    contains_substr(worker_type_code, 'Temporary')
                    or contains_substr(worker_type_code, 'Part Time')
                )
            )
            and not contains_substr(job_title, 'Temporary')
            and not contains_substr(job_title, 'Part Time')
            and not contains_substr(job_title, 'Part-Time')
            and (
                home_business_unit_name = 'KIPP TEAM and Family Schools Inc.'
                or home_business_unit_name = 'KIPP Paterson'
                or (
                    home_business_unit_name = 'KIPP Miami'
                    and (
                        contains_substr(job_title, 'Director')
                        or contains_substr(job_title, 'Head')
                        or contains_substr(job_title, 'Leader')
                        or contains_substr(job_title, 'Dean')
                        or home_work_location_name = 'Room 11'
                    )
                )
                or (
                    home_business_unit_name
                    in ('TEAM Academy Charter School', 'KIPP Cooper Norcross Academy')
                    and job_title in (
                        'Director School Operations',
                        'Director Campus Operations',
                        'Managing Director of School Operations',
                        'Managing Director of Operations'
                    )
                )
                or (
                    home_business_unit_name
                    in ('TEAM Academy Charter School', 'KIPP Cooper Norcross Academy')
                    and home_department_name
                    in ('Technology', 'Marketing, Comms, and Enrollment')
                )
            )
            and (
                assignment_status in ('Active', 'Leave')
                or worker_termination_date >= date_sub(
                    current_date('{{ var("local_timezone") }}'), interval 30 day
                )
            )
    ),

    managers as (
        select employee_number, work_email, from {{ ref("int_people__staff_roster") }}
    )

select
    s.employee_number as external_user_id,
    s.work_email,
    s.job_title,
    s.worker_hire_date_recent as `start_date`,
    s.home_department_name as department,

    m.work_email as manager_email,

    coalesce(s.given_name, s.legal_given_name) as first_name,
    coalesce(s.family_name_1, s.legal_family_name) as last_name,
    coalesce(s.home_work_location_abbreviation, s.home_work_location_name) as location,

    if(s.assignment_status in ('Active', 'Leave'), 'Active', 'Inactive') as `status`,

    case
        s.home_business_unit_name
        when 'KIPP TEAM and Family Schools Inc.'
        then 'KTAF'
        when 'KIPP Paterson'
        then 'Paterson'
        when 'KIPP Miami'
        then 'Miami'
        when 'TEAM Academy Charter School'
        then 'Newark'
        when 'KIPP Cooper Norcross Academy'
        then 'Camden'
    end as business_unit,
from staff as s
left join managers as m on s.reports_to_employee_number = m.employee_number
