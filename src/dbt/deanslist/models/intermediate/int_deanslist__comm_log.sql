select
    cl.*,

    u.full_name as user_full_name,

    row_number() over (
        partition by cl.student_school_id, cl.academic_year, cl.reason
        order by cl.call_date desc, cl.call_date_time desc
    )
    = 1 as is_latest_for_reason,
from {{ ref("stg_deanslist__comm_log") }} as cl
left join {{ ref("stg_deanslist__users") }} as u on cl.user_id_str = u.dl_user_id
