with
    -- trunk-ignore(sqlfluff/ST03): referenced by string in dbt_utils.deduplicate
    measurements as (
        select
            mgm.rubric_id,
            mgm.measurement_id,
            mgm.measurement_group_name,
            mgm.measurement_group_weight,
            mgm.measurement_group_description,
            mgm.measurement_weight,
            mgm.is_private_measurement,
            mgm.require_measurement,
            mgm.exclude_measurement,
            mgm.measurement_group_id,
            m.`name`,
            m.`description`,
            m.scale_min,
            m.scale_max,
        from
            {{ ref("stg_schoolmint_grow__rubrics__measurement_groups__measurements") }}
            as mgm
        inner join
            {{ ref("stg_schoolmint_grow__measurements") }} as m
            on mgm.measurement_id = m.measurement_id
    ),

    -- Some rubrics reuse the same measurement under multiple strands — see
    -- model description. Pick the canonical strand (non-excluded, then
    -- alphabetical) so the dim's (rubric, measurement) PK is unique.
    deduplicated as (
        {{
            dbt_utils.deduplicate(
                relation="measurements",
                partition_by="rubric_id, measurement_id",
                order_by="exclude_measurement asc, measurement_group_id asc",
            )
        }}
    )

select
    {{ dbt_utils.generate_surrogate_key(["rubric_id", "measurement_id"]) }}
    as staff_observation_rubric_measurement_key,

    {{ dbt_utils.generate_surrogate_key(["rubric_id"]) }}
    as staff_observation_rubric_key,

    `name`,
    `description`,
    scale_min,
    scale_max,

    measurement_group_name as strand_name,
    measurement_group_weight as strand_weight,
    measurement_group_description as strand_description,
    measurement_weight as weight,
    is_private_measurement,
    require_measurement as is_required,
    exclude_measurement as is_excluded,
from deduplicated
