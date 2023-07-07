select og.observation_group_id, osv._id as user_id, osv.name, osv.email,
from {{ ref("stg_schoolmint_grow__schools_observationgroups") }} as og
cross join unnest(og.observees) as osv
