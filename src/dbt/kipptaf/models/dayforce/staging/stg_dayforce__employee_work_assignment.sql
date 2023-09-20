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
    )

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
    work_assignment_effective_end,
    coalesce(
        date_add(
            lag(work_assignment_effective_end, 1) over (
                partition by employee_reference_code, work_assignment_effective_start
                order by work_assignment_effective_end asc
            ),
            interval 1 day
        ),
        work_assignment_effective_start
    ) as work_assignment_effective_start,
from parsed_dates
where
    work_assignment_effective_end > work_assignment_effective_start
    and work_assignment_effective_start <= '2020-12-31'
