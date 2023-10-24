with
    parsed_dates as ( -- noqa: ST03
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

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="parsed_dates",
                partition_by="employee_reference_code, manager_effective_start",
                order_by="manager_effective_end desc",
            )
        }}
    ),

    with_next as (
        select
            *,
            lead(manager_effective_start, 1) over (
                partition by employee_reference_code
                order by manager_effective_start asc
            ) as manager_effective_start_next,
        from deduplicate
    )

select
    employee_reference_code as employee_number,
    manager_employee_number,
    manager_effective_start as manager_effective_start_date,
    coalesce(
        date_sub(manager_effective_start_next, interval 1 day), '2020-12-31'
    ) as manager_effective_end_date,
from with_next
where manager_effective_start <= '2020-12-31'
