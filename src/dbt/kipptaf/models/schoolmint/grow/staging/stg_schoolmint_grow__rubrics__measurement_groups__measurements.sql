select
    mg.rubric_id,
    mg.measurement_group_id,

    m._id,  /* not documented anywhere - ID of shame */
    m.measurement as measurement_id,
    m.key,
    m.weight,
    m.isprivate as is_private,
    m.require,
    m.exclude,
from {{ ref("stg_schoolmint_grow__rubrics__measurement_groups") }} as mg
cross join unnest(mg.measurements) as m
