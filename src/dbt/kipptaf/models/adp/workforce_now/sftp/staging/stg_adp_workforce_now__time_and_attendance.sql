select
    position_id,
    badge,
    pay_class,
    supervisor_id,

    left(supervisor_position, 1) as supervisor_flag,
from {{ source("adp_workforce_now", "src_adp_workforce_now__time_and_attendance") }}
where pay_class != 'NON-TIME'
