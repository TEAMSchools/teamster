select
    mg.rubric_id,
    mg.strand_name,
    mg.strand_id,
    mg.strand_key,
    mg.strand_description,
    m.measurement as measurement_id,
from {{ ref("stg_schoolmint_grow__rubrics__measurement_groups") }} as mg
cross join unnest(mg.measurements) as m
