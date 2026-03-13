with
    rubric_measurements as (
        select
            rubric_id,
            name as rubric_name,
            cast(scale_min as float64) as rubric_scale_min,
            cast(scale_max as float64) as rubric_scale_max,
            measurement_group_id,
            measurement_group_name as strand_name,
            cast(measurement_group_weight as float64) as measurement_group_weight,
            measurement_id,
            cast(measurement_weight as float64) as measurement_weight,
        from {{ ref("stg_schoolmint_grow__rubrics__measurement_groups__measurements") }}
    ),

    measurements as (
        select
            measurement_id,
            name as measurement_name,
            description as measurement_description,
        from {{ ref("stg_schoolmint_grow__measurements") }}
    )

select
    rm.rubric_id,
    rm.rubric_name,
    rm.rubric_scale_min,
    rm.rubric_scale_max,
    rm.measurement_group_id,
    rm.strand_name,
    rm.measurement_group_weight,
    rm.measurement_id,
    m.measurement_name,
    m.measurement_description,
    rm.measurement_weight,

    {{
        dbt_utils.generate_surrogate_key(
            ["rm.rubric_id", "rm.measurement_group_id", "rm.measurement_id"]
        )
    }} as rubric_measurement_key,
from rubric_measurements as rm
left join measurements as m on rm.measurement_id = m.measurement_id
