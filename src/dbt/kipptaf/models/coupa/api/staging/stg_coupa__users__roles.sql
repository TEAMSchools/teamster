select u.id as user_id, r.id as role_id, r.name as role_name,
from {{ source("coupa", "src_coupa__users") }} as u
cross join unnest(u.roles) as r
