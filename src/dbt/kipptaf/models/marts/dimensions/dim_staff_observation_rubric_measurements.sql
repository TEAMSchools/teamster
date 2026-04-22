select
    {{ dbt_utils.generate_surrogate_key(["mgm.rubric_id", "mgm.measurement_id"]) }}
    as staff_observation_rubric_measurement_key,

    {{ dbt_utils.generate_surrogate_key(["mgm.rubric_id"]) }}
    as staff_observation_rubric_key,

    m.`name`,
    m.`description`,
    m.scale_min,
    m.scale_max,

    mgm.measurement_group_name as strand_name,
    mgm.measurement_group_key as strand_key,
    mgm.measurement_group_weight as strand_weight,
    mgm.measurement_group_description as strand_description,
    mgm.measurement_key,
    mgm.measurement_weight as weight,
    mgm.is_private_measurement,
    mgm.require_measurement as is_required,
    mgm.exclude_measurement as is_excluded,
from {{ ref("stg_schoolmint_grow__rubrics__measurement_groups__measurements") }} as mgm
inner join
    {{ ref("stg_schoolmint_grow__measurements") }} as m
    on mgm.measurement_id = m.measurement_id
