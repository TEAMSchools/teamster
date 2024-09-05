select o.observation_id, mn.`column`, mn.shared, mn.text, mn.created, mn._id,

from {{ ref("stg_schoolmint_grow__observations") }} as o
cross join unnest(o.magic_notes) as mn
