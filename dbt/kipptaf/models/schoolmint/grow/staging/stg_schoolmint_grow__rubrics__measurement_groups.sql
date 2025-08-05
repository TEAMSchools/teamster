select
    r.rubric_id,

    mg._id as measurement_group_id,
    mg.name as measurement_group_name,
    mg.key as measurement_group_key,
    mg.weight as measurement_group_weight,
    mg.description as measurement_group_description,

    /* repeated records */
    mg.measurements,
from {{ ref("stg_schoolmint_grow__rubrics") }} as r
cross join unnest(r.measurement_groups) as mg
