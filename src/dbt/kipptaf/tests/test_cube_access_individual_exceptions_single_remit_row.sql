with
    live as (
        select
            employee_number,
            staff_department_scope,
            staff_pii_scope,
            staff_compensation_scope,
            staff_observations_scope,
            staff_benefits_scope,
        from {{ ref("stg_google_sheets__people__cube_access_individual_exceptions") }}
        where
            {{ is_live_row("status", "grant_date", "expiry_date") }}
            and (
                staff_department_scope is not null
                or staff_pii_scope is not null
                or staff_compensation_scope is not null
                or staff_observations_scope is not null
                or staff_benefits_scope is not null
            )
    )

select employee_number, count(*) as n_remit_rows,
from live
group by employee_number
having count(*) > 1
