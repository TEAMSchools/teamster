select
    s.school_id,

    og._id as observation_group_id,
    og.name as observation_group_name,
    og.observers,
    og.observees,
from {{ ref("stg_schoolmint_grow__schools") }} as s
cross join unnest(s.observationgroups) as og
