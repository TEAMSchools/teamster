select u.user_id, r._id as role_id, r.name as role_name,
from {{ ref("stg_schoolmint_grow__users") }} as u
cross join unnest(u.roles) as r
