select
    position_id,
    badge,
    pay_class,
    supervisor_id,

    left(supervisor_position, 1) as supervisor_flag,
    left(include_in_time_summary_payroll, 1) as transfer_to_payroll,
from {{ source("adp_workforce_now", "src_adp_workforce_now__time_and_attendance") }}
where pay_class != 'NON-TIME'
