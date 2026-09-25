with
    live as (
        select
            google_email,
            staff_department_scope,
            staff_pii_scope,
            staff_compensation_scope,
            staff_observations_scope,
            staff_benefits_scope,
        from {{ ref("stg_google_sheets__people__cube_access_individual_exceptions") }}
        where
            {{ is_live_row("status", "grant_date", "expiry_date") }}
            and (
                staff_department_scope != 'inherit'
                or staff_pii_scope != 'inherit'
                or staff_compensation_scope != 'inherit'
                or staff_observations_scope != 'inherit'
                or staff_benefits_scope != 'inherit'
            )
    )

select google_email, count(*) as n_remit_rows,
from live
group by google_email
having count(*) > 1
