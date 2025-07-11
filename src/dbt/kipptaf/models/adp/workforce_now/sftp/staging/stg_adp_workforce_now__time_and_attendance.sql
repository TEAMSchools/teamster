select
    position_id,
    badge,
    pay_class,
    supervisor_id,

    left(supervisor_position, 1) as supervisor_flag,

    parse_date('%m/%d/%Y', start_using_time_attendance) as start_using_time_attendance,
    parse_date('%m/%d/%Y', stop_using_time_attendance) as stop_using_time_attendance,
from {{ source("adp_workforce_now", "src_adp_workforce_now__time_and_attendance") }}
