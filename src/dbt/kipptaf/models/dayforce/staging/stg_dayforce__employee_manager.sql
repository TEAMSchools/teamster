with
    employee_manager as (
        select
            employee_reference_code,
            manager_employee_number,
            parse_date('%m/%d/%Y', manager_effective_start) as manager_effective_start,
            coalesce(
                parse_date('%m/%d/%Y', manager_effective_end), '2020-12-31'
            ) as manager_effective_end,
        from {{ source("dayforce", "src_dayforce__employee_manager") }}
        where manager_derived_method = 'Direct Report'
    )

select *
from employee_manager
where manager_effective_start < manager_effective_end
