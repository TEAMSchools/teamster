select a.assignment_id, t._id as tag_id, t.name as tag_name, t.url as tag_url,
from {{ ref("stg_schoolmint_grow__assignments") }} as a
cross join unnest(a.tags) as t
