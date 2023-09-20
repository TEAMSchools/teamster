with
    parsed_dates as (
        select
            employee_reference_code,
            manager_employee_number,
            parse_date('%m/%d/%Y', manager_effective_start) as manager_effective_start,
            coalesce(
                parse_date('%m/%d/%Y', manager_effective_end), '2020-12-31'
            ) as manager_effective_end,
        from {{ source("dayforce", "src_dayforce__employee_manager") }}
        where manager_derived_method = 'Direct Report'
    ),

    start_order as (
        select
            *,
            row_number() over (
                partition by employee_reference_code, manager_effective_start
                order by manager_effective_end asc
            ) as rn_employee_start,
        from parsed_dates
        where manager_effective_start <= '2020-12-31'
    )

select
    employee_reference_code,
    manager_employee_number,
    manager_effective_end,
    coalesce(
        date_add(
            lag(manager_effective_end, 1) over (
                partition by employee_reference_code, manager_effective_start
                order by manager_effective_end asc
            ),
            interval 1 day
        ),
        manager_effective_start
    ) as manager_effective_start,
from start_order
where manager_effective_end > manager_effective_start
