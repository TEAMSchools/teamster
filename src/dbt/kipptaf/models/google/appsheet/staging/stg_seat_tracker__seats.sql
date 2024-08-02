select
    * except (edited_at, plan_status),

    coalesce(
        safe.parse_timestamp('%m/%d/%Y %T', edited_at, '{{ var("local_timezone") }}'),
        safe.parse_timestamp(
            '%a %b %d %Y %T', left(edited_at, 24), '{{ var("local_timezone") }}'
        )
    ) as edited_at,

    if(staffing_status = 'Open', true, false) as is_open,
    if(staffing_status = 'Staffed', true, false) as is_staffed,
    if(plan_status in ('Active', 'TRUE'), true, false) as is_active,
    if(status_detail in ('New Hire', 'Transfer In'), true, false) as is_new_hire,
    if(mid_year_hire, 1, 0) as is_mid_year_hire_int,
    case
        plan_status
        when 'TRUE'
        then 'Active'
        when 'FALSE'
        then 'Inactive'
        else plan_status
    end as plan_status,
from {{ source("google_appsheet", "src_seat_tracker__seats") }}
where academic_year is not null
