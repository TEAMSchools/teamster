with
    roster as (
        select
            employee_number,
            formatted_name,
            case
                when
                    job_title in (
                        'Teacher',
                        'Teacher In Residence',
                        'Learning Specialist',
                        'ESE Teacher'
                    )
                then 'Classroom Teacher'
                when
                    job_title in (
                        'Assistant School Leader',
                        'Assistant School Leader, SPED',
                        'School Leader',
                        'School Leader in Residence',
                        'Social Worker',
                        'Counselor',
                        'Dean of Students',
                        'Head of Schools',
                        'Executive Director'
                    )
                then 'Instructional Staff'
            end as worker_category,
        from {{ ref("int_people__staff_roster") }}
        where
            home_business_unit_name = 'KIPP Miami'
            and worker_hire_date_recent < '2024-06-30'
            and (
                worker_termination_date is null
                or worker_termination_date > '2024-07-01'
            )
    ),

    salary_history as (
        select distinct roster.*, history.base_remuneration_annual_rate_amount, history.effective_date_start,
        from roster
        left join
            {{ ref("int_people__staff_roster_history") }} as history
            on roster.employee_number = history.employee_number

    ),

    academic_year_23 as (
        select
            employee_number,
            worker_category,
            min(base_remuneration_annual_rate_amount) as pay_23
        from salary_history
        where effective_date_start between date(2023, 07, 01) and date(2024, 06, 30)
        group by all

    ),

    academic_year_24 as (
        select
            employee_number,
            worker_category,
            max(base_remuneration_annual_rate_amount) as pay_24
        from salary_history
        where effective_date_start between date(2024, 07, 01) and date(2025, 06, 30)
        group by all
    )

select
    roster.employee_number,
    roster.formatted_name,
    roster.worker_category,
    academic_year_23.pay_23,
    academic_year_24.pay_24
from roster
inner join
    academic_year_23
    on roster.employee_number = academic_year_23.employee_number
    and roster.worker_category = academic_year_23.worker_category
inner join
    academic_year_24
    on roster.employee_number = academic_year_24.employee_number
    and roster.worker_category = academic_year_24.worker_category
