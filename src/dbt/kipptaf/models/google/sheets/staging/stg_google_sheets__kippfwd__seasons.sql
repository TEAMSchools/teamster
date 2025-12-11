with
    admin_season as (
        select
            *,

            case
                admin_season when 'BOY' then 1 when 'MOY' then 2 else 3
            end as admin_season_order,

        from {{ source("google_sheets", "src_google_sheets__kippfwd__seasons") }}
    )

select *, concat(grade_level, admin_season_order) as grade_season,
from admin_season
