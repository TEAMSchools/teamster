select u.id as user_id, cg.id as content_group_id, cg.name as content_group_name,
from {{ source("coupa", "src_coupa__users") }} as u
cross join unnest(u.content_groups) as cg
