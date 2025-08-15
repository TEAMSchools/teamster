select cl.*, u.full_name as user_full_name,
from {{ ref("stg_deanslist__comm_log") }} as cl
left join {{ ref("stg_deanslist__users") }} as u on cl.user_id = u.dl_user_id
