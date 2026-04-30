with
    staff as (
        select *,
        from {{ ref("int_people__staff_roster") }}
        where
            assignment_status in ('Active', 'Leave')
            and (
                home_business_unit_name = 'KIPP TEAM and Family Schools Inc.'
                or home_business_unit_name = 'KIPP Paterson'
                or (
                    home_business_unit_name in (
                        'KIPP Miami',
                        'TEAM Academy Charter School',
                        'KIPP Cooper Norcross Academy'
                    )
                    and (
                        contains_substr(job_title, 'Director')
                        or contains_substr(job_title, 'Head')
                        or contains_substr(job_title, 'Leader')
                    )
                )
            )
    ),

    managers as (
        select employee_number, work_email, from {{ ref("int_people__staff_roster") }}
    )

select
    s.assignment_status as `status`,
    s.work_email,
    s.job_title,
    s.employee_number as external_user_id,
    coalesce(s.worker_rehire_date, s.worker_original_hire_date) as `start_date`,
    s.home_department_name as department,

    m.work_email as manager_email,

    coalesce(s.given_name, s.legal_given_name) as first_name,
    coalesce(s.family_name_1, s.legal_family_name) as last_name,
from staff as s
left join managers as m on s.reports_to_employee_number = m.employee_number
