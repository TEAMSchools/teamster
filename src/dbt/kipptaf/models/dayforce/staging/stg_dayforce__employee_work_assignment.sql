with
    parsed_dates as (
        select
            employee_reference_code,
            legal_entity_name,
            physical_location_name,
            department_name,
            job_name,
            flsa_status_name,
            job_family_name,
            pay_class_name,
            pay_type_name,
            parse_date(
                '%m/%d/%Y', work_assignment_effective_start
            ) as work_assignment_effective_start,
            coalesce(
                parse_date('%m/%d/%Y', work_assignment_effective_end), '2020-12-31'
            ) as work_assignment_effective_end,
        from {{ source("dayforce", "src_dayforce__employee_work_assignment") }}
        where primary_work_assignment
    ),

    with_prev as (
        select
            *,
            lag(work_assignment_effective_end, 1) over (
                partition by employee_reference_code
                order by work_assignment_effective_end asc
            ) as work_assignment_effective_end_prev,
        from parsed_dates
    )

select
    employee_reference_code as employee_number,
    legal_entity_name,
    physical_location_name,
    department_name,
    job_name,
    flsa_status_name,
    job_family_name,
    pay_class_name,
    pay_type_name,
    work_assignment_effective_end as work_assignment_effective_end_date,
    if(
        work_assignment_effective_start = work_assignment_effective_end_prev,
        date_add(work_assignment_effective_start, interval 1 day),
        work_assignment_effective_start
    ) as work_assignment_effective_start_date,
from with_prev
where work_assignment_effective_start <= '2020-12-31'
