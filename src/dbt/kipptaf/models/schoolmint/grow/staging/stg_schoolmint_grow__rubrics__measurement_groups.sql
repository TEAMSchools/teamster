select
    r._id as rubric_id,
    mg.name as strand_name,
    mg._id as strand_id,
    mg.`key` as strand_key,
    mg.description as strand_description,
    mg.measurements,
from {{ ref("stg_schoolmint_grow__rubrics") }} as r
cross join unnest(r.measurementgroups) as mg
