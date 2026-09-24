with
    live_grants as (
        select google_email,
        from {{ ref("stg_google_sheets__people__cube_access_individual_exceptions") }}
        where is_live
    )

select lg.google_email,
from live_grants as lg
left join {{ ref("dim_staff_cube_access") }} as a on lg.google_email = a.google_email
where a.google_email is null
group by lg.google_email
