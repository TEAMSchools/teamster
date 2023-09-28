with
    date_scaffold as (
        select
            employee_number,
            work_assignment_effective_start_date as effective_start_date,
        from {{ ref("stg_dayforce__employee_work_assignment") }}

        union distinct

        select employee_number, status_effective_start_date as effective_start_date,
        from {{ ref("stg_dayforce__employee_status") }}

        union distinct

        select employee_number, manager_effective_start_date as effective_start_date,
        from {{ ref("stg_dayforce__employee_manager") }}
    ),

    end_dates as (
        select
            employee_number,
            effective_start_date,
            coalesce(
                date_sub(
                    lead(effective_start_date, 1) over (
                        partition by employee_number order by effective_start_date asc
                    ),
                    interval 1 day
                ),
                '2020-12-31'
            ) as effective_end_date,
        from date_scaffold
    )

select
    ed.employee_number,
    safe_cast(ed.effective_start_date as timestamp) as effective_start_date,
    safe_cast(ed.effective_end_date as timestamp) as effective_end_date,
    if(ed.effective_end_date = '2020-12-31', true, false) as is_active,

    e.legal_first_name,
    e.legal_last_name,
    e.preferred_first_name,
    e.preferred_last_name,
    e.original_hire_date,
    e.rehire_date,
    e.termination_date,
    e.address,
    e.city,
    e.state,
    e.postal_code,
    e.mobile_number,
    e.birth_date,
    e.gender,
    e.ethnicity,
    e.preferred_last_name || ', ' || e.preferred_first_name as preferred_name_lastfirst,
    case
        ethnicity
        when 'Black or African American'
        then 'Black/African American'
        when 'Hispanic or Latino'
        then 'Latinx/Hispanic/Chicana(o)'
        when 'Two or more races (Not Hispanic or Latino)'
        then 'Bi/Multiracial'
        else ethnicity
    end as race_ethnicity_reporting,

    wa.work_assignment_effective_start_date,
    wa.work_assignment_effective_end_date,
    wa.legal_entity_name,
    wa.physical_location_name,
    wa.department_name,
    wa.job_name,
    wa.flsa_status_name,
    wa.job_family_name,
    wa.pay_class_name,
    wa.pay_type_name,

    s.status_effective_start_date,
    s.status_effective_end_date,
    s.status,
    s.status_reason_description,
    s.base_salary,

    m.manager_effective_start_date,
    m.manager_effective_end_date,
    m.manager_employee_number,

    {{
        dbt_utils.generate_surrogate_key(
            ["ed.employee_number", "wa.work_assignment_effective_start_date"]
        )
    }} as surrogate_key,
from end_dates as ed
inner join
    {{ ref("stg_dayforce__employees") }} as e on ed.employee_number = e.employee_number
left join
    {{ ref("stg_dayforce__employee_work_assignment") }} as wa
    on ed.employee_number = wa.employee_number
    and ed.effective_start_date
    between wa.work_assignment_effective_start_date
    and wa.work_assignment_effective_end_date
left join
    {{ ref("stg_dayforce__employee_status") }} as s
    on ed.employee_number = s.employee_number
    and ed.effective_start_date
    between s.status_effective_start_date and s.status_effective_end_date
left join
    {{ ref("stg_dayforce__employee_manager") }} as m
    on ed.employee_number = m.employee_number
    and ed.effective_start_date
    between m.manager_effective_start_date and m.manager_effective_end_date
{# bad records #}
where ed.employee_number not in (102553, 100764)
