select
    r._id as rubric_id,
    r.name,
    r.district,
    r.scalemin as scale_min,
    r.scalemax as scale_max,
    r.isprivate as is_private,
    r.ispublished as is_published,

    mg._id as measurement_group_id,
    mg.name as measurement_group_name,
    mg.key as measurement_group_key,
    mg.weight as measurement_group_weight,
    mg.description as measurement_group_description,

    m.measurement as measurement_id,
    m.key as measurement_key,
    m.weight as measurement_weight,
    m.isprivate as is_private_measurement,
    m.require as require_measurement,
    m.exclude as exclude_measurement,

    timestamp(r.archivedat) as archived_at,
    timestamp(r.created) as created,
    timestamp(r.lastmodified) as last_modified,
from {{ source("schoolmint_grow", "src_schoolmint_grow__rubrics") }} as r
-- trunk-ignore-begin(sqlfluff/CV12)
left join unnest(r.measurementgroups) as mg
left join unnest(mg.measurements) as m
-- trunk-ignore-end(sqlfluff/CV12)
where r._dagster_partition_key = 'f'
