select
    s.school_id,

    og._id as observation_group_id,
    og.name as observation_group_name,
    og.observers as observation_group_observers,
    og.observees as observation_group_observees,
from {{ ref("stg_schoolmint_grow__schools") }} as s
cross join unnest(s.observation_groups) as og
